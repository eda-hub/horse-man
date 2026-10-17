"""第2・第3から第4の統合正本および10月17日事後台帳の回帰。"""
import copy
import json
import unittest
from pathlib import Path

from cycle04_migration import (ROOT,CARRYOVER,MANIFEST,DAY,SUMMARY,canon,
                               validate_carryover,validate_manifest,validate_postrace,
                               compute_summary,audit)

class Cycle04MigrationTest(unittest.TestCase):
    def test_all_legacy_items_are_mapped_without_reclassifying_kpi(self):
        d=validate_carryover(ROOT)
        self.assertEqual(len(d["items"]),68)
        self.assertEqual(d["historical_pending_kpi_decisions"],57)
        self.assertEqual(d["performance_promotion"],"NOT_APPROVED")

    def test_history_manifest_is_retained_without_premature_deletion(self):
        manifest=validate_manifest(ROOT)
        self.assertGreaterEqual(len(manifest["files"]),12)
        self.assertEqual(sum(x["decision"]=="DELETE_VERIFIED" for x in manifest["files"]),7)
        self.assertTrue(all(not (ROOT/x["path"]).exists() for x in manifest["files"] if x["decision"]=="DELETE_VERIFIED"))

    def test_all_36_are_reconciled_without_forward_certification(self):
        d=validate_postrace(ROOT)
        self.assertEqual(d["races"],36)
        self.assertEqual(d["official_primary"],6)
        self.assertEqual(d["secondary_results"],30)
        self.assertEqual(d["formally_eligible"],0)

    def test_invalid_postrace_scope_and_eligibility_rejected(self):
        day=json.loads((ROOT/DAY).read_text())
        for transform in (
            lambda d:d["initial_scope"].append(d["declared_scope"][0]),
            lambda d:d["races"][0].update(prediction_eligibility="ELIGIBLE"),
            lambda d:d["races"][0].update(canonical_race_id="20261017-TOK-11"),
            lambda d:d["races"][0].update(official_individual_page_verified=True),
            lambda d:d.update(registered_at_jst="2026-10-17T09:00:00+09:00"),
        ):
            bad=copy.deepcopy(day);transform(bad)
            with self.subTest(reason=str(bad)[:40]),self.assertRaises(ValueError):
                validate_postrace(ROOT,bad)

    def test_stored_summary_is_computed_not_claimed(self):
        self.assertEqual(json.loads((ROOT/SUMMARY).read_text()),compute_summary(ROOT))
        report=audit(ROOT)
        self.assertFalse(report["normal_full_cycle_complete"])
        self.assertEqual(len(report["not_registered_dates"]),5)

    def test_identity_normalization_requires_date_venue_and_race(self):
        self.assertEqual(canon("2026-10-17-NIIGATA-11"),"20261017-NII-11")
        with self.assertRaises(ValueError):
            canon("2026-10-18-NIIGATA-11")

if __name__=="__main__":
    unittest.main()
