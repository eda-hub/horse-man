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
    "docs/validation/recommendation-intents/",
    "docs/validation/recommendation-gates/",
    "docs/validation/recommendation-prediction-gates/",
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


RACE_ID_RE = re.compile(r"^(\\d{4}-\\d{2}-\\d{2})-(TOKYO|KYOTO|NIIGATA)-(0[1-9]|1[0-2])$")
RACE_HINT_RE = re.compile(r"(?<![A-Za-z0-9])(?:\\d{8}|\\d{4}-\\d{2}-\\d{2})[-_](TOKYO|KYOTO|NIIGATA)[-_](0[1-9]|1[0-2])(?=[-_.]|$)", re.I)
LOCAL_RACE_RE = re.compile(r"(?<![a-z0-9])(tokyo|kyoto|niigata)[-_](0[1-9]|1[0-2])(?=[-_.]|$)", re.I)
DATE_DIRS = {"snapshots", "fix-manifests", "persistence-intents",
             "recommendations", "recommendation-intents", "recommendation-gates",
             "recommendation-prediction-gates", "persistence-incidents", "reviews"}


def _race_parts(race_id, date):
    match = RACE_ID_RE.fullmatch(race_id or "")
    if match is None or match.group(1) != date:
        raise ValueError("race ID/date mismatch or unsupported race identity")
    return match.group(2), match.group(3)


def _target_parts(payload, race_id):
    """新規原本の承認済み単一用途pathを確認。日付/場/レースの取り違えを防ぐ。"""
    date = payload.branch.removeprefix("prediction/")
    venue, number = _race_parts(race_id, date)
    parts = payload.path.split("/")
    if len(parts) < 4 or parts[:2] != ["docs", "validation"]:
        raise ValueError("unrecognized persistence target")
    category = parts[2]
    suffix = parts[3:]
    if category not in DATE_DIRS | {"persistence-receipts"}:
        raise ValueError("persistence target category not approved")
    if category == "recommendation-gates" and suffix[:1] == ["history"]:
        suffix = suffix[1:]
    if category in DATE_DIRS:
        if len(suffix) != 2 or suffix[0] != date or not suffix[1].endswith(".json"):
            raise ValueError("evidence path date or extension mismatch")
        filename = suffix[1]
    else:
        if len(suffix) != 1 or not suffix[0].startswith(date) or not suffix[0].endswith(".md"):
            raise ValueError("receipt path date or extension mismatch")
        filename = suffix[0]
        if filename != date + ".md" and not filename.startswith(date + "-"):
            raise ValueError("receipt basename outside race date")
    for text in (payload.path, filename):
        for found in RACE_HINT_RE.finditer(text):
            if found.group(1).upper() != venue or found.group(2) != number:
                raise ValueError("target path race differs from requested race")
    for found in LOCAL_RACE_RE.finditer(filename):
        if found.group(1).upper() != venue or found.group(2) != number:
            raise ValueError("target filename race differs from requested race")
    if category in {"snapshots", "fix-manifests", "recommendations",
                    "recommendation-gates", "recommendation-prediction-gates"}:
        marker = venue + "-" + number
        if marker not in filename.upper():
            raise ValueError("race-specific evidence filename required")
    if category == "recommendation-intents" and not LOCAL_RACE_RE.search(filename):
        raise ValueError("recommendation intent filename must identify the race")
    return category, date


def _json_or_receipt(payload, category):
    try:
        decoded = payload.body.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("evidence must be UTF-8") from exc
    if category == "persistence-receipts":
        records = re.findall(r"```persistence-receipt-v1\\s*(\\{.*?\\})\\s*```",
                             decoded, flags=re.S)
        if not records:
            raise ValueError("receipt structured records required")
        try:
            return [json.loads(part) for part in records]
        except json.JSONDecodeError as exc:
            raise ValueError("invalid structured receipt") from exc
    try:
        obj = json.loads(decoded)
    except json.JSONDecodeError as exc:
        raise ValueError("fixed JSON evidence required") from exc
    if not isinstance(obj, dict):
        raise ValueError("fixed evidence must be a JSON object")
    return [obj]


def _identity_values(obj):
    """ID/pathと日時のメタデータを収集。自由記述やURL内の数字は判定材料にしない。"""
    if isinstance(obj, list):
        for value in obj:
            yield from _identity_values(value)
    elif isinstance(obj, dict):
        for key, value in obj.items():
            if key in {"race_id", "race_date_jst", "working_branch",
                       "scheduled_post_time_jst", "deadline_jst",
                       "snapshot_id", "recommendation_id", "artifact_id",
                       "artifact_path", "prediction_intent_path", "intent_path",
                       "receipt_path", "receipt_id", "previous_receipt_ref",
                       "baseline_forecast_id", "required_race_ids"}:
                yield key, value
            if isinstance(value, (dict, list)):
                yield from _identity_values(value)


