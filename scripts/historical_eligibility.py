#!/usr/bin/env python3
"""発走前証跡を生成しない、Git原本に結び付けた旧KPI訂正overlay。"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys

SCHEMA = "historical-eligibility-correction-v1"
FOLDER = Path("docs/validation/historical-corrections")
SHA = re.compile(r"[0-9a-f]{40}\Z")
STATES = {"ELIGIBLE": 2, "PENDING": 1, "INELIGIBLE": 0}
KPIS = {"production", "betting", "betting_rules", "betting_evidence", "shadow"}

class CorrectionError(ValueError):
    pass

def required(v, label):
    if not isinstance(v, str) or not v.strip():
        raise CorrectionError(f"{label}: nonempty text required")
    return v

def safe_path(v):
    if not isinstance(v, str) or "\\" in v:
        raise CorrectionError("POSIX repository path required")
    p = PurePosixPath(v)
    if p.is_absolute() or ".." in p.parts or str(p) != v or not v.startswith("docs/validation/"):
        raise CorrectionError(f"unsafe evidence path: {v}")
    return v

def timestamp(v):
    try:
        t = datetime.fromisoformat(required(v, "reviewed_at_jst").replace("Z", "+00:00"))
    except ValueError as exc:
        raise CorrectionError("invalid review timestamp") from exc
    if t.tzinfo is None or t.utcoffset() is None or t.astimezone(timezone.utc) > datetime.now(timezone.utc):
        raise CorrectionError("timezone required / future review forbidden")
    return t

def git(root, *args):
    r = subprocess.run(["git", "-C", str(root), *args], capture_output=True, check=False)
    if r.returncode:
        raise CorrectionError("Git original unavailable: " + " ".join(args))
    return r.stdout

def blob(root, ref):
    if not isinstance(ref, dict):
        raise CorrectionError("evidence reference object required")
    commit, path, sha = ref.get("commit_sha"), safe_path(ref.get("path")), ref.get("blob_sha")
    if not isinstance(commit, str) or not SHA.fullmatch(commit) or not isinstance(sha, str) or not SHA.fullmatch(sha):
        raise CorrectionError("full original commit/blob SHA required")
    if git(root, "rev-parse", "--verify", commit + "^{commit}").decode().strip() != commit:
        raise CorrectionError("false original commit")
    if git(root, "rev-parse", commit + ":" + path).decode().strip() != sha:
        raise CorrectionError("original blob hash mismatch")
    data = git(root, "show", commit + ":" + path)
    if not data:
        raise CorrectionError("empty original evidence")
    return data

def state(day, race, kpi):
    k = day.get("kpis", {}).get(kpi, {})
    if race not in k.get("target_ids", []):
        raise CorrectionError(f"{race}/{kpi}: not in KPI scope")
    found = [st for field, st in (("eligible_ids", "ELIGIBLE"),
             ("pending_ids", "PENDING"), ("ineligible_ids", "INELIGIBLE"))
             if race in k.get(field, [])]
    if len(found) != 1:
        raise CorrectionError(f"{race}/{kpi}: invalid KPI partition")
    return found[0]

def read_original(data, race, kpi, expected):
    try:
        text = data.decode("utf-8")
        mark = re.escape(chr(96) * 3 + "cycle03-day-v1")
        blocks = re.findall("^" + mark + r"\s*\n(.*?)\n" + re.escape(chr(96) * 3) + r"\s*$", text, re.M | re.S)
        if len(blocks) != 1:
            raise CorrectionError("historical ledger block missing or duplicate")
        old = json.loads(blocks[0])
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise CorrectionError("historical ledger unreadable") from exc
    if state(old, race, kpi) != expected:
        raise CorrectionError("historical claim differs from overlay")

def load(root, days):
    """Validate all records and their sequential SHA256 chain; return keyed corrections."""
    root = Path(root).resolve()
    folder = root / FOLDER
    if not folder.exists():
        return {}
    if folder.is_symlink() or not folder.is_dir():
        raise CorrectionError("invalid correction folder")
    paths = sorted(folder.glob("*.json"))
    if any(p.is_file() and p not in paths for p in folder.rglob("*")):
        raise CorrectionError("nested/unknown overlay entries forbidden")
    chains = {}
    for path in paths:
        if path.is_symlink():
            raise CorrectionError("overlay symlink forbidden")
        raw = path.read_bytes()
        try:
            o = json.loads(raw)
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise CorrectionError(f"{path}: invalid JSON") from exc
        if not isinstance(o, dict) or o.get("schema_version") != SCHEMA:
            raise CorrectionError(f"{path}: invalid schema")
        ident = required(o.get("correction_id"), "correction_id")
        if path.stem != ident or not re.fullmatch("[A-Za-z0-9_-]+", ident):
            raise CorrectionError("overlay ID/filename mismatch")
        date, race, kpi = (required(o.get(x), x) for x in ("race_date_jst", "race_id", "kpi"))
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date) or race not in days.get(date, {}).get("initial_scope", []):
            raise CorrectionError("another race/date")
        if kpi not in KPIS and not kpi.startswith("shadow_"):
            raise CorrectionError("unknown KPI")
        original = o.get("original")
        if not isinstance(original, dict) or original.get("path") != f"docs/validation/records/{date}.md":
            raise CorrectionError("original ledger path mismatch")
        source_state = state(days[date], race, kpi)
        if original.get("status") != source_state:
            raise CorrectionError("old ledger claim mismatch")
        if o.get("before") not in STATES or o.get("after") not in STATES or STATES[o["before"]] <= STATES[o["after"]]:
            raise CorrectionError("upgrades / no-op corrections forbidden")
        if o["before"] == "INELIGIBLE":
            raise CorrectionError("no waivers for ineligible claims")
        required(o.get("reason"), "reason")
        required(o.get("reviewed_by"), "reviewed_by")
        required(o.get("owner"), "owner")
        reviewed = timestamp(o.get("reviewed_at_jst"))
        affected = o.get("affected_aggregates")
        if (not isinstance(affected, list) or any(not isinstance(x, str) or not x.startswith("cycle03:") for x in affected)
                or f"cycle03:{kpi}" not in affected or len(set(affected)) != len(affected)):
            raise CorrectionError("independent KPI impact required")
        basis = o.get("basis")
        if not isinstance(basis, list) or not basis:
            raise CorrectionError("actual evidence basis required")
        read_original(blob(root, original), race, kpi, source_state)
        for ref in basis:
            required(ref.get("role") if isinstance(ref, dict) else None, "basis role")
            blob(root, ref)
        revision = o.get("revision")
        if type(revision) is not int or revision < 1:
            raise CorrectionError("invalid revision")
        chains.setdefault((date, race, kpi), []).append(
            (revision, o, hashlib.sha256(raw).hexdigest(), reviewed))
    result = {}
    for key, items in chains.items():
        items.sort(key=lambda item: item[0])
        prior_hash = prior_state = prior_time = first_original = None
        for number, (revision, obj, digest, reviewed) in enumerate(items, 1):
            if revision != number or obj.get("previous_record_sha256") != prior_hash:
                raise CorrectionError(f"{key}: revision branch/gap/hash mismatch")
            if number == 1:
                first_original = obj["original"]
                if obj["before"] != first_original["status"]:
                    raise CorrectionError(f"{key}: first revision mismatch")
            elif (obj["original"] != first_original or obj["before"] != prior_state
                  or reviewed <= prior_time):
                raise CorrectionError(f"{key}: correction chain rollback")
            prior_hash, prior_state, prior_time = digest, obj["after"], reviewed
            result[key] = {"original": first_original["status"], "effective": obj["after"],
                           "id": obj["correction_id"], "owner": obj["owner"],
                           "reviewed_by": obj["reviewed_by"], "reason": obj["reason"]}
    return result

def effective(corrections, date, race, kpi, original):
    row = corrections.get((date, race, kpi))
    if row and row["original"] != original:
        raise CorrectionError("original mismatch")
    return row["effective"] if row else original

def days_at(root):
    from check_cycle03 import DAY_TAG, block, validate_day
    days = {}
    for path in sorted((Path(root) / "docs/validation/records").glob("*.md")):
        obj = block(path, DAY_TAG)
        if obj is not None:
            date = validate_day(obj, path)
            if date in days:
                raise CorrectionError("duplicate day")
            days[date] = obj
    return days

def report(days, corrections):
    originals, applied, money = {}, {}, {}
    reference_stake = reference_return = 0
    for date, day in sorted(days.items()):
        originals[date], applied[date] = {}, {}
        for kpi, k in sorted(day["kpis"].items()):
            orig = {x: 0 for x in STATES}
            new = {x: 0 for x in STATES}
            old_eligible, new_eligible = [], []
            for race in k["target_ids"]:
                s = state(day, race, kpi)
                updated = effective(corrections, date, race, kpi, s)
                orig[s] += 1
                new[updated] += 1
                if s == "ELIGIBLE":
                    old_eligible.append(race)
                if updated == "ELIGIBLE":
                    new_eligible.append(race)
            originals[date][kpi], applied[date][kpi] = orig, new
            if kpi == "betting" and day.get("kpi_contract") == "betting-kpi-split-v1":
                settlement = day["fixed_plan_settlement"]
                reference_stake += settlement["stake_yen"]
                reference_return += settlement["return_yen"]
                def measured(races):
                    stake = sum(settlement["races"][r]["stake_yen"] for r in races) if races else None
                    returned = sum(settlement["races"][r]["return_yen"] for r in races) if races else None
                    return {"stake_yen": stake, "return_yen": returned,
                            "roi_pct": round(100 * returned / stake, 6) if stake else None}
                money[date] = {"original_formal": measured(old_eligible),
                               "corrected_formal": measured(new_eligible),
                               "fixed_settlement_reference": {"stake_yen": settlement["stake_yen"],
                                                              "return_yen": settlement["return_yen"]}}
    return {"schema_version": "historical-eligibility-view-v1",
            "original_claim_counts": originals, "corrected_claim_counts": applied,
            "approved_corrections": [{"date": d, "race": r, "kpi": k, **v}
                                      for (d, r, k), v in sorted(corrections.items())],
            "split_betting_performance": money,
            "fixed_settlement_reference_total": {"stake_yen": reference_stake,
                                                 "return_yen": reference_return},
            "certification": "overlay cannot create pre-race evidence; reference settlement is not certified ROI"}

def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    try:
        days = days_at(args.root)
        corrections = load(args.root, days)
        result = report(days, corrections)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"HISTORICAL_OVERLAY_VALID: {len(corrections)} approved KPI corrections")
    except (CorrectionError, OSError, ValueError) as exc:
        print(f"HISTORICAL_OVERLAY_INVALID: {exc}", file=sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
