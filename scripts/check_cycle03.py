#!/usr/bin/env python3
"""Check the machine-readable cycle 03 ledger embedded in Markdown records.

This checks accounting consistency, not whether the cited pre-race evidence is
authentic or timely. Those checks remain part of the manual's readback contract.
"""

import argparse
import json
import re
import sys
from pathlib import Path

DAY_TAG = "cycle03-day-v1"
SUMMARY_TAG = "cycle03-summary-v1"
EXPECTED_DATES = {
    "2026-09-26", "2026-09-27", "2026-10-03", "2026-10-04",
    "2026-10-10", "2026-10-11", "2026-10-12",
}
REQUIRED_KPI_NAMES = {"production", "betting", "shadow"}
ALLOWED_KPI_NAMES = {"production", "betting", "betting_evidence", "shadow"}


def block(path: Path, tag: str):
    text = path.read_text(encoding="utf-8")
    matches = re.findall(r"^```" + re.escape(tag) + r"\s*\n(.*?)\n```\s*$", text, re.M | re.S)
    if len(matches) > 1:
        raise ValueError(f"{path}: {tag} appears more than once")
    if not matches:
        return None
    try:
        return json.loads(matches[0])
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path}: invalid {tag} JSON: {exc}") from exc


def ids(obj, key, label):
    value = obj.get(key)
    if not isinstance(value, list) or any(not isinstance(x, str) or not x for x in value):
        raise ValueError(f"{label}: {key} must be a list of nonempty race IDs")
    if len(value) != len(set(value)):
        raise ValueError(f"{label}: duplicate ID in {key}")
    return set(value)


def money(value, label):
    if value is not None and (type(value) is not int or value < 0):
        raise ValueError(f"{label}: money must be a nonnegative integer or null")
    return value


def validate_day(day, path):
    label = str(path)
    if not isinstance(day, dict) or day.get("cycle_id") != "cycle_03":
        raise ValueError(f"{label}: cycle_id must be cycle_03")
    date = day.get("race_date_jst")
    if date not in EXPECTED_DATES or path.stem != date:
        raise ValueError(f"{label}: race_date_jst must match an enrolled race date and filename")
    initial = ids(day, "initial_scope", label)
    validation = ids(day, "validation_candidates", label)
    purchase = ids(day, "purchase_candidates", label)
    final = ids(day, "final_completed_scope", label)
    reviewed = ids(day, "reviewed_scope", label)
    unreviewed = ids(day, "unreviewed_scope", label)
    if not validation <= initial or not purchase <= initial:
        raise ValueError(f"{label}: selected candidates must belong to initial_scope")
    if not final <= validation | purchase:
        raise ValueError(f"{label}: final_completed_scope contains unselected races")
    if reviewed & unreviewed or reviewed | unreviewed != initial:
        raise ValueError(f"{label}: reviewed and unreviewed must partition initial_scope")
    kpis = day.get("kpis")
    if not isinstance(kpis, dict) or not REQUIRED_KPI_NAMES <= set(kpis) or any(
        not (name in ALLOWED_KPI_NAMES or name.startswith("shadow_")) for name in kpis
    ):
        raise ValueError(
            f"{label}: kpis must include production, betting, shadow; "
            "betting_evidence and additional shadow_* items are allowed"
        )
    for name, kpi in kpis.items():
        if not isinstance(kpi, dict):
            raise ValueError(f"{label}: {name} must be an object")
        scope = ids(kpi, "target_ids", f"{label}/{name}")
        eligible = ids(kpi, "eligible_ids", f"{label}/{name}")
        ineligible = ids(kpi, "ineligible_ids", f"{label}/{name}")
        pending = ids(kpi, "pending_ids", f"{label}/{name}")
        if not scope <= initial:
            raise ValueError(f"{label}/{name}: target IDs outside initial_scope")
        if name in {"betting", "betting_evidence"} and not scope <= purchase:
            raise ValueError(f"{label}/{name}: betting targets must be purchase candidates")
        if any(a & b for a, b in ((eligible, ineligible), (eligible, pending), (ineligible, pending))):
            raise ValueError(f"{label}/{name}: eligibility sets overlap")
        if scope != eligible | ineligible | pending:
            raise ValueError(f"{label}/{name}: eligibility sets do not partition targets")
        refs = kpi.get("evidence_refs")
        if not isinstance(refs, dict) or set(refs) != eligible:
            raise ValueError(f"{label}/{name}: every eligible race needs exactly one evidence reference")
        for race_id, ref in refs.items():
            if not isinstance(ref, dict):
                raise ValueError(f"{label}/{name}/{race_id}: incomplete evidence reference")
            if name == "betting":
                if any(not isinstance(ref.get(key), str) or not ref[key]
                    for key in ("source_type", "source_ref", "working_branch")):
                    raise ValueError(f"{label}/{name}/{race_id}: incomplete betting performance source")
            elif any(not isinstance(ref.get(key), str) or not ref[key]
                for key in ("snapshot_id", "receipt_id", "working_branch")):
                raise ValueError(f"{label}/{name}/{race_id}: incomplete evidence reference")
        stake = money(kpi.get("stake_yen"), f"{label}/{name}/stake_yen")
        returned = money(kpi.get("return_yen"), f"{label}/{name}/return_yen")
        if name != "betting" and (stake is not None or returned is not None):
            raise ValueError(f"{label}/{name}: money belongs only to betting performance")
        if name == "betting" and ((stake is None) != (returned is None)):
            raise ValueError(f"{label}/{name}: stake and return must be both measured or both null")
        if name == "betting" and eligible and (stake is None or stake != 10000 * len(eligible)):
            raise ValueError(f"{label}/{name}: eligible official betting requires 10,000 yen per race")
        if name == "betting" and not eligible and (stake is not None or returned is not None):
            raise ValueError(f"{label}/{name}: do not replace unmeasured ROI with zero")
    return date


