import json
import tempfile
import unittest
from pathlib import Path

from check_cycle03 import run, summarize


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


if __name__ == "__main__":
    unittest.main()
