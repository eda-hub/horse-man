#!/usr/bin/env python3
"""Git管理の血統調査台帳。取得・推測・予想への自動加点は行わない。"""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

SCHEMA = "pedigree-registry-v1"
RESEARCH_SCHEMA = "pedigree-research-v1"
TAXONOMY_SCHEMA = "pedigree-taxonomy-v1"
KEY_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{2,79}$")
HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")
FACT_FIELDS = {
    "parent.sire", "parent.dam", "attribute.training_country",
    "attribute.breeding_country",
}
VERIFICATION = {"VERIFIED", "UNVERIFIED"}
ERRORS = {"NOT_FOUND", "SOURCE_ERROR"}
SOURCE_CLASSES = {
    "OFFICIAL_JRA_VAN", "OFFICIAL_JRA", "BREEDING_DB",
    "MEDIA_ORIGINAL", "WEB_AGGREGATOR", "USER_RELAYED",
    "INTERNAL_DERIVED",
}


class RegistryError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise RegistryError(message)


def stamp(value):
    require(isinstance(value, str), "時刻はタイムゾーン付きISO 8601文字列が必要")
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RegistryError("時刻形式が不正: " + value) from exc
    require(parsed.tzinfo is not None and parsed.utcoffset() is not None, "時刻にタイムゾーンが必要")
    return parsed.astimezone(dt.timezone.utc)


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def hash_object(value):
    data = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    return hashlib.sha256(data).hexdigest()


def key_check(key):
    require(isinstance(key, str) and KEY_PATTERN.fullmatch(key), "horse_key/request_idが不正")
    return key


def field_check(field):
    require(field in FACT_FIELDS, "未対応の血統項目: " + str(field))


def load(path, default=None):
    if not path.exists():
        if default is not None:
            return default
        raise RegistryError("ファイルが存在しない: " + str(path))
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError) as exc:
        raise RegistryError("JSONを読み取れない: " + str(path)) from exc


def file_blob_sha(path):
    if not path.exists():
        return "ABSENT"
    content = path.read_bytes()
    return hashlib.sha1(b"blob " + str(len(content)).encode() + b"\0" + content).hexdigest()


def guard_head(expected, root):
    if expected is None:
        return
    cp = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=False, capture_output=True, text=True,
    )
    require(cp.returncode == 0 and cp.stdout.strip() == expected, "作業HEADが変更されたため保存を拒否")


@contextlib.contextmanager
def single_writer(root):
    root.mkdir(parents=True, exist_ok=True)
    lock = root / ".registry.lock"
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise RegistryError("別のWriterが使用中。競合を確認してから再実行") from exc
    try:
        os.close(fd)
        yield
    finally:
        lock.unlink(missing_ok=True)


