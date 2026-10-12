"""終了総括の欠測・契約境界・原記録保全・保存資料の改変検出を確認する。"""

import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from build_cycle03_review import DEFAULT_REPORT, EXPECTED_DATES, build, main
from check_cycle03 import summarize
from test_check_cycle03 import example, fenced

BASIS = "0520dc25437358df459e7e08219965f9b1e0f732"


def write_inputs(root, days):
    records = root / "docs/validation/records"
    records.mkdir(parents=True, exist_ok=True)
    for key, value in days.items():
        (records / f"{key}.md").write_text(fenced("cycle03-day-v1", value), encoding="utf-8")
    (root / "docs/validation/cycle_03.md").write_text(
        fenced("cycle03-summary-v1", summarize(days)), encoding="utf-8")


def split_day(missing_plan=False):
    day = example("2026-10-04", "split-race")
    day["kpi_contract"] = "betting-kpi-split-v1"
    day["purchase_candidates"] = ["split-race"]
    kpi = {"target_ids": ["split-race"], "eligible_ids": [],
           "ineligible_ids": ["split-race"] if missing_plan else [],
           "pending_ids": [] if missing_plan else ["split-race"],
           "evidence_refs": {}, "stake_yen": None, "return_yen": None}
    for name in ("betting", "betting_rules", "betting_evidence"):
        day["kpis"][name] = copy.deepcopy(kpi)
    race = {"stake_yen": 0 if missing_plan else 10000, "return_yen": 0 if missing_plan else 20000,
            "source_verification": "INELIGIBLE" if missing_plan else "PENDING",
            "snapshot_id": None if missing_plan else "fixed-snapshot",
            "snapshot_path": None if missing_plan else "fixed.md"}
    if missing_plan:
        race["missing_fixed_plan"] = True
    day["fixed_plan_settlement"] = {"stake_yen": race["stake_yen"],
                                    "return_yen": race["return_yen"], "races": {"split-race": race}}
    return day


class CycleReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.days = {"2026-09-26": example("2026-09-26", "race-a")}
        write_inputs(self.root, self.days)

    def report(self, as_of="2026-10-13"):
        return build(self.root, as_of, BASIS)

    def cli(self, *args):
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            return main(["--root", str(self.root), *args])

    def write_report(self):
        return self.cli("--write", "--as-of-date-jst", "2026-10-13", "--basis-commit", BASIS)

    def test_missing_day_with_saved_evidence_is_unknown_not_zero(self):
        path = self.root / "docs/validation/snapshots/2026-09-27.md"
        path.parent.mkdir(parents=True)
        path.write_text("保存済み予想\n", encoding="utf-8")
        r = self.report()
        missing = r["daily"]["2026-09-27"]
        self.assertIsNone(missing["scope_counts"])
        self.assertIsNone(missing["kpis"])
        self.assertEqual(missing["evidence_paths"], [path.relative_to(self.root).as_posix()])
        self.assertEqual(r["collection"]["status"], "INCOMPLETE")
        self.assertEqual(r["period"]["status"], "ENDED")

    def test_complete_dates_with_unreviewed_scope_still_incomplete(self):
        days = {d: example(d, "race-" + d) for d in EXPECTED_DATES}
        write_inputs(self.root, days)
        self.assertEqual(self.report()["collection"]["missing_dates"], [])
        self.assertEqual(self.report()["collection"]["status"], "INCOMPLETE")

    def test_complete_collection_does_not_certify_or_promote_rules(self):
        days = {d: example(d, "race-" + d) for d in EXPECTED_DATES}
        for d in days.values():
            d["reviewed_scope"], d["unreviewed_scope"] = d["initial_scope"], []
        write_inputs(self.root, days)
        r = self.report()
        self.assertEqual(r["collection"]["status"], "REVIEW_REQUIRED")
        self.assertEqual(r["certification"]["stage_transition"], "NOT_PERFORMED")
        self.assertEqual(r["certification"]["evidence_authenticity"], "NOT_REAUTHENTICATED")
        self.assertEqual(r["pending_kpi_decision_count"], 7)

    def test_same_race_across_days_rejected(self):
        self.days["2026-10-03"] = example("2026-10-03", "race-a")
        write_inputs(self.root, self.days)
        with self.assertRaisesRegex(ValueError, "異なる開催日"):
            self.report()

    def test_stale_cycle_summary_rejected(self):
        path = self.root / "docs/validation/cycle_03.md"
        path.write_text(fenced("cycle03-summary-v1", {"cycle_id": "cycle_03"}), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "不一致"):
            self.report()

    def test_split_and_legacy_contracts_stay_separate_reference_is_not_official(self):
        self.days["2026-10-04"] = split_day()
        write_inputs(self.root, self.days)
        r = self.report()
        self.assertEqual(set(r["contract_groups"]), {"LEGACY_UNSPLIT", "betting-kpi-split-v1"})
        self.assertEqual(r["split_fixed_plan_reference"]["reference_return_rate_pct"], 200)
        self.assertEqual(r["split_fixed_plan_reference"]["fixed_plan_ids"], ["split-race"])
        self.assertIsNone(r["kpi_ledger_claims"]["betting"]["ledger_claimed_return_rate_pct"])
        self.assertEqual(r["kpi_ledger_claims"]["betting"]["counts"]["pending_ids"], 1)

    def test_missing_fixed_plan_is_not_a_zero_return_performance_sample(self):
        self.days["2026-10-04"] = split_day(True)
        write_inputs(self.root, self.days)
        ref = self.report()["split_fixed_plan_reference"]
        self.assertEqual(ref["fixed_plan_ids"], [])
        self.assertEqual(ref["missing_fixed_plan_ids"], ["split-race"])
        self.assertIsNone(ref["reference_return_rate_pct"])

    def test_report_tampering_is_detected(self):
        self.assertEqual(self.write_report(), 0)
        output = self.root / DEFAULT_REPORT
        r = json.loads(output.read_text())
        r["scope_totals_recorded_days_only"]["initial"] += 1
        output.write_text(json.dumps(r), encoding="utf-8")
        self.assertEqual(self.cli("--check"), 1)

    def test_raw_source_change_detected_even_when_ledger_unchanged(self):
        self.assertEqual(self.write_report(), 0)
        source = self.root / "docs/validation/records/2026-09-26.md"
        source.write_text(source.read_text() + "\n結果後追補\n", encoding="utf-8")
        self.assertEqual(self.cli("--check"), 1)

    def test_generation_is_deterministic_and_inputs_unchanged(self):
        before = {p: p.read_bytes() for p in self.root.rglob("*.md")}
        self.assertEqual(self.report(), self.report())
        self.assertEqual(self.write_report(), 0)
        self.assertEqual(self.cli("--check"), 0)
        self.assertEqual(before, {p: p.read_bytes() for p in before})

    def test_original_paths_and_symlink_outputs_cannot_be_overwritten(self):
        args = ["--write", "--as-of-date-jst", "2026-10-13", "--basis-commit", BASIS]
        self.assertEqual(self.cli(*args, "--output", "docs/validation/records/2026-09-26.md"), 1)
        link = self.root / "docs/validation/reviews"
        link.symlink_to(self.root / "docs/validation/records", target_is_directory=True)
        self.assertEqual(self.cli(*args), 1)

    def test_require_complete_rejects_before_writing_incomplete_output(self):
        self.assertEqual(self.cli("--write", "--require-complete", "--as-of-date-jst", "2026-10-13",
                                  "--basis-commit", BASIS), 1)
        self.assertFalse((self.root / DEFAULT_REPORT).exists())

    def test_no_implicit_end_or_basis_and_no_empty_data_success(self):
        self.assertEqual(self.report("2026-10-11")["period"]["status"], "IN_PERIOD")
        self.assertEqual(self.report("2026-10-12")["period"]["status"], "LAST_SCHEDULED_DAY")
        self.assertEqual(self.cli("--write"), 1)
        with self.assertRaisesRegex(ValueError, "40桁"):
            build(self.root, "2026-10-13", "main")
        (self.root / "docs/validation/records/2026-09-26.md").unlink()
        with self.assertRaisesRegex(ValueError, "日別台帳がなく"):
            self.report()

    def test_registered_real_report_reproduces_known_collection(self):
        root = Path(__file__).resolve().parents[1]
        saved = json.loads((root / DEFAULT_REPORT).read_text(encoding="utf-8"))
        r = build(root, saved["as_of_date_jst"], saved["basis_commit"])
        self.assertEqual(r, saved)
        self.assertEqual(r["collection"]["missing_dates"], ["2026-09-27"])
        self.assertEqual(r["scope_totals_recorded_days_only"]["initial"], 134)
        self.assertEqual(r["scope_totals_recorded_days_only"]["selected_without_final"], 17)
        self.assertEqual(r["split_fixed_plan_reference"]["return_yen"], 101050)


if __name__ == "__main__":
    unittest.main()
