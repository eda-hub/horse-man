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

    def test_pre_race_confirmed_claim_must_include_fixed_quote(self):
        review = sample_review()
        review["change_evidence"] = [{"status": "PRE_RACE_CONFIRMED",
                                      "reason": "事前入力を採用"}]
        with self.assertRaisesRegex(ComplianceError, "exact fixed quote"):
            review_status(review)

    def test_legacy_is_readable_but_never_owner_complete(self):
        old = {"error_classification": "不明", "non_degradation": "確認", "next_validation": "次回"}
        self.assertEqual(review_status(old)["state"], "LEGACY_INCOMPLETE")
        self.assertIn("HISTORICAL_REVIEW_SCHEMA", review_status(old)["missing"])

    def test_dead_heat_order_mismatch_uses_feasible_finish_order(self):
        from recommendation import settle
        result = {"race_id": RACE, "race_date_jst": DATE, "status": "OFFICIAL",
                  "source_url": "https://example.invalid/official",
                  "retrieved_at_jst": DATE + "T12:30:00+09:00",
                  "finish_groups": [[1], [2, 3], [4]],
                  "scratched_horses": [], "place_places": 3}
        rec = {"race_id": RACE, "race_date_jst": DATE, "status": "RECOMMENDED",
               "scheduled_post_time_jst": DATE + "T10:10:00+09:00",
               "tickets": [{"type": "EXACTA", "horses": [2, 1]}]}
        self.assertEqual(settle(rec, result)["tickets"][0]["result"], "MISS")
        pos = {1: 1, 2: 2, 3: 2, 4: 4}
        self.assertIn("ORDER_MISMATCH",
                      classify_ticket(rec["tickets"][0], pos, anchor=2))
        self.assertIn("ORDER_MISMATCH",
                      classify_ticket({"type": "TRIFECTA", "horses": [2, 1, 3]},
                                      pos, anchor=2))
        # 境界で同着となった有効券・非順序券まで着順不一致にしない。
        self.assertNotIn("ORDER_MISMATCH",
                         classify_ticket({"type": "EXACTA", "horses": [1, 3]}, pos, 1))
        self.assertNotIn("ORDER_MISMATCH",
                         classify_ticket({"type": "WIDE", "horses": [2, 3]}, pos, 2))

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

    def test_unfilled_draft_preserves_official_result_and_owner_gaps(self):
        entry = self.entry()
        entry["review"] = sample_review("DRAFT")
        for field in ("error_classification", "non_degradation", "next_validation"):
            entry["review"][field] = ""
        entry["review"]["protected_good_parts"] = []
        entry["review"]["protected_good_parts_status"] = "PENDING"
        entry["review"]["protected_good_parts_reason"] = "保護対象の判断待ち"
        entry["review"]["protected_good_parts_required_inputs"] = ["Owner判断"]
        # 全必須項目が空のCOMPLETEは同一の結果でも書込み前に拒否する。
        complete = copy.deepcopy(entry)
        complete["review"]["state"] = "COMPLETE"
        path = self.root / workflow.DIRECTORY / (DATE + ".json")
        original = path.read_bytes()
        with self.assertRaises(ComplianceError):
            workflow.review(self.root, DATE, complete)
        self.assertEqual(path.read_bytes(), original)
        workflow.review(self.root, DATE, entry)
        day, _ = workflow.read_day(self.root, DATE)
        row = day["races"][RACE]
        self.assertNotIn(RACE, day["reviewed_scope"])
        self.assertEqual(row["review"]["error_classification"], "")
        self.assertEqual(row["result_ref"]["artifact_path"], entry["result_path"])
        self.assertEqual(row["result_reconciliation_ref"], entry["result_reconciliation_ref"])
        self.assertEqual(len(row["review_history"]), 1)
        report = workflow.summary(self.root)
        self.assertEqual(report["reviewed_races"], 0)
        self.assertEqual(report["independent_review_metrics"]["unmarked_by_fixed_phase"]["INITIAL"]["coverage"]["eligible_count"], 0)
        self.assertEqual(report["independent_review_metrics"]["initial_final_change_evidence"]["coverage"]["eligible_count"], 0)
        self.assertIn("REVIEW_NOT_COMPLETE",
                      report["independent_review_metrics"]["unmarked_by_fixed_phase"]["INITIAL"]["coverage"]["missing"][f"{DATE}:{RACE}"]["reason"])
        self.assertTrue(any(g["race_id"] == RACE for g in
                            report["completion"]["review_owner_gaps"]))

    def test_each_fixed_phase_requires_forward_eligible_production(self):
        self.case.select()
        self.case.entry["phase"] = "FINAL"
        workflow.record_prediction(self.root, DATE, self.case.entry)
        workflow.review(self.root, DATE, self.entry())
        frozen_day, _ = workflow.read_day(self.root, DATE)
        baseline = independent_metrics(self.root, [frozen_day])
        self.assertEqual(baseline["initial_final_change_evidence"]["coverage"]["included_count"], 1)
        self.assertEqual(baseline["unmarked_by_fixed_phase"]["INITIAL"]["coverage"]["included_count"], 1)
        self.assertEqual(baseline["unmarked_by_fixed_phase"]["FINAL"]["coverage"]["included_count"], 1)
        # 合成されたgateの状態ごとに、本当に集計対象から排除されることを検証。
        for status, mode in (("PENDING", "FORWARD"),
                             ("INELIGIBLE", "FORWARD"),
                             ("INELIGIBLE", "REPLAY")):
            for target in ("INITIAL", "FINAL"):
                with self.subTest(status=status, mode=mode, phase=target):
                    day = copy.deepcopy(frozen_day)
                    row = day["races"][RACE]
                    index = next(i for i, item in enumerate(row["prediction_history"])
                                 if item["phase"] == target)
                    original_gate = self.root / row["prediction_history"][index]["prediction_gate_path"]
                    gate = json.loads(original_gate.read_text())
                    gate["mode"] = mode
                    gate["kpi_eligibility"]["production"] = status
                    if mode == "REPLAY":
                        gate["timing_route"] = "LATE_PRESERVATION"
                    dest = self.root / "synthetic-review-gates" / (target + "-" + status + "-" + mode + ".json")
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_text(json.dumps(gate))
                    row["prediction_history"][index]["prediction_gate_path"] = dest.relative_to(self.root).as_posix()
                    metrics = independent_metrics(self.root, [day])
                    excluded = metrics["unmarked_by_fixed_phase"][target]["coverage"]
                    other = "FINAL" if target == "INITIAL" else "INITIAL"
                    self.assertEqual(excluded["included_count"], 0)
                    self.assertEqual(excluded["eligible_count"], 0)
                    self.assertIn(status if mode == "FORWARD" else "NOT_FORWARD",
                                  excluded["missing"][f"{DATE}:{RACE}"]["reason"])
                    self.assertEqual(metrics["unmarked_by_fixed_phase"][other]["coverage"]["included_count"], 1)
                    change = metrics["initial_final_change_evidence"]["coverage"]
                    self.assertEqual(change["eligible_count"], 0)
                    self.assertEqual(change["included_count"], 0)
                    self.assertIn("PHASE_NOT_FORWARD_ELIGIBLE",
                                  change["missing"][f"{DATE}:{RACE}"]["reason"])
        row_only = copy.deepcopy(frozen_day)
        row_only["races"][RACE]["mode"] = "REPLAY"
        metrics = independent_metrics(self.root, [row_only])
        for phase in ("INITIAL", "FINAL"):
            self.assertEqual(metrics["unmarked_by_fixed_phase"][phase]["coverage"]["eligible_count"], 0)
        self.assertEqual(metrics["initial_final_change_evidence"]["coverage"]["eligible_count"], 0)

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

    def test_fixed_final_recommendation_draft_to_complete_only_then_counts_failures(self):
        # FINAL適格推奨・公式結果は同じ固定原本。回顧の状態だけを改訂する。
        self.case.select()
        self.case.entry["phase"] = "FINAL"
        workflow.record_prediction(self.root, DATE, self.case.entry)
        entry = self.entry()
        entry["review"] = sample_review("DRAFT")
        entry["review"]["error_classification"] = ""
        entry["review"]["protected_good_parts"] = []
        entry["review"]["protected_good_parts_status"] = "PENDING"
        entry["review"]["protected_good_parts_reason"] = "Ownerの評価待ち"
        entry["review"]["protected_good_parts_required_inputs"] = ["Ownerの完了判断"]
        workflow.review(self.root, DATE, entry)

        day, _ = workflow.read_day(self.root, DATE)
        row = day["races"][RACE]
        self.assertEqual(row["review"]["state"], "DRAFT")
        self.assertEqual(day["reviewed_scope"], [])
        self.assertEqual(row["recommendation_state"], "RECOMMENDED")
        self.assertIn(RACE, day["kpis"]["recommendation"]["eligible_ids"])
        self.assertEqual(row["recommendation_result"]["status"], "SETTLED")
        self.assertTrue(any(t["result"] != "INVALID"
                            for t in row["recommendation_result"]["tickets"]))
        original_result = copy.deepcopy(row["result_ref"])
        original_manifest = copy.deepcopy(row["result_reconciliation_ref"])
        original_settlement = copy.deepcopy(row["recommendation_result"])
        first_revision = copy.deepcopy(row["review_history"][0])
        before = workflow.summary(self.root)["independent_review_metrics"]["recommendation_failure_classification"]
        self.assertEqual(before["coverage"]["target_ids"], [f"{DATE}:{RACE}"])
        self.assertEqual(before["coverage"]["eligible_count"], 0)
        self.assertEqual(before["coverage"]["included_count"], 0)
        self.assertEqual(before["unique_races"], 0)
        self.assertEqual(before["unique_tickets"], 0)
        self.assertEqual(before["miss_tickets"], 0)
        self.assertEqual(before["label_counts"], {})
        self.assertEqual(before["labeled_tickets"], [])
        self.assertIsNone(before["miss_ticket_rate"])
        self.assertEqual(before["coverage"]["missing"][f"{DATE}:{RACE}"],
                         {"reason": "REVIEW_NOT_COMPLETE",
                          "required_inputs": ["completed_review"]})

        # 同じ公式結果・FINAL推奨に対し、独立した改訂原本を経由してCOMPLETEへ。
        entry["review"] = sample_review("COMPLETE")
        with self.assertRaisesRegex(ComplianceError, "explicit correction history"):
            workflow.review(self.root, DATE, entry)
        revision = {"schema_version": "cycle04-review-revision-v1",
                    "race_date_jst": DATE, "race_id": RACE, "revision": 2,
                    "supersedes_sha256": first_revision["sha256"], "review": entry["review"]}
        path = f"docs/validation/review-revisions/{DATE}/{RACE}/2.json"
        dest = self.root / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        raw = (json.dumps(revision, ensure_ascii=False, indent=2) + "\n").encode()
        dest.write_bytes(raw)
        entry["revision_ref"] = {"artifact_path": path, "sha256": hashlib.sha256(raw).hexdigest()}
        workflow.review(self.root, DATE, entry)
        completed_day, _ = workflow.read_day(self.root, DATE)
        completed_row = completed_day["races"][RACE]
        self.assertEqual(completed_day["reviewed_scope"], [RACE])
        self.assertEqual(completed_row["result_ref"], original_result)
        self.assertEqual(completed_row["result_reconciliation_ref"], original_manifest)
        self.assertEqual(completed_row["recommendation_result"], original_settlement)
        self.assertEqual(completed_row["review_history"][0], first_revision)
        self.assertEqual(completed_row["review_history"][1]["previous_sha256"],
                         first_revision["sha256"])
        after = workflow.summary(self.root)["independent_review_metrics"]["recommendation_failure_classification"]
        self.assertEqual(after["coverage"]["target_ids"], before["coverage"]["target_ids"])
        self.assertEqual(after["coverage"]["eligible_count"], 1)
        self.assertEqual(after["coverage"]["included_count"], 1)
        self.assertEqual(after["coverage"]["missing"], {})
        self.assertEqual(after["unique_races"], 1)
        valid = [t for t in original_settlement["tickets"] if t["result"] != "INVALID"]
        misses = [t for t in valid if t["result"] == "MISS"]
        self.assertGreater(len(valid), 0)
        self.assertEqual(after["unique_tickets"], len(valid))
        self.assertEqual(after["miss_tickets"], len(misses))
        self.assertEqual(after["miss_ticket_rate"], len(misses) / len(valid))
        self.assertEqual(len(after["labeled_tickets"]), len(misses))

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