def atomic_save(path, object_value, expected_blob="ABSENT"):
    require(file_blob_sha(path) == expected_blob, "保存対象のblobが変更されたため再読込が必要")
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(object_value, indent=2, ensure_ascii=False, sort_keys=True) + "\n").encode()
    fd, temporary = tempfile.mkstemp(prefix=".pedigree-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        if path.read_bytes() != payload or hash_object(load(path)) != hash_object(object_value):
            raise RegistryError("保存内容の読戻し照合に失敗")
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return {"status": "PERSIST_VERIFIED", "path": str(path), "sha256": hashlib.sha256(payload).hexdigest(),
            "git_blob_sha": file_blob_sha(path), "verified_at": now()}


class Registry:
    def __init__(self, root, expected_head=None):
        self.root = Path(root).resolve()
        self.horses = self.root / "horses"
        self.research = self.root / "research"
        self.taxonomies = self.root / "taxonomies"
        self.expected_head = expected_head

    def path(self, key):
        return self.horses / (key_check(key) + ".json")

    def read_horse(self, key):
        horse = load(self.path(key))
        require(horse.get("schema_version") == SCHEMA and horse.get("horse_key") == key,
                "馬レコードのschema/key不一致: " + key)
        require(isinstance(horse.get("revisions"), list), "revisionの形式が不正")
        return horse

    def all_horses(self):
        if not self.horses.exists():
            return []
        return [self.read_horse(p.stem) for p in sorted(self.horses.glob("*.json"))]

    def resolve(self, selector):
        horses = self.all_horses()
        if "horse_key" in selector:
            candidate = [h for h in horses if h["horse_key"] == selector["horse_key"]]
        elif "provider" in selector and "external_id" in selector:
            candidate = [h for h in horses if any(
                x.get("provider") == selector["provider"] and x.get("id") == selector["external_id"]
                for x in h["identity"].get("external_ids", [])
            )]
        elif "name" in selector:
            name = selector["name"].casefold().strip()
            candidate = [h for h in horses if name in [
                n.casefold().strip() for n in h["identity"].get("names", [])
            ]]
        else:
            raise RegistryError("horse_keyまたはprovider+external_idまたはnameで指定")
        if len(candidate) != 1 or candidate[0]["identity"].get("status") != "RESOLVED":
            return {"status": "IDENTITY_UNRESOLVED", "candidates": [x["horse_key"] for x in candidate]}
        return {"status": "RESOLVED", "horse_key": candidate[0]["horse_key"]}

    def register(self, identity, expected_blob="ABSENT"):
        key = key_check(identity["horse_key"])
        values = identity["identity"]
        require(values.get("status") in {"RESOLVED", "UNRESOLVED"}, "同定状態が不正")
        require(isinstance(values.get("names"), list) and values["names"]
                and all(isinstance(n, str) and n.strip() for n in values["names"]), "名称が必要")
        require(len(values["names"]) == len(set(values["names"])), "同一レコードの別名が重複")
        require(isinstance(values.get("external_ids"), list), "external_idsは配列")
        require(isinstance(values.get("birth_year"), int) or values.get("birth_year") is None,
                "生年の形式が不正")
        require(isinstance(values.get("country"), str) or values.get("country") is None,
                "国の形式が不正")
        if values["status"] == "RESOLVED":
            require(values.get("identity_evidence") and values.get("identity_checked_at"),
                    "同定済みの根拠と照合時刻が必要")
            stamp(values["identity_checked_at"])
        for record in self.all_horses():
            require(record["horse_key"] != key, "既存horse_keyの上書きは不可")
            for eid in values["external_ids"]:
                require(not any(eid.get("provider") == prev.get("provider") and eid.get("id") == prev.get("id")
                                for prev in record["identity"].get("external_ids", [])), "外部IDが既存馬と重複")
        for eid in values["external_ids"]:
            require(isinstance(eid, dict) and eid.get("provider") and eid.get("id"), "外部IDの項目不足")
        item = {"schema_version": SCHEMA, "horse_key": key, "identity": values, "revisions": []}
        with single_writer(self.root):
            guard_head(self.expected_head, self.root)
            return atomic_save(self.path(key), item, expected_blob)

    def _validate_revision(self, h, rev):
        field = rev.get("field")
        field_check(field)
        require(rev.get("verification") in VERIFICATION, "verificationが不正")
        observed = stamp(rev["first_observed_at"])
        captured = stamp(rev["captured_at"])
        require(observed <= captured, "captured_atがfirst_observed_atより前")
        if "provider_timestamp" in rev and rev["provider_timestamp"] is not None:
            stamp(rev["provider_timestamp"])
        source = rev.get("source") or {}
        require(source.get("source_class") in SOURCE_CLASSES, "source_classが不正")
        require(all(source.get(k) for k in ("origin_group", "acquisition_method", "record_sha256")),
                "出所の識別子・取得方法・hash不足")
        require(bool(source.get("url")) != bool(source.get("provider_record_key")),
                "URLまたはprovider_record_keyを一つ指定")
        require(HASH_PATTERN.fullmatch(source["record_sha256"]), "原レコードhashはsha256")
        if rev["verification"] == "VERIFIED":
            check = rev.get("verification_evidence") or {}
            require(all(check.get(k) for k in ("checked_by", "method", "checked_at")),
                    "VERIFIEDには検証担当/手法/検証時刻が必要")
            require(stamp(check["checked_at"]) >= observed, "検証時刻が観測前")
        else:
            require(not rev.get("verification_evidence"), "未確認レコードに検証証跡を付けない")
        value = rev.get("value")
        require(isinstance(value, str) and value.strip(), "valueには非空文字列を指定")
        if field.startswith("parent."):
            key_check(value)
            require(value != h["horse_key"], "自己を親とする循環を拒否")
            parent = self.read_horse(value)
            require(parent["identity"]["status"] == "RESOLVED", "親馬の同定が未解決")
        if field.endswith("_country"):
            require(len(value) <= 100, "国の値が長すぎる")
        prev = rev.get("previous_revision_id")
        if prev:
            require(rev.get("correction_reason"), "訂正理由が必要")
            prior = [x for x in h["revisions"] if x["revision_id"] == prev]
            require(len(prior) == 1 and prior[0]["field"] == field, "訂正元revisionがない")
            require(observed >= stamp(prior[0]["first_observed_at"]), "過去へ訂正を遡及できない")
            require(not any(x.get("previous_revision_id") == prev for x in h["revisions"]),
                    "訂正済みrevisionを再度直接訂正できない")
        else:
            require(not rev.get("correction_reason"), "訂正理由だけの登録は禁止")

    def add_fact(self, payload, expected_blob):
        key = key_check(payload["horse_key"])
        with single_writer(self.root):
            guard_head(self.expected_head, self.root)
            require(file_blob_sha(self.path(key)) == expected_blob, "blob競合。読直して再統合")
            horse = self.read_horse(key)
            require(horse["identity"]["status"] == "RESOLVED", "同定未解決の事実は確定登録不可")
            revision = {k: v for k, v in payload.items() if k not in ("horse_key", "revision_id")}
            self._validate_revision(horse, revision)
            fp = hash_object(revision)
            for existing in horse["revisions"]:
                if existing.get("content_sha256") == fp:
                    return {"status": "REUSED", "revision_id": existing["revision_id"],
                            "git_blob_sha": expected_blob}
                if (existing["source"].get("record_sha256") == revision["source"]["record_sha256"]
                    and existing["source"].get("origin_group") == revision["source"]["origin_group"]
                    and existing["field"] == revision["field"] and existing["value"] != revision["value"]):
                    raise RegistryError("同一source record/hashの内容不一致")
            revision["content_sha256"] = fp
            revision["revision_id"] = "rev-" + fp[:20]
            horse["revisions"].append(revision)
            receipt = atomic_save(self.path(key), horse, expected_blob)
            return {"status": "ADDED", "revision_id": revision["revision_id"], "receipt": receipt}

    def fact(self, horse_key, field, cutoff, mode):
        horse = self.read_horse(horse_key)
        if horse["identity"]["status"] != "RESOLVED":
            return {"status": "IDENTITY_UNRESOLVED"}
        applicable = []
        for r in horse["revisions"]:
            if r["field"] != field:
                continue
            if stamp(r["first_observed_at"]) > cutoff or stamp(r["captured_at"]) > cutoff:
                continue
            if mode == "FORWARD" and stamp(r["saved_at"]) > cutoff:
                continue
            applicable.append(r)
        superseded = {r["previous_revision_id"] for r in applicable if r.get("previous_revision_id")}
        tips = [r for r in applicable if r["revision_id"] not in superseded]
        verified = [r for r in tips if r["verification"] == "VERIFIED"
                    and stamp(r["verification_evidence"]["checked_at"]) <= cutoff]
        unique = {r["value"] for r in verified}
        if len(unique) > 1:
            return {"status": "CONFLICT", "candidates": [
                {"value": r["value"], "revision_id": r["revision_id"], "source": r["source"]}
                for r in verified]}
        if unique:
            selected = min(verified, key=lambda r: (r["first_observed_at"], r["revision_id"]))
            return {"status": "VERIFIED", "value": selected["value"],
                    "revision_id": selected["revision_id"], "sha256": selected["content_sha256"],
                    "source": selected["source"], "first_observed_at": selected["first_observed_at"]}
        return {"status": "UNVERIFIED" if tips else "PARTIAL",
                "candidate_revisions": [r["revision_id"] for r in tips]}

    def follow(self, root_key, path, cutoff, mode):
        position = root_key
        proof = []
        for leg in path:
            item = self.fact(position, "parent.sire" if leg == "S" else "parent.dam", cutoff, mode)
            if item["status"] != "VERIFIED":
                return None, proof, item["status"]
            proof.append({"horse_key": position, "revision_id": item["revision_id"],
                          "sha256": item["sha256"]})
            position = item["value"]
            if not self.path(position).exists():
                return None, proof, "PARTIAL"
        return position, proof, "VERIFIED"

    def contain(self, horse_key, ancestor, depth, cutoff, mode):
        key_check(ancestor)
        require(1 <= depth <= 10, "世代は1〜10に限定")
        found, missing, paths, proof = [], [], [], []
        stack = [("", horse_key)]
        while stack:
            path, item_key = stack.pop()
            if len(path) == depth:
                continue
            for leg, field in (("S", "parent.sire"), ("D", "parent.dam")):
                p = path + leg
                val = self.fact(item_key, field, cutoff, mode)
                if val["status"] != "VERIFIED":
                    missing.append({"path": p, "status": val["status"]})
                    continue
                proof.append({"path": p, "revision_id": val["revision_id"], "sha256": val["sha256"]})
                if val["value"] == ancestor:
                    found.append(p)
                elif not self.path(val["value"]).exists():
                    missing.append({"path": p, "status": "PARTIAL"})
                else:
                    stack.append((p, val["value"]))
        state = "PRESENT" if found else ("UNKNOWN" if missing else "ABSENT_WITHIN_SCOPE")
        return {"status": state, "paths": sorted(found), "unverified_paths": sorted(missing, key=lambda x:x["path"]),
                "scope_depth": depth, "derived_from": proof, "algorithm_version": SCHEMA}

    def line(self, horse_key, name, taxonomy_version, cutoff, mode):
        require(re.fullmatch(r"v[0-9]+(?:_[a-z0-9]+)?", taxonomy_version), "分類版が不正")
        taxonomy = load(self.taxonomies / (taxonomy_version + ".json"))
        require(taxonomy.get("schema_version") == TAXONOMY_SCHEMA and taxonomy.get("version") == taxonomy_version,
                "分類定義の版が不一致")
        founder_keys = taxonomy.get("lines", {}).get(name)
        require(isinstance(founder_keys, list) and founder_keys, "未定義の系統: " + name)
        current = horse_key
        proof = []
        for depth in range(1, 11):
            item = self.fact(current, "parent.sire", cutoff, mode)
            if item["status"] != "VERIFIED":
                return {"status": "UNKNOWN", "derived_from": proof, "taxonomy_version": taxonomy_version,
                        "taxonomy_sha256": hash_object(taxonomy)}
            proof.append({"revision_id": item["revision_id"], "sha256": item["sha256"]})
            current = item["value"]
            if current in founder_keys:
                return {"status": "PRESENT", "generation": depth, "derived_from": proof,
                        "taxonomy_version": taxonomy_version, "taxonomy_sha256": hash_object(taxonomy)}
        return {"status": "UNKNOWN", "derived_from": proof, "taxonomy_version": taxonomy_version,
                "taxonomy_sha256": hash_object(taxonomy)}

    def query(self, request):
        cutoff = stamp(request["data_cutoff"])
        mode = request.get("mode", "FORWARD")
        require(mode in ("FORWARD", "REPLAY"), "modeはFORWARDまたはREPLAY")
        resolved = self.resolve(request["horse"])
        if resolved["status"] != "RESOLVED":
            return {"schema_version": RESEARCH_SCHEMA, "identity": resolved,
                    "reused": {}, "missing": [{"item": "identity", "status": "IDENTITY_UNRESOLVED"}],
                    "external_queries": 0, "data_cutoff": request["data_cutoff"], "mode": mode}
        key = resolved["horse_key"]
        reused, missing = {}, []
        for field in request.get("fields", []):
            require(isinstance(field, str) and re.fullmatch(r"(sire|dam|dam_sire|training_country@[SD]*|breeding_country@[SD]*)", field),
                    "不正な要求項目: " + str(field))
            if field in ("sire", "dam"):
                result = self.fact(key, "parent." + field, cutoff, mode)
            else:
                path = "DS" if field == "dam_sire" else field.split("@", 1)[1]
                target, parents, state = self.follow(key, path, cutoff, mode)
                result = (self.fact(target, "parent.sire" if field == "dam_sire"
                                    else "attribute." + field.split("@")[0], cutoff, mode)
                          if target else {"status": state, "derived_from": parents})
                if target:
                    result = dict(result, derived_from=parents)
            if result["status"] == "VERIFIED":
                reused[field] = result
            else:
                missing.append({"item": field, **result})
        for spec in request.get("contains", []):
            require(isinstance(spec, dict), "contains要素が不正")
            ancestor = spec["ancestor_key"]
            depth = spec.get("depth", request.get("depth", 5))
            result = self.contain(key, ancestor, depth, cutoff, mode)
            tag = "contains:" + ancestor + ":" + str(depth)
            if result["status"] in ("PRESENT", "ABSENT_WITHIN_SCOPE"):
                reused[tag] = result
            else:
                missing.append({"item": tag, **result})
        version = request.get("taxonomy_version")
        for spec in request.get("lines", []):
            require(version, "系統要求にはtaxonomy_versionが必要")
            name = spec["name"]
            path = spec.get("path", "")
            require(re.fullmatch(r"[SD]{0,10}", path), "pathが不正")
            target, parents, state = self.follow(key, path, cutoff, mode)
            result = self.line(target, name, version, cutoff, mode) if target else {"status": state}
            if target:
                result = dict(result, parent_proof=parents)
            tag = "line:" + name + "@" + path
            if result["status"] == "PRESENT":
                reused[tag] = result
            else:
                missing.append({"item": tag, **result})
        return {"schema_version": RESEARCH_SCHEMA, "identity": resolved, "reused": reused,
                "missing": missing, "external_queries": 0,
                "data_cutoff": request["data_cutoff"], "mode": mode}

    def plan(self, payload):
        request_id = key_check(payload["request_id"])
        results = self.query(payload)
        path = self.research / (request_id + ".json")
        with single_writer(self.root):
            guard_head(self.expected_head, self.root)
            previous = load(path, {}) if path.exists() else {}
            require(not previous or previous.get("request") == payload,
                    "同じrequest_idで異なる要求は登録できない")
            research = {"schema_version": RESEARCH_SCHEMA, "request_id": request_id,
                        "request": payload, "result": results,
                        "attempts": previous.get("attempts", []),
                        "created_at": previous.get("created_at", now()),
                        "saved_at": now()}
            receipt = atomic_save(path, research, file_blob_sha(path))
        return {"result": results, "receipt": receipt}

    def attempt(self, payload):
        request_id = key_check(payload["request_id"])
        path = self.research / (request_id + ".json")
        require(payload.get("status") in ERRORS, "失敗はNOT_FOUND/SOURCE_ERRORを区別")
        require(payload.get("source") and payload.get("item"), "出所と要求項目が必要")
        with single_writer(self.root):
            guard_head(self.expected_head, self.root)
            before = file_blob_sha(path)
            record = load(path)
            required = {x["item"] for x in record["result"]["missing"]}
            require(payload["item"] in required, "未充足項目ではない")
            old = [x for x in record["attempts"] if
                   x["item"] == payload["item"] and x["source"] == payload["source"]]
            max_retries = int(payload.get("max_source_error_attempts", 2))
            require(1 <= max_retries <= 10, "再試行回数が範囲外")
            if old:
                last = old[-1]
                if last["status"] == "SOURCE_ERROR":
                    require(len([x for x in old if x["status"] == "SOURCE_ERROR"]) < max_retries,
                            "SOURCE_ERROR再試行上限")
                require(stamp(now()) >= stamp(last["next_retry_at"]), "再試行可能時刻より前")
            delay_hours = int(payload.get("not_found_retry_hours", 24))
            require(1 <= delay_hours <= 720, "NOT_FOUND再試行間隔が範囲外")
            attempted = stamp(now())
            next_retry = attempted + (dt.timedelta(hours=delay_hours) if payload["status"] == "NOT_FOUND"
                                      else dt.timedelta(minutes=5))
            incident = {"item": payload["item"], "source": payload["source"], "status": payload["status"],
                        "detail": payload.get("detail", ""), "attempted_at": attempted.isoformat(),
                        "next_retry_at": next_retry.isoformat()}
            if not old or old[-1] != incident:
                record["attempts"].append(incident)
            record["saved_at"] = now()
            receipt = atomic_save(path, record, before)
            return {"attempt": incident, "receipt": receipt}

    def reindex(self):
        names = {}
        for horse in self.all_horses():
            for name in horse["identity"]["names"]:
                names.setdefault(name.casefold().strip(), []).append(horse["horse_key"])
        output = {"schema_version": SCHEMA, "generated_at": now(),
                  "aliases": {k: sorted(set(v)) for k, v in sorted(names.items())}}
        path = self.root / "aliases.json"
        with single_writer(self.root):
            receipt = atomic_save(path, output, file_blob_sha(path))
            return {"receipt": receipt, "aliases": len(names)}


def command_line(argv=None):
    parser = argparse.ArgumentParser(description="血統調査台帳: 外部取得は実施しない")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1] / "data/pedigree")
    parser.add_argument("--expected-head", help="読み取り時のGit HEAD SHA。変更時は拒否")
    sub = parser.add_subparsers(dest="action", required=True)
    for act in ("register", "add-fact", "query", "plan", "attempt"):
        item = sub.add_parser(act)
        item.add_argument("--input", required=True, type=Path, help="入力JSON")
        if act in ("register", "add-fact"):
            item.add_argument("--expected-blob", required=True, help="元のgit blob SHA。新規はABSENT")
    sub.add_parser("reindex")
    args = parser.parse_args(argv)
    r = Registry(args.root, args.expected_head)
    try:
        if args.action == "reindex":
            result = r.reindex()
        else:
            payload = load(args.input)
            if args.action == "register":
                result = r.register(payload, args.expected_blob)
            elif args.action == "add-fact":
                result = r.add_fact(payload, args.expected_blob)
            elif args.action == "query":
                result = r.query(payload)
            elif args.action == "plan":
                result = r.plan(payload)
            elif args.action == "attempt":
                result = r.attempt(payload)
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except (RegistryError, KeyError, TypeError, OSError) as exc:
        print(json.dumps({"status": "ERROR", "reason": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(command_line())
