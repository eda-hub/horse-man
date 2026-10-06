#!/usr/bin/env python3
import json
import re
import sys
from pathlib import Path

RELEASE = "v1.7.0"
TAG = "prediction-day-v2"
KPI_STATES = ("eligible_ids", "ineligible_ids", "pending_ids")


class CycleValidationError(ValueError):
    pass


def blocks(path, tag):
    content = path.read_text(encoding="utf-8")
    pattern = r"^```" + re.escape(tag) + r"\s*\n(.*?)\n```\s*$"
    for raw in re.findall(pattern, content, re.M | re.S):
        yield json.loads(raw)


def string_set(value, label):
    if not isinstance(value, list) or any(not isinstance(x, str) or not x for x in value):
        raise CycleValidationError(f"{label}: list of non-empty strings required")
    if len(value) != len(set(value)):
        raise CycleValidationError(f"{label}: duplicate race_id")
    return set(value)


def validate_kpi(kpi, target_scope, label):
    if not isinstance(kpi, dict):
        raise CycleValidationError(f"{label}: KPI object required")
    target = string_set(kpi.get("target_ids", []), label + "/target_ids")
    if not target.issubset(target_scope):
        raise CycleValidationError(f"{label}: target_ids must be within declared scope")
    partitions = {}
    for name in KPI_STATES:
        partitions[name] = string_set(kpi.get(name, []), label + "/" + name)
    for i, left in enumerate(KPI_STATES):
        for right in KPI_STATES[i + 1:]:
            overlap = partitions[left] & partitions[right]
            if overlap:
                raise CycleValidationError(f"{label}: KPI partitions overlap: {sorted(overlap)}")
    classified = set().union(*partitions.values())
    if classified != target:
        missing = target - classified
        extra = classified - target
        raise CycleValidationError(
            f"{label}: target partition mismatch missing={sorted(missing)} extra={sorted(extra)}"
        )


def validate_day(record, path):
    if not isinstance(record, dict):
        raise CycleValidationError(f"{path}: record object required")
    if record.get("manual_release") != RELEASE:
        raise CycleValidationError(f"{path}: manual_release must be {RELEASE}")
    race_date = record.get("race_date_jst")
    if not isinstance(race_date, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", race_date):
        raise CycleValidationError(f"{path}: race_date_jst required")
    cycle_id = record.get("cycle_id")
    if not isinstance(cycle_id, str) or not cycle_id:
        raise CycleValidationError(f"{path}: cycle_id required")

    initial = string_set(record.get("initial_scope", []), f"{path}/initial_scope")
    final = string_set(record.get("final_scope", []), f"{path}/final_scope")
    reviewed = string_set(record.get("reviewed_scope", []), f"{path}/reviewed_scope")
    if not final.issubset(initial):
        raise CycleValidationError(f"{path}: final_scope must be subset of initial_scope")
    if reviewed != initial:
        raise CycleValidationError(f"{path}: reviewed_scope must equal initial_scope")

    kpis = record.get("kpis")
    if not isinstance(kpis, dict) or "production" not in kpis or "shadow" not in kpis:
        raise CycleValidationError(f"{path}: production/shadow KPI objects required")
    validate_kpi(kpis["production"], initial, f"{path}/production")
    validate_kpi(kpis["shadow"], final, f"{path}/shadow")

    market = record.get("market_validation")
    if market is not None:
        validate_kpi(market, initial, f"{path}/market_validation")
    return record


def run(root=Path(".")):
    records_dir = root / "docs/validation/records"
    count = 0
    seen = set()
    if records_dir.exists():
        for path in sorted(records_dir.glob("*.md")):
            for record in blocks(path, TAG):
                key = (record.get("race_date_jst"), record.get("cycle_id"))
                if key in seen:
                    raise CycleValidationError(f"{path}: duplicate day/cycle record: {key}")
                validate_day(record, path)
                seen.add(key)
                count += 1
    print(f"PREDICTION_CYCLE_V2_OK: {count} day record(s) validated")
    return count


def main():
    try:
        run()
    except (CycleValidationError, json.JSONDecodeError, OSError) as exc:
        print(f"NON_COMPLIANT: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
