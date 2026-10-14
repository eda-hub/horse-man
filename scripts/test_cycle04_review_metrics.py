"""PR88 回顧Owner境界・履歴保全・独立分類の合成回帰。"""
import copy
import hashlib
import json
import unittest

from cycle04_review_metrics import (review_status, classify_ticket, REVIEW_SCHEMA,
                                    review_hash, independent_metrics)
from check_prediction_compliance import ComplianceError
from test_cycle04_result_eligibility import sample_review
import cycle04_workflow as workflow
import test_cycle04_workflow as fixtures
from test_recommendation import DATE, RACE


class OwnerSchema(unittest.TestCase):
    def test_three_owner_lists_require_states_reasons_and_absent_reason(self):
        good = sample_review()
        self.assertEqual(review_status(good)["state"], "COMPLETE")
        for name in ("protected_good_parts", "revalidation_targets", "improvement_targets"):
            with self.subTest(name=name):
                malformed = copy.deepcopy(good)
                malformed[name + "_reason"] = ""
                with self.assertRaisesRegex(ComplianceError, "state/reason"):
                    review_status(malformed)
                malformed = copy.deepcopy(good)
                malformed[name + "_status"] = "NOT_APPLICABLE"
                malformed[name] = []
                malformed[name + "_reason"] = "確認対象なし"
                review_status(malformed)

    def test_pending_inputs_are_explicit_and_cannot_claim_complete(self):
        value = sample_review()
        value["state"] = "DRAFT"
        value["protected_good_parts"] = []
        value["protected_good_parts_status"] = "PENDING"
        value["protected_good_parts_reason"] = "結果未確認"
        value["protected_good_parts_required_inputs"] = ["公式全頭結果"]
        self.assertIn("protected_good_parts:PENDING", review_status(value)["missing"])
        value["state"] = "COMPLETE"
        with self.assertRaisesRegex(ComplianceError, "COMPLETE review"):
            review_status(value)

    def test_legacy_is_readable_but_never_owner_complete(self):
        old = {"error_classification": "不明", "non_degradation": "確認", "next_validation": "次回"}
        self.assertEqual(review_status(old)["state"], "LEGACY_INCOMPLETE")
        self.assertIn("HISTORICAL_REVIEW_SCHEMA", review_status(old)["missing"])

    def test_multiple_failure_labels_have_no_deduped_denominator(self):
        # 軸5が3着内外かつ相手4も3着内外となる複数原因。
        pos = {1: 1, 2: 2, 3: 3, 4: 4, 5: 5}
        labels = classify_ticket({"type": "TRIO", "horses": [1, 2, 5]}, pos, 5)
        self.assertIn("AXIS_COLLAPSE", labels)
        self.assertIn("THIRD_HORSE_MISSING", labels)
        self.assertIn("OPPONENT_MISSING", labels)
        self.assertIn("ORDER_MISMATCH",
                      classify_ticket({"type": "EXACTA", "horses": [2, 1]}, pos, 2))


class OwnerWorkflow(unittest.TestCase):
    def setUp(self):
        self.case = fixtures.OperationalWorkflow()
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.root = self.case.root
        self.case.register()
        workflow.record_prediction(self.root, DATE, self.case.entry)

    def entry(self):
        return self.case.result_entry()

    def test_draft_keeps_result_but_never_claims_review_completed(self):
        entry = self.entry()
        entry["review"] = sample_review("DRAFT")
        entry["review"]["protected_good_parts"] = []
        entry["review"]["protected_good_parts_status"] = "PENDING"
        entry["review"]["protected_good_parts_reason"] = "追跡中"
        entry["review"]["protected_good_parts_required_inputs"] = ["Owner判断"]
        workflow.review(self.root, DATE, entry)
        day, _ = workflow.read_day(self.root, DATE)
        self.assertEqual(day["reviewed_scope"], [])
        self.assertTrue(day["races"][RACE]["result_ref"])
        self.assertEqual(day["races"][RACE]["review_history"][0]["revision"], 1)
        self.assertEqual(workflow.summary(self.root)["reviewed_races"], 0)

    def test_draft_to_complete_needs_fixed_revision_and_preserves_original(self):
        entry = self.entry()
        entry["review"] = sample_review("DRAFT")
        workflow.review(self.root, DATE, entry)
        day, _ = workflow.read_day(self.root, DATE)
        original = copy.deepcopy(day["races"][RACE]["review_history"][0])
        entry["review"] = sample_review()
        with self.assertRaisesRegex(ComplianceError, "explicit correction history"):
            workflow.review(self.root, DATE, entry)
        doc = {"schema_version": "cycle04-review-revision-v1",
               "race_date_jst": DATE, "race_id": RACE, "revision": 2,
               "supersedes_sha256": original["sha256"], "review": entry["review"]}
        path = f"docs/validation/review-revisions/{DATE}/{RACE}/2.json"
        dest = self.root / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        raw = (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode()
        dest.write_bytes(raw)
        entry["revision_ref"] = {"artifact_path": path, "sha256": hashlib.sha256(raw).hexdigest()}
        workflow.review(self.root, DATE, entry)
        newday, _ = workflow.read_day(self.root, DATE)
        self.assertEqual(newday["reviewed_scope"], [RACE])
        self.assertEqual(newday["races"][RACE]["review_history"][0], original)
        self.assertEqual(newday["races"][RACE]["review_history"][1]["previous_sha256"],
                         original["sha256"])
        self.assertEqual(review_hash(entry["review"]),
                         newday["races"][RACE]["review_history"][-1]["sha256"])
        dest.write_bytes(b'{"tampered":true}')
        with self.assertRaisesRegex(ComplianceError, "revision artifact hash"):
            workflow.read_day(self.root, DATE)

    def test_unchanged_pair_keeps_anchor_outcome_by_evidence_state(self):
        self.case.select()
        self.case.entry["phase"] = "FINAL"
        workflow.record_prediction(self.root, DATE, self.case.entry)
        workflow.review(self.root, DATE, self.entry())
        metrics = workflow.summary(self.root)["independent_review_metrics"]
        state = metrics["initial_final_change_evidence"]["by_evidence_state"]["UNCHANGED"]
        self.assertEqual(state["count"], 1)
        self.assertEqual(state["unchanged_outcome"], 1)
        self.assertEqual(state["anchor_win_improved"], 0)
        self.assertEqual(state["new_anchor_win_rate"], 1)

    def test_unmarked_and_missing_final_have_separate_coverage(self):
        workflow.review(self.root, DATE, self.entry())
        day, _ = workflow.read_day(self.root, DATE)
        result = independent_metrics(self.root, [day])
        initial = result["unmarked_by_fixed_phase"]["INITIAL"]
        final = result["unmarked_by_fixed_phase"]["FINAL"]
        self.assertEqual(initial["coverage"]["included_count"], 1)
        self.assertEqual(final["coverage"]["included_count"], 0)
        self.assertIn(f"{DATE}:{RACE}", final["coverage"]["missing"])
        self.assertEqual(result["initial_final_change_evidence"]["coverage"]["included_count"], 0)
        self.assertIsNone(result["composite_unmarked_good_run"])


if __name__ == "__main__":
    unittest.main()