def verify_payload_binding(payload, race_id):
    """原本/保存先/CLIレースの一致をGitHub初期化・遠隔read/write前に確定する。

    公式時刻は返値のclock検査で突合する。時刻のないgate/FIXもrace/pathは必須。
    """
    category, date = _target_parts(payload, race_id)
    venue, number = _race_parts(race_id, date)
    objects = _json_or_receipt(payload, category)
    schema = {"snapshots": "prediction-snapshot-v2",
              "fix-manifests": "prediction-fix-manifest-v1",
              "persistence-intents": "prediction-persistence-intent-v1",
              "recommendations": "recommendation-snapshot-v1",
              "recommendation-intents": "recommendation-persistence-intent-v1",
              "recommendation-gates": "recommendation-compliance-v1",
              "recommendation-prediction-gates": "prediction-compliance-v2",
              "persistence-incidents": "prediction-persistence-incident-v1"}
    post_values = []
    deadline_values = []
    has_race = False
    for item in objects:
        if not isinstance(item, dict):
            raise ValueError("structured evidence must be an object")
        if category in schema and item.get("schema_version") != schema[category]:
            raise ValueError("evidence schema/path category mismatch")
        if category == "persistence-receipts" and not item.get("receipt_id"):
            raise ValueError("receipt ID required")
        for key, value in _identity_values(item):
            if key == "race_id":
                if value != race_id:
                    raise ValueError("payload race ID differs from requested race")
                has_race = True
            elif key == "required_race_ids":
                if not isinstance(value, list) or race_id not in value or not all(
                        RACE_ID_RE.fullmatch(v) and v[:10] == date
                        for v in value if isinstance(v, str)) or any(
                        not isinstance(v, str) for v in value):
                    raise ValueError("prediction intent race scope mismatch")
                has_race = True
            elif key == "race_date_jst" and value != date:
                raise ValueError("payload race date differs from target branch")
            elif key == "working_branch" and value != payload.branch:
                raise ValueError("payload working branch mismatch")
            elif key in {"scheduled_post_time_jst", "deadline_jst"}:
                from prediction_clock import aware, JST
                try:
                    parsed = aware(value, key).astimezone(JST)
                except (ValueError, TypeError) as exc:
                    raise ValueError("invalid payload scheduled/deadline time") from exc
                if parsed.date().isoformat() != date:
                    raise ValueError("payload post time date differs from target branch")
                (post_values if key == "scheduled_post_time_jst" else deadline_values).append(parsed)
            elif key in {"snapshot_id", "recommendation_id", "artifact_id",
                         "artifact_path", "prediction_intent_path", "intent_path",
                         "receipt_path", "receipt_id", "previous_receipt_ref",
                         "baseline_forecast_id"} and isinstance(value, str):
                if key.endswith("_path") and value.startswith("docs/validation/"):
                    # 別レースの日時が参照先に混入していないことも確認する。
                    for token in value.split("/"):
                        if re.fullmatch(r"\\d{4}-\\d{2}-\\d{2}", token) and token != date:
                            raise ValueError("referenced evidence date mismatch")
                for match in RACE_HINT_RE.finditer(value):
                    if match.group(1).upper() != venue or match.group(2) != number:
                        raise ValueError("payload reference race mismatch")
                for match in LOCAL_RACE_RE.finditer(value):
                    if match.group(1).upper() != venue or match.group(2) != number:
                        raise ValueError("payload reference race mismatch")
    if not has_race and category not in {"fix-manifests"}:
        raise ValueError("payload race identity required")
    # FIXではsnapshot_idとartifact_pathでレースを証明する。
    if category == "fix-manifests":
        if not any(RACE_HINT_RE.search(str(item.get("snapshot_id", ""))) and
                   RACE_HINT_RE.search(str(item.get("artifact_path", "")))
                   for item in objects):
            raise ValueError("FIX snapshot and artifact race identity required")
    if category in {"snapshots", "recommendations", "recommendation-prediction-gates"} and not post_values:
        raise ValueError("payload official scheduled post time required")
    if category == "persistence-intents" and not deadline_values:
        raise ValueError("prediction intent deadline required")
    if category == "recommendation-intents" and not deadline_values:
        raise ValueError("recommendation intent deadline required")
    if category == "persistence-receipts" and not post_values:
        raise ValueError("receipt scheduled post required")
    return dict(race_id=race_id, race_date=date,
                scheduled_posts=post_values, deadlines=deadline_values,
                multi_race_intent=category == "persistence-intents" and
                any(len(item.get("required_race_ids", [])) > 1 for item in objects))


def verify_clock_binding(gate, identity):
    """公式chainの判定を要求race/date/postと原本に照合。外れた時計は常に未判定。"""
    from prediction_clock import aware
    if not isinstance(gate, dict) or gate.get("race_id") != identity["race_id"] or (
            gate.get("race_date") != identity["race_date"]) or not gate.get("official_source"):
        return {"status": "UNDETERMINED", "reason": "clock race/date/source mismatch"}
    try:
        official = aware(gate.get("scheduled_post_jst"), "clock scheduled post")
        if any(aware(post) != official for post in identity["scheduled_posts"]):
            raise ValueError("payload scheduled post differs from official clock")
        for deadline in identity["deadlines"]:
            if identity["multi_race_intent"]:
                if aware(deadline) > official:
                    raise ValueError("intent deadline exceeds requested race post")
            elif aware(deadline) != official:
                raise ValueError("intent deadline differs from official clock post")
    except (ValueError, TypeError) as exc:
        return {"status": "UNDETERMINED", "reason": str(exc)}
    return gate


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


