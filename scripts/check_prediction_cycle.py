#!/usr/bin/env python3
import json
import re
import sys
from pathlib import Path

from check_prediction_compliance import NEXT_RELEASE, NEXT_SCHEMA, ComplianceError, validate_gate

RELEASE = NEXT_RELEASE
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


def load_next_gates(root):
    gate_dir = root / "docs/validation/execution-gates"
    gates = {}
    if not gate_dir.exists():
        return gates
    for path in sorted(gate_dir.glob("*/*.json")):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise CycleValidationError(f"{path}: invalid gate JSON") from exc
        if raw.get("manual_release") != RELEASE or raw.get("schema_version") != NEXT_SCHEMA:
            continue
        try:
            gate = validate_gate(root, path)
        except ComplianceError as exc:
            raise CycleValidationError(str(exc)) from exc
        key = (gate["race_date_jst"], gate["race_id"])
        if key in gates:
            raise CycleValidationError(f"duplicate next-contract gate: {key}")
        gates[key] = gate
    return gates



def load_recommendation_gates(root):
    from recommendation import verify
    directory = root / "docs/validation/recommendation-gates"
    gates = {}
    for path in sorted(directory.glob("*/*.json")):
        try:
            rec = verify(root, path)
            gate = json.loads(path.read_text(encoding="utf-8"))
        except (ComplianceError, OSError, ValueError, TypeError, KeyError) as exc:
            raise CycleValidationError(f"{path}: invalid recommendation gate: {exc}") from exc
        key = (rec["race_date_jst"], rec["race_id"])
        if key in gates:
            raise CycleValidationError(f"{path}: duplicate recommendation gate for {key}")
        gates[key] = gate
    return gates


def validate_recommendation_day(record, path, recommendation_gates, effective):
    """正式有効日より前の既存v2台帳には新項目を要求しない。"""
    if not effective or record["race_date_jst"] < effective:
        return
    final = string_set(record["final_scope"], str(path) + "/final_scope")
    section = record.get("recommendations")
    if not isinstance(section, dict):
        raise CycleValidationError(f"{path}: recommendations status partition required")
    names = {
        "RECOMMENDED": "recommended_ids",
        "NO_RECOMMENDATION": "no_recommendation_ids",
        "EXPLICIT_MARKS_ONLY": "marks_only_ids",
        "PENDING": "pending_ids",
    }
    partitions = {state: string_set(section.get(key), f"{path}/recommendations/{key}")
                  for state, key in names.items()}
    for state, ids in partitions.items():
        for other, others in partitions.items():
            if state != other and ids & others:
                raise CycleValidationError(f"{path}: overlapping recommendation status")
    if set().union(*partitions.values()) != final:
        raise CycleValidationError(f"{path}: recommendation status scope mismatch")
    for state, races in partitions.items():
        for race in races:
            gate = recommendation_gates.get((record["race_date_jst"], race))
            if gate is None:
                if state != "PENDING":
                    raise CycleValidationError(f"{path}: missing recommendation gate for {race}")
                continue
            if gate["status"] != state:
                raise CycleValidationError(f"{path}: recommendation status/gate mismatch for {race}")
    kpi = record.get("kpis", {}).get("recommendation")
    if not isinstance(kpi, dict):
        raise CycleValidationError(f"{path}: recommendation KPI required")
    validate_kpi(kpi, final, f"{path}/recommendation")
    eligible_scope = partitions["RECOMMENDED"]
    if string_set(kpi.get("target_ids"), f"{path}/recommendation/target_ids") != eligible_scope:
        raise CycleValidationError(f"{path}: recommendation KPI target must equal RECOMMENDED scope")
    for race in eligible_scope:
        gate = recommendation_gates.get((record["race_date_jst"], race))
        expected = expected_state(kpi, race)
        if gate is None:
            if expected != "PENDING":
                raise CycleValidationError(f"{path}: recommendation KPI requires gate for {race}")
            continue
        if expected != gate["kpi_eligibility"]:
            raise CycleValidationError(f"{path}: recommendation KPI/gate mismatch for {race}")

def expected_state(kpi, race):
    if race in kpi.get("eligible_ids", []):
        return "ELIGIBLE"
    if race in kpi.get("ineligible_ids", []):
        return "INELIGIBLE"
    if race in kpi.get("pending_ids", []):
        return "PENDING"
    return None


def validate_gate_links(record, path, gates):
    race_date = record["race_date_jst"]
    for layer in ("production", "shadow"):
        kpi = record["kpis"][layer]
        for race in kpi.get("target_ids", []):
            expected = expected_state(kpi, race)
            gate = gates.get((race_date, race))
            if gate is None:
                if expected == "ELIGIBLE":
                    raise CycleValidationError(
                        f"{path}: ELIGIBLE {layer} lacks execution gate for {race}"
                    )
                continue
            actual = gate.get("kpi_eligibility", {}).get(layer)
            if actual != expected:
                raise CycleValidationError(
                    f"{path}: {race}/{layer} gate state mismatch: ledger={expected} gate={actual}"
                )

def validate_day(record, path, gates=None, recommendation_gates=None, recommendation_effective=None):
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
    if gates is not None:
        validate_gate_links(record, path, gates)
    validate_recommendation_day(record, path, recommendation_gates or {}, recommendation_effective)
    return record


def run(root=Path(".")):
    records_dir = root / "docs/validation/records"
    gates = load_next_gates(root)
    state_file = root / "docs/validation/execution-gates/contract-state.json"
    state = json.loads(state_file.read_text(encoding="utf-8")) if state_file.is_file() else {}
    effective = (state.get("recommendation_effective_race_date")
                 if state.get("status") == "ACTIVE" else None)
    recommendation_gates = load_recommendation_gates(root)
    count = 0
    seen = set()
    if records_dir.exists():
        for path in sorted(records_dir.glob("*.md")):
            for record in blocks(path, TAG):
                key = (record.get("race_date_jst"), record.get("cycle_id"))
                if key in seen:
                    raise CycleValidationError(f"{path}: duplicate day/cycle record: {key}")
                validate_day(record, path, gates, recommendation_gates, effective)
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
