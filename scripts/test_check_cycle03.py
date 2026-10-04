import json
import tempfile
import unittest
from pathlib import Path

from check_cycle03 import run, summarize, validate_day


def example(date, race):
    empty = {"target_ids": [], "eligible_ids": [], "ineligible_ids": [],
             "pending_ids": [], "evidence_refs": {}, "stake_yen": None,
             "return_yen": None}
    return {
        "cycle_id": "cycle_03", "race_date_jst": date,
        "initial_scope": [race], "validation_candidates": [race],
        "purchase_candidates": [], "final_completed_scope": [],
        "reviewed_scope": [], "unreviewed_scope": [race],
        "kpis": {"production": {**empty, "target_ids": [race],
                                 "pending_ids": [race]},
                 "betting": empty, "shadow": empty},
    }


def fenced(tag, obj):
    return "```" + tag + "\n" + json.dumps(obj, ensure_ascii=False) + "\n```\n"


class LedgerChecks(unittest.TestCase):
    def test_consistent_but_incomplete_cycle(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            records = root / "records"
            records.mkdir()
            day = example("2026-09-26", "race-a")
            (records / "2026-09-26.md").write_text(fenced("cycle03-day-v1", day))
            cycle = root / "cycle_03.md"
            cycle.write_text(fenced("cycle03-summary-v1", summarize({"2026-09-26": day})))
            run(records, cycle, True, False)
            with self.assertRaisesRegex(ValueError, "every scheduled day"):
                run(records, cycle, True, True)

    def test_duplicate_and_stale_summary_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            records = root / "records"
            records.mkdir()
            day = example("2026-09-26", "race-a")
            day["initial_scope"].append("race-a")
            (records / "2026-09-26.md").write_text(fenced("cycle03-day-v1", day))
            cycle = root / "cycle_03.md"
            cycle.write_text("")
            with self.assertRaisesRegex(ValueError, "duplicate"):
                run(records, cycle, True, False)
            day["initial_scope"] = ["race-a"]
            (records / "2026-09-26.md").write_text(fenced("cycle03-day-v1", day))
            cycle.write_text(fenced("cycle03-summary-v1", {"cycle_id": "cycle_03"}))
            with self.assertRaisesRegex(ValueError, "differs"):
                run(records, cycle, True, False)

    def test_no_data_cannot_pass_operational_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "records").mkdir()
            (root / "cycle_03.md").write_text("")
            run(root / "records", root / "cycle_03.md", False, False)
            with self.assertRaisesRegex(ValueError, "no cycle 03"):
                run(root / "records", root / "cycle_03.md", True, False)

    def test_split_contract_can_record_missing_fixed_plan(self):
        day = example("2026-10-04", "race-a")
        empty = {"target_ids": ["race-a"], "eligible_ids": [], "ineligible_ids": ["race-a"],
                 "pending_ids": [], "evidence_refs": {}, "stake_yen": None, "return_yen": None}
        day["purchase_candidates"] = ["race-a"]
        day["kpi_contract"] = "betting-kpi-split-v1"
        day["kpis"]["betting"] = dict(empty)
        day["kpis"]["betting_evidence"] = dict(empty)
        day["kpis"]["betting_rules"] = dict(empty)
        day["fixed_plan_settlement"] = {
            "stake_yen": 0, "return_yen": 0,
            "races": {"race-a": {
                "snapshot_path": None, "snapshot_id": None,
                "stake_yen": 0, "return_yen": 0,
                "source_verification": "INELIGIBLE",
                "missing_fixed_plan": True
            }}
        }
        validate_day(day, Path("2026-10-04.md"))

    def test_missing_fixed_plan_cannot_invent_money_or_snapshot(self):
        day = example("2026-10-04", "race-a")
        empty = {"target_ids": ["race-a"], "eligible_ids": [], "ineligible_ids": ["race-a"],
                 "pending_ids": [], "evidence_refs": {}, "stake_yen": None, "return_yen": None}
        day["purchase_candidates"] = ["race-a"]
        day["kpi_contract"] = "betting-kpi-split-v1"
        day["kpis"]["betting"] = dict(empty)
        day["kpis"]["betting_evidence"] = dict(empty)
        day["kpis"]["betting_rules"] = dict(empty)
        day["fixed_plan_settlement"] = {
            "stake_yen": 10000, "return_yen": 0,
            "races": {"race-a": {
                "snapshot_path": "invented.md", "snapshot_id": "invented",
                "stake_yen": 10000, "return_yen": 0,
                "source_verification": "INELIGIBLE",
                "missing_fixed_plan": True
            }}
        }
        with self.assertRaisesRegex(ValueError, "missing fixed plan"):
            validate_day(day, Path("2026-10-04.md"))


if __name__ == "__main__":
    unittest.main()