def persist_fixed(payload, transport, clock_check, *, operation_id, race_id,
                  max_resaves=2, allow_update=False, alternative=None,
                  alternative_authorized=False):
    """応答欠落時もまずremoteを読取り、同一原本だけ最大2回再保存。

    transport.read(branch,path,ref) -> {branch,path,content:bytes,commit_sha,blob_sha}
    transport.write(branch,path,body,expected_blob_sha) -> {commit_sha,branch,path}
    alternativeは通信系障害かつ事前許可された場合のみ利用する。
    安全性拒否・理由不明の場合に経路を切替えない。
    allow_updateは旧呼出互換のみ（固定原本の異内容上書きは常に禁止）。
    """
    if not isinstance(payload, FixedPayload) or not operation_id:
        raise ValueError("immutable payload and operation ID required")
    if not 0 <= max_resaves <= 2:
        raise ValueError("max_resaves must be between 0 and 2")
    identity = verify_payload_binding(payload, race_id)
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
                    gate = verify_clock_binding(clock_check("readback"), identity)
                except (ValueError, OSError, KeyError, TypeError) as exc:
                    gate = {"status": "UNDETERMINED", "reason": sanitized(exc)}
                result.timing_state = gate.get("status", "UNDETERMINED")
                return result
            # 固定原本は一切上書きしない。旧allow_update指定も許可の根拠にしない。
            # 別内容は新revision/pathで保存し、既存bytesは保全する。
            result.failure_category = "conflict"
            result.operations.append(dict(operation="read", attempt=attempt,
                                          at_utc=_instant(),
                                          reason="immutable fixed content differs; create a new revision"))
            return result
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
            gate = verify_clock_binding(clock_check("before_write"), identity)  # 当該レースの新鮮な公式時計
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
                post_gate = verify_clock_binding(clock_check("readback"), identity)
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


def initialization_failure(payload, operation_id, error):
    """branch存在確認・接続初期化の失敗も保存要求と同じ構造で保全する。"""
    result = PersistenceResult(target=dict(repository=payload.repository,
                                           branch=payload.branch, path=payload.path,
                                           sha256=payload.digest, operation_id=operation_id))
    if not isinstance(error, PersistenceError):
        error = PersistenceError(sanitized(error), kind="unknown", api_reached=None,
                                 tool="github_contents_initialize")
    _failure(result, error, operation="transport_initialize", attempt=0,
             path=payload.path)
    # 初期化が一度も完了していない場合、再試行許可は自動判断しない。
    result.retry_allowed = False
    return result


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
        # 呼出側がpersist_fixedを経由しなくても、固定原本のPUT更新を許さない。
        if expected_blob_sha is not None:
            raise PersistenceError("immutable fixed content update refused; new revision required",
                                   kind="conflict", api_reached=False,
                                   tool="github_contents_rest")
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
    parser.add_argument("--allow-update", action="store_true", help="deprecated: fixed content updates are refused")
    parser.add_argument("--write", action="store_true", help="required for GitHub persistence")
    parser.add_argument("--local-incident", type=Path, help="write only sanitized incident metadata")
    args = parser.parse_args(argv)
    branch = "prediction/" + args.date
    payload = None
    result = None
    try:
        payload = FixedPayload("eda-hub/horse-man", branch, args.path,
                               args.payload_file.read_bytes())
        if not args.write:
            raise ValueError("remote write requires explicit --write")
        if args.allow_update:
            raise ValueError("fixed contents are immutable; create a new revision/path instead")
        verify_payload_binding(payload, args.race_id)  # GitHub branch確認前に拒否
        token = os.environ.get(args.token_env)
        if not token:
            raise ValueError("GitHub token unavailable; no remote write attempted")
        # 初期化時のbranch確認403/通信障害も後段の例外処理で構造化保全。
        transport = GitHubContentsTransport(payload.repository, payload.branch, token)
        result = persist_fixed(payload, transport,
                               lambda stage: observed_assessment(args.root,args.date,args.race_id),
                               operation_id=args.operation_id, race_id=args.race_id)
        print(json.dumps(result.as_dict(), ensure_ascii=False, indent=2))
        if result.readback_state != "MATCH" or result.timing_state != "PRE_SCHEDULED":
            if args.local_incident:
                save_incident_local(args.local_incident, incident_record(payload, result))
            return 1
        print("固定原本のGitHub commit読戻し一致。receiptと独立個別完了は別途必要。")
        return 0
    except (ValueError, OSError, PersistenceError, KeyError, TypeError) as exc:
        print("保存未完了：" + sanitized(exc))
        if args.local_incident and payload is not None and result is None:
            record = incident_record(payload, initialization_failure(payload, args.operation_id, exc))
            try:
                save_incident_local(args.local_incident, record)
            except (OSError, ValueError) as log_error:
                print("障害記録のローカル保存も失敗：" + sanitized(log_error))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
