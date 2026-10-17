"""固定原本の許可された保存・読戻し。実GitHub通信は注入されたアダプターが担当。

このモジュール自体はGitHubへ接続しない。write/readが実際に成功したと
ツール応答とcommit固定読戻しで確認した場合だけ成功状態を返す。
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from prediction_clock import safe_for_write

ALLOWED_PATHS = (
    "docs/validation/persistence-intents/",
    "docs/validation/fix-manifests/",
    "docs/validation/snapshots/",
    "docs/validation/recommendations/",
    "docs/validation/persistence-receipts/",
    "docs/validation/persistence-incidents/",
    "docs/validation/reviews/",
)
TRANSIENT = {"transport", "timeout", "rate_limit", "server_unavailable"}
BLOCKED = {"safety_refusal", "authorization", "branch_policy", "unknown"}
REDACT = re.compile(
    r"(?i)(authorization\s*[:=]\s*bearer\s+\S+|bearer\s+\S+|gh[pousr]_[a-zA-Z0-9_]+|github_pat_[a-zA-Z0-9_]+|"
    r"(?:token|secret|password|authorization|api[_-]?key)\s*[:=]\s*[^\s,;]+)"
)


def sanitized(value):
    if value is None:
        return None
    return REDACT.sub("[REDACTED]", str(value))[:1200]


def sha256(raw):
    if not isinstance(raw, bytes):
        raise ValueError("fixed payload must be bytes")
    return hashlib.sha256(raw).hexdigest()


def allowed_target(repository, branch, path):
    if repository != "eda-hub/horse-man" or not re.fullmatch(r"prediction/\d{4}-\d{2}-\d{2}", branch or ""):
        raise ValueError("repository or prediction branch outside authorized scope")
    posix = Path(path)
    if posix.is_absolute() or ".." in posix.parts or "\\" in path or path.endswith("/"):
        raise ValueError("unsafe path")
    if not any(path.startswith(prefix) for prefix in ALLOWED_PATHS):
        raise ValueError("path outside approved prediction evidence scope")


def classify_failure(*, kind=None, http_status=None, text=None, api_reached=None):
    """HTTP statusだけで安全性拒否と決めつけない。"""
    if kind == "safety_refusal":
        return "safety_refusal"
    if kind == "ci_or_checker":
        return "ci_or_checker"
    if kind == "branch_policy":
        return "branch_policy"
    if kind in {"timeout", "transport"}:
        return kind
    if http_status in (401, 403):
        return "authorization" if api_reached else "unknown"
    if http_status in (409, 412, 422):
        return "conflict"
    if http_status in (429, 500, 502, 503, 504):
        return "rate_limit" if http_status == 429 else "server_unavailable"
    if kind in {"branch_policy", "authorization", "conflict"}:
        return kind
    return "unknown"


@dataclass(frozen=True)
class FixedPayload:
    repository: str
    branch: str
    path: str
    body: bytes
    digest: str = field(init=False)

    def __post_init__(self):
        allowed_target(self.repository, self.branch, self.path)
        object.__setattr__(self, "digest", sha256(self.body))


@dataclass
class PersistenceResult:
    target: dict
    write_state: str = "NOT_ATTEMPTED"
    readback_state: str = "NOT_ATTEMPTED"
    timing_state: str = "UNDETERMINED"
    completion_verified: bool = False
    failure_category: str | None = None
    retry_allowed: bool = False
    commit_sha: str | None = None
    operations: list = field(default_factory=list)

    def as_dict(self):
        return {**vars(self), "operations": list(self.operations)}


class PersistenceError(Exception):
    def __init__(self, message, *, kind=None, http_status=None, api_reached=None,
                 request_id=None, tool=None):
        super().__init__(message)
        self.kind = kind
        self.http_status = http_status
        self.api_reached = api_reached
        self.request_id = request_id
        self.tool = tool


def _instant():
    return datetime.now(timezone.utc).isoformat()


def _failure(result, exc, *, operation, attempt, path):
    category = classify_failure(kind=exc.kind, http_status=exc.http_status,
                                text=str(exc), api_reached=exc.api_reached)
    result.failure_category = category
    result.operations.append(dict(operation=operation, attempt=attempt, path=path,
                                  at_utc=_instant(), category=category,
                                  api_reached=exc.api_reached,
                                  http_status=exc.http_status,
                                  tool=sanitized(exc.tool),
                                  request_id=sanitized(exc.request_id),
                                  reason=sanitized(exc)))
    result.retry_allowed = category in TRANSIENT
    return category


def _read(transport, payload, ref=None):
    """read(branch,path,commit_sha)はref指定時必ずそのcommitから返す契約。"""
    try:
        response = transport.read(payload.branch, payload.path, ref)
    except FileNotFoundError as exc:
        if ref is None:
            raise
        raise PersistenceError("fixed commit readback missing", kind="unknown",
                               api_reached=True) from exc
    if response.get("branch") != payload.branch or response.get("path") != payload.path:
        raise PersistenceError("readback branch/path mismatch", kind="conflict", api_reached=True)
    if ref is not None and response.get("commit_sha") != ref:
        raise PersistenceError("readback commit mismatch", kind="conflict", api_reached=True)
    body = response.get("content")
    if not isinstance(body, bytes):
        raise PersistenceError("readback bytes unavailable", kind="unknown", api_reached=True)
    return response


def persist_fixed(payload, transport, clock_check, *, operation_id,
                  max_resaves=2, allow_update=False, alternative=None,
                  alternative_authorized=False):
    """応答欠落時もまずremoteを読取り、同一原本だけ最大2回再保存。

    transport.read(branch,path,ref) -> {branch,path,content:bytes,commit_sha,blob_sha}
    transport.write(branch,path,body,expected_blob_sha) -> {commit_sha,branch,path}
    alternativeは通信系障害かつ事前許可された場合のみ利用する。
    安全性拒否・理由不明の場合に経路を切替えない。
    """
    if not isinstance(payload, FixedPayload) or not operation_id:
        raise ValueError("immutable payload and operation ID required")
    if not 0 <= max_resaves <= 2:
        raise ValueError("max_resaves must be between 0 and 2")
    result = PersistenceResult(target=dict(repository=payload.repository,
                                            branch=payload.branch, path=payload.path,
                                            sha256=payload.digest, operation_id=operation_id))
    route = transport
    expected = None
    for attempt in range(max_resaves + 1):
        # 不明応答・timeout後にも先にremoteを確認し、上書きや重複を回避する。
        try:
            existing = _read(route, payload)
            if sha256(existing["content"]) == payload.digest and existing.get("commit_sha"):
                result.write_state = "ALREADY_PRESENT"
                result.commit_sha = existing["commit_sha"]
                exact = _read(route, payload, result.commit_sha)
                if sha256(exact["content"]) != payload.digest:
                    raise PersistenceError("commit readback digest mismatch", kind="conflict", api_reached=True)
                result.readback_state = "MATCH"
                result.failure_category = None
                result.retry_allowed = False
                result.operations.append(dict(operation="readback", attempt=attempt,
                                              at_utc=_instant(), commit_sha=result.commit_sha))
                # 既存原本の存在と、今この時点での発走前適格は別の概念。
                try:
                    gate = clock_check("readback")
                except (ValueError, OSError, KeyError, TypeError) as exc:
                    gate = {"status": "UNDETERMINED", "reason": sanitized(exc)}
                result.timing_state = gate.get("status", "UNDETERMINED")
                return result
            expected = existing.get("blob_sha")
            if not allow_update:
                result.failure_category = "conflict"
                result.operations.append(dict(operation="read", attempt=attempt,
                                              reason="different existing bytes; update not approved"))
                return result
            if not expected:
                raise PersistenceError("existing blob SHA missing", kind="unknown", api_reached=True)
        except FileNotFoundError:
            expected = None
        except PersistenceError as exc:
            category = _failure(result, exc, operation="read", attempt=attempt, path=payload.path)
            if category not in TRANSIENT:
                return result
            if alternative is not None and alternative_authorized:
                route = alternative  # 通信障害時の事前許可済み独立経路のみ
            if attempt == max_resaves:
                return result
            continue

        try:
            gate = clock_check("before_write")  # 必ず今取り直した時計の結果を渡す
        except (ValueError, OSError, KeyError, TypeError) as exc:
            gate = {"status": "UNDETERMINED", "reason": sanitized(exc)}
        result.timing_state = gate.get("status", "UNDETERMINED")
        result.operations.append(dict(operation="clock", attempt=attempt,
                                      at_utc=_instant(), status=result.timing_state,
                                      remaining_seconds=gate.get("remaining_seconds")))
        if not safe_for_write(gate):
            return result
        try:
            response = route.write(payload.branch, payload.path, payload.body, expected)
            if response.get("branch") != payload.branch or response.get("path") != payload.path:
                raise PersistenceError("write target mismatch", kind="conflict", api_reached=True)
            commit_sha = response.get("commit_sha")
            if not isinstance(commit_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", commit_sha):
                raise PersistenceError("write commit missing or invalid", kind="unknown", api_reached=True)
            result.commit_sha = commit_sha
            result.write_state = "WRITTEN"
            result.operations.append(dict(operation="write", attempt=attempt,
                                          at_utc=_instant(), commit_sha=commit_sha,
                                          expected_blob_sha=expected))
            readback = _read(route, payload, commit_sha)
            if sha256(readback["content"]) != payload.digest:
                raise PersistenceError("commit readback content mismatch", kind="conflict", api_reached=True)
            result.readback_state = "MATCH"
            result.failure_category = None
            result.retry_allowed = False
            result.operations.append(dict(operation="readback", attempt=attempt,
                                          at_utc=_instant(), commit_sha=commit_sha))
            try:
                post_gate = clock_check("readback")
            except (ValueError, OSError, KeyError, TypeError) as exc:
                post_gate = {"status": "UNDETERMINED", "reason": sanitized(exc)}
            result.timing_state = post_gate.get("status", "UNDETERMINED")
            # 個別完了にはreceipt等の独立確認が必要。このモジュールでは昇格しない。
            return result
        except PersistenceError as exc:
            category = _failure(result, exc, operation="write_or_readback",
                                attempt=attempt, path=payload.path)
            if category not in TRANSIENT:
                return result
            if alternative is not None and alternative_authorized:
                route = alternative
            if attempt == max_resaves:
                return result
    return result


def incident_record(payload, result, *, observed_at=None, unavailable_fields=()):
    """公開可能なメタデータのみ。固定原本bytesとエラー原文の秘密は出力しない。"""
    return dict(schema_version="prediction-persistence-incident-v1",
                incident_at_utc=observed_at or _instant(),
                target=result.target, write_state=result.write_state,
                readback_state=result.readback_state, timing_state=result.timing_state,
                individual_completion=False, failure_category=result.failure_category,
                retry_allowed=result.retry_allowed,
                inaccessible_fields=list(unavailable_fields),
                operations=result.operations,
                origin_hash_sha256=payload.digest,
                remote_persistence_certified=False)


def save_incident_local(path, record):
    """ローカル保全だけを実施。GitHubの正式receiptにはならない。"""
    destination = Path(path)
    if destination.exists():
        raise FileExistsError("incident record already exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    return destination


class GitHubContentsTransport:
    """許可された既存日次branchでのみGitHub Contents APIを使用する。

    接続済みChatGPT GitHubツールとは別の実行アダプター。トークンは環境変数から
    利用側が明示的に受け渡す。資格情報・権限・branchを作成しない。
    """
    def __init__(self, repository, branch, token):
        import urllib.parse
        if not token or repository != "eda-hub/horse-man":
            raise ValueError("explicit token and approved repository required")
        if not re.fullmatch(r"prediction/\d{4}-\d{2}-\d{2}", branch):
            raise ValueError("only prediction date branch may be written")
        self.repository = repository
        self.branch = branch
        self._token = token
        self._base = "https://api.github.com/repos/" + urllib.parse.quote(repository, safe="/")
        # 存在しないbranchをmainから自動生成しない。
        self._call("GET", "/branches/" + urllib.parse.quote(branch, safe=""))

    def _call(self, method, suffix, body=None):
        import urllib.error
        import urllib.request
        url = self._base + suffix
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
        req = urllib.request.Request(url, data=payload, method=method, headers={
            "Accept": "application/vnd.github+json",
            "Authorization": "Bearer " + self._token,
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "horse-man-persistence-v1",
            "Content-Type": "application/json",
        })
        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            request_id = exc.headers.get("x-github-request-id") if exc.headers else None
            body = exc.read(3000).decode("utf-8", errors="replace")
            message = sanitized(body)
            if exc.code == 404 and method == "GET" and "/contents/" in suffix:
                raise FileNotFoundError("GitHub path not found") from exc
            raise PersistenceError(message, kind="branch_policy" if "protected branch" in body.lower() else None,
                                   http_status=exc.code, api_reached=True,
                                   request_id=request_id, tool="github_contents_rest") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise PersistenceError("network failure: " + sanitized(exc),
                                   kind="transport", api_reached=None,
                                   tool="github_contents_rest") from exc

    def read(self, branch, path, ref=None):
        import base64
        import urllib.parse
        if branch != self.branch:
            raise ValueError("read branch mismatch")
        allowed_target(self.repository, branch, path)
        target_ref = ref or branch
        endpoint = ("/contents/" + urllib.parse.quote(path, safe="/") +
                    "?ref=" + urllib.parse.quote(target_ref, safe=""))
        result = self._call("GET", endpoint)
        if result.get("type") != "file" or result.get("encoding") != "base64":
            raise PersistenceError("GitHub content is not base64 file", kind="unknown", api_reached=True)
        raw = base64.b64decode(result["content"], validate=False)
        # commit固定refの読み戻しはGitHubが解決した同一refのファイル。
        # branch HEADの現存確認はref固定とは独立している。
        return {"branch": branch, "path": path, "content": raw,
                "blob_sha": result.get("sha"),
                "commit_sha": ref or self._branch_head()}

    def _branch_head(self):
        import urllib.parse
        b = self._call("GET", "/branches/" + urllib.parse.quote(self.branch, safe=""))
        return b["commit"]["sha"]

    def write(self, branch, path, content, expected_blob_sha):
        import base64
        import urllib.parse
        if branch != self.branch:
            raise ValueError("write branch mismatch")
        allowed_target(self.repository, branch, path)
        data = {"message": "固定原本を保存し読戻し照合する",
                "branch": branch, "content": base64.b64encode(content).decode("ascii")}
        if expected_blob_sha is not None:
            data["sha"] = expected_blob_sha
        response = self._call("PUT", "/contents/" + urllib.parse.quote(path, safe="/"), data)
        return {"branch": branch, "path": path,
                "commit_sha": response.get("commit", {}).get("sha")}


def main(argv=None):
    import argparse
    import os
    from prediction_clock import observed_assessment
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", required=True)
    parser.add_argument("--race-id", required=True)
    parser.add_argument("--path", required=True, help="repository relative path")
    parser.add_argument("--payload-file", type=Path, required=True, help="fixed local bytes")
    parser.add_argument("--operation-id", required=True)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--token-env", default="GITHUB_TOKEN")
    parser.add_argument("--allow-update", action="store_true", help="explicit exact-SHA update approval")
    parser.add_argument("--write", action="store_true", help="required for GitHub persistence")
    parser.add_argument("--local-incident", type=Path, help="write only sanitized incident metadata")
    args = parser.parse_args(argv)
    branch = "prediction/" + args.date
    try:
        payload = FixedPayload("eda-hub/horse-man", branch, args.path,
                               args.payload_file.read_bytes())
        if not args.write:
            raise ValueError("remote write requires explicit --write")
        token = os.environ.get(args.token_env)
        if not token:
            raise ValueError("GitHub token unavailable; no remote write attempted")
        transport = GitHubContentsTransport(payload.repository, payload.branch, token)
        result = persist_fixed(payload, transport,
                               lambda stage: observed_assessment(args.root,args.date,args.race_id),
                               operation_id=args.operation_id, allow_update=args.allow_update)
        print(json.dumps(result.as_dict(), ensure_ascii=False, indent=2))
        if result.readback_state != "MATCH" or result.timing_state != "PRE_SCHEDULED":
            if args.local_incident:
                save_incident_local(args.local_incident, incident_record(payload, result))
            return 1
        print("固定原本のGitHub commit読戻し一致。receiptと独立個別完了は別途必要。")
        return 0
    except (ValueError, OSError, PersistenceError, KeyError, TypeError) as exc:
        print("保存未完了：" + sanitized(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