def summarize(days):
    totals = {}
    names = set.union(*(set(day["kpis"]) for day in days.values()))
    for name in sorted(names):
        totals[name] = {key: sorted({race for day in days.values() for race in day["kpis"].get(name, {}).get(key, [])})
                        for key in ("target_ids", "eligible_ids", "ineligible_ids", "pending_ids")}
        if name == "betting":
            measured = [day["kpis"][name] for day in days.values() if day["kpis"][name]["eligible_ids"]]
            totals[name]["stake_yen"] = sum(k["stake_yen"] for k in measured) if measured else None
            totals[name]["return_yen"] = sum(k["return_yen"] for k in measured) if measured else None
    return {"cycle_id": "cycle_03", "recorded_dates": sorted(days), "kpis": totals}


def run(records_dir: Path, cycle_file: Path, require_data: bool, require_complete: bool, print_summary: bool = False):
    days = {}
    for path in sorted(records_dir.glob("*.md")):
        day = block(path, DAY_TAG)
        if day is None:
            continue  # Historical cycle 02 records have no cycle 03 ledger.
        date = validate_day(day, path)
        if date in days:
            raise ValueError(f"duplicate day ledger: {date}")
        days[date] = day
    summary = block(cycle_file, SUMMARY_TAG)
    if not days:
        if summary is not None:
            raise ValueError("cycle summary exists without any day ledger")
        if require_data or require_complete:
            raise ValueError("no cycle 03 day ledgers; no operational evidence to validate")
        print("NO_DATA: no cycle 03 day ledger; operational success is unverified")
        return
    all_races = [race for day in days.values() for race in day["initial_scope"]]
    if len(all_races) != len(set(all_races)):
        raise ValueError("the same race is in more than one day ledger")
    expected = summarize(days)
    if print_summary:
        print(f"```{SUMMARY_TAG}\n{json.dumps(expected, ensure_ascii=False, indent=2)}\n```")
        return
    if summary is None:
        raise ValueError("day ledgers exist but cycle summary block is missing")
    if summary != expected:
        raise ValueError("cycle summary differs from day ledgers; recalculate instead of adding old totals")
    if require_complete and set(days) != EXPECTED_DATES:
        raise ValueError("cycle closure requires a ledger for every scheduled day, including no-race days")
    remaining = len(EXPECTED_DATES - set(days))
    pending = sum(len(k["pending_ids"]) for k in summary["kpis"].values())
    print(f"CONSISTENT: {len(days)} day ledgers, {remaining} scheduled dates absent, {pending} KPI decisions pending; evidence authenticity is not checked")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records-dir", type=Path, default=Path("docs/validation/records"))
    parser.add_argument("--cycle-file", type=Path, default=Path("docs/validation/cycle_03.md"))
    parser.add_argument("--require-data", action="store_true")
    parser.add_argument("--require-complete", action="store_true")
    parser.add_argument("--print-summary", action="store_true",
                        help="print the calculated fenced JSON block for review and inclusion in the cycle file")
    args = parser.parse_args()
    try:
        run(args.records_dir, args.cycle_file, args.require_data, args.require_complete, args.print_summary)
    except (ValueError, OSError) as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
