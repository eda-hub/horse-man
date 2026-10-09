import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from check_prediction_compliance import ComplianceError, validate_gate
from recommendation import (CONTRACT, GATE_SCHEMA, INTENT_SCHEMA, audit, build,
                            settle, ticket_key, validate_snapshot, verify, sha256, display, report, seal)
from test_check_prediction_compliance import (
    add_next_production_snapshot, next_gate, receipt_record,
    write, write_contract_state, write_receipts,
)

DATE = "2026-10-17"
RACE = "20261017-TOK-01"
REC_ID = RACE + "-R001"
POST = DATE + "T10:10:00+09:00"


class RecommendationTest(unittest.TestCase):
    def root(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        write(root, "docs/manual/README.md",
              "# manual\n- **現行リリース**: \x60v1.7.0\x60\n")
        write_contract_state(root, "ACTIVE", "2026-10-13",
                             "2026-10-12T18:00:00+09:00")
        g = next_gate(DATE, RACE)
        g["kpi_eligibility"]["production"] = "ELIGIBLE"
        snapshot = add_next_production_snapshot(root, g)
        write(root, f"docs/validation/execution-gates/{DATE}/{RACE}.json",
              json.dumps(g, ensure_ascii=False))
        return root, g, snapshot

    def scenario(self):
        return {
            "recommendation_id": REC_ID, "race_date_jst": DATE,
            "fixed_at_jst": DATE + "T09:57:00+09:00",
            "reason": "◎と○の同時3着内が展開上自然",
            "joint_top3_scenario": "joint",
            "horse_roles": [
                {"horse_no": h, "finish_role": finish, "source_ref": "test-source",
                 "observed_at_jst": DATE + "T09:40:00+09:00",
                 "scenario_id": "joint", "reason": "先行展開と地力"}
                for h, finish in ((5, "WIN"), (2, "TOP2"))
            ],
            "scenarios": [{"scenario_id": "joint", "description": "同時3着内の展開",
                           "probability_status": "NOT_CALCULATED"}],
            "lower_bound_review": "◎の下側不確実性は認識済み",
            "anchor_failure_scenario": "◎が不利を受ける場合は全損",
        }

    def rec(self, root, pred, scenario=None):
        path = f"docs/validation/snapshots/{DATE}/{pred['snapshot_id']}.json"
        return build(pred, scenario if scenario is not None else self.scenario(), path, root=root)

    def artifacts(self, root, g, pred, rec=None):
        rec = rec if rec is not None else self.rec(root, pred)
        art = f"docs/validation/recommendations/{DATE}/{REC_ID}.json"
        write(root, art, json.dumps(rec, ensure_ascii=False))
        prediction_intent_path = f"docs/validation/persistence-intents/{DATE}/first.json"
        original = {
            "schema_version": "prediction-persistence-intent-v1", "race_date_jst": DATE,
            "working_branch": f"prediction/{DATE}", "snapshot_id": pred["snapshot_id"],
            "required_race_ids": [RACE], "deadline_jst": POST,
            "artifact_path": rec["prediction_ref"]["artifact_path"],
            "recommendation_scope": {
                "race_id": RACE, "recommendation_id": REC_ID, "artifact_path": art,
            },
        }
        write(root, prediction_intent_path, json.dumps(original, ensure_ascii=False))
        intent = {
            "prediction_intent_path": prediction_intent_path,
            "schema_version": INTENT_SCHEMA, "race_date_jst": DATE,
            "race_id": RACE, "recommendation_id": REC_ID,
            "artifact_path": art, "prediction_ref": rec["prediction_ref"],
            "deadline_jst": POST,
        }
        intent_path = f"docs/validation/recommendation-intents/{DATE}/final.json"
        write(root, intent_path, json.dumps(intent, ensure_ascii=False))
        receipt_rel = f"docs/validation/persistence-receipts/{DATE}.md"
        prior = (root / receipt_rel).read_text(encoding="utf-8")
        receipt_id = REC_ID + "-RECEIPT"
        receipt = receipt_record(receipt_id, REC_ID, art,
                                 verified=DATE + "T09:59:00+09:00", post=POST)
        receipt["receipt_verified_at_jst"] = DATE + "T10:00:00+09:00"
        receipt["content_sha256"] = sha256(root / art)
        fence = "\x60\x60\x60"
        write(root, receipt_rel, prior + fence + "persistence-receipt-v1\n" +
              json.dumps(receipt, ensure_ascii=False) + "\n" + fence + "\n")
        proof_rel = f"docs/validation/recommendation-prediction-gates/{DATE}/{REC_ID}.json"
        prod_rel = f"docs/validation/execution-gates/{DATE}/{RACE}.json"
        write(root, proof_rel, (root / prod_rel).read_text(encoding="utf-8"))
        gate = {
            "prediction_gate_ref": {"artifact_path": proof_rel, "sha256": sha256(root / proof_rel)},
            "schema_version": GATE_SCHEMA, "race_id": RACE, "race_date_jst": DATE,
            "recommendation_id": REC_ID, "status": rec["status"],
            "prediction_ref": rec["prediction_ref"], "content_sha256": sha256(root / art),
            "intent_path": intent_path, "mode": "FORWARD",
            "kpi_eligibility": "ELIGIBLE" if rec["status"] == "RECOMMENDED" else "INELIGIBLE",
            "evidence_ref": {
                "artifact_id": REC_ID, "artifact_path": art,
                "receipt_path": receipt_rel, "receipt_id": receipt_id,
                "timing_eligibility": "PRE_RACE_ELIGIBLE",
                "persist_verified_at_jst": receipt["persist_verified_at_jst"],
            },
        }
        gate_path = f"docs/validation/recommendation-gates/{DATE}/{RACE}.json"
        write(root, gate_path, json.dumps(gate, ensure_ascii=False))
        return gate_path, art

    def test_01_end_to_end_odds_free(self):
        root, g, pred = self.root()
        gate_path, _ = self.artifacts(root, g, pred)
        self.assertEqual(verify(root, root / gate_path)["status"], "RECOMMENDED")
        self.assertTrue(audit(root))
        self.assertTrue(settle(self.rec(root, pred), {
            "race_id": RACE, "race_date_jst": DATE, "status": "OFFICIAL", "finish_groups": [[5], [2], [6], [4]],
            "scratched_horses": [], "place_places": 3,
            "source_url": "https://example.invalid/official",
            "retrieved_at_jst": DATE + "T12:30:00+09:00",
        })["race_hit"])

    def test_02_odds_change_does_not_change_recommendation(self):
        root, _, pred = self.root()
        self.assertEqual(self.rec(root, pred), self.rec(root, pred))
        changed = self.scenario()
        changed["odds"] = 400.0
        self.assertEqual(self.rec(root, pred), self.rec(root, pred, changed))
        bad = self.rec(root, pred)
        bad["odds"] = 400.0
        with self.assertRaisesRegex(ComplianceError, "forbidden"):
            validate_snapshot(root, bad)

    def test_03_pair_requires_anchor_and_main_pair(self):
        root, _, pred = self.root()
        rec = self.rec(root, pred)
        rec["tickets"][0]["horses"] = [2, 6]
        with self.assertRaisesRegex(ComplianceError, "non-anchor"):
            validate_snapshot(root, rec)

    def test_04_third_only_horse_cannot_enter_quinella(self):
        root, _, pred = self.root()
        scenario = self.scenario()
        scenario.pop("joint_top3_scenario")
        scenario["joint_top2_scenario"] = "joint"
        scenario["horse_roles"][1]["finish_role"] = "TOP3"
        no_rec = self.rec(root, pred, scenario)
        self.assertEqual(no_rec["status"], "NO_RECOMMENDATION")
        validate_snapshot(root, no_rec)

    def test_05_trio_normalization_and_exacta_order(self):
        self.assertEqual(ticket_key({"type": "TRIO", "horses": [5, 2, 6]}),
                         ticket_key({"type": "TRIO", "horses": [6, 5, 2]}))
        self.assertNotEqual(ticket_key({"type": "EXACTA", "horses": [5, 2]}),
                            ticket_key({"type": "EXACTA", "horses": [2, 5]}))

    def test_06_duplicate_count_missing_horse_cancelled(self):
        root, _, pred = self.root()
        rec = self.rec(root, pred)
        for changed, msg in (
            ({"unique_ticket_count": 2}, "count"),
            ({"cancelled_horses": [2]}, "scratched"),
        ):
            bad = copy.deepcopy(rec)
            bad.update(changed)
            with self.assertRaisesRegex(ComplianceError, msg):
                validate_snapshot(root, bad)
        bad = copy.deepcopy(rec)
        bad["tickets"][0]["horses"] = [5, 99]
        with self.assertRaises(ComplianceError):
            validate_snapshot(root, bad)

    def test_07_future_evidence_or_missing_scenario_is_rejected(self):
        root, _, pred = self.root()
        rec = self.rec(root, pred)
        rec["horse_roles"][0]["observed_at_jst"] = DATE + "T10:01:00+09:00"
        with self.assertRaisesRegex(ComplianceError, "future"):
            validate_snapshot(root, rec)
        rec = self.rec(root, pred)
        rec["tickets"][0]["scenario_id"] = "nonexistent"
        with self.assertRaisesRegex(ComplianceError, "scenario missing"):
            validate_snapshot(root, rec)

    def test_08_no_recommendation_and_pending_do_not_become_eligible(self):
        root, g, pred = self.root()
        rec = self.rec(root, pred)
        rec["status"] = "NO_RECOMMENDATION"
        rec["reason"] = "同時好走根拠不足"
        rec["tickets"] = []
        rec["main_ticket_types"] = []
        rec["candidate_decisions"] = []
        rec["unique_ticket_count"] = 0
        rec["dependency_audit"]["anchor_dependency"] = "NONE"
        validate_snapshot(root, rec)
        gate_path, _ = self.artifacts(root, g, pred, rec)
        self.assertEqual(verify(root, root / gate_path)["status"], "NO_RECOMMENDATION")
        bad = json.loads((root / gate_path).read_text())
        bad["kpi_eligibility"] = "ELIGIBLE"
        write(root, gate_path, json.dumps(bad))
        with self.assertRaisesRegex(ComplianceError, "only FINAL RECOMMENDED"):
            verify(root, root / gate_path)

    def test_09_hash_and_tamper_or_missing_gate_detected(self):
        root, g, pred = self.root()
        gate_path, art = self.artifacts(root, g, pred)
        (root / art).write_text((root / art).read_text() + " ")
        with self.assertRaisesRegex(ComplianceError, "hash"):
            verify(root, root / gate_path)
        self.assertFalse(audit(root))
        (root / gate_path).unlink()
        self.assertFalse(audit(root))

    def test_10_receipt_late_or_wrong_prediction_ref_fails(self):
        root, g, pred = self.root()
        gate_path, art = self.artifacts(root, g, pred)
        broken = json.loads((root / art).read_text())
        broken["prediction_ref"]["sha256"] = "0" * 64
        write(root, art, json.dumps(broken))
        gate = json.loads((root / gate_path).read_text())
        gate["content_sha256"] = sha256(root / art)
        gate["prediction_ref"] = broken["prediction_ref"]
        write(root, gate_path, json.dumps(gate))
        with self.assertRaisesRegex(ComplianceError, "prediction hash"):
            verify(root, root / gate_path)

    def test_11_settle_tied_scratch_and_pending(self):
        root, _, pred = self.root()
        rec = self.rec(root, pred)
        result = {"race_id": RACE, "race_date_jst": DATE,
                  "status": "OFFICIAL", "finish_groups": [[2, 5], [6], [4]],
                  "place_places": 3, "scratched_horses": [],
                  "source_url": "https://example.invalid/official",
                  "retrieved_at_jst": DATE + "T12:30:00+09:00"}
        self.assertTrue(settle(rec, result)["race_hit"])
        result["scratched_horses"] = [2]
        self.assertEqual(settle(rec, result)["status"], "INVALID")
        self.assertEqual(settle(rec, {"race_id": RACE, "race_date_jst": DATE,
                                      "status": "UNCONFIRMED"})["status"], "PENDING")

    def test_12_old_v2_prediction_stays_valid_without_recommendation(self):
        root, g, pred = self.root()
        path = root / f"docs/validation/execution-gates/{DATE}/{RACE}.json"
        validate_gate(root, path)
        self.assertTrue(audit(root))  # 発効前の既存v2に追加gateを要求しない

    def test_13_effective_date_requires_recommendation_gate(self):
        root, _, _ = self.root()
        state = json.loads((root / "docs/validation/execution-gates/contract-state.json").read_text())
        state["recommendation_effective_race_date"] = "2026-10-17"
        write(root, "docs/validation/execution-gates/contract-state.json", json.dumps(state))
        self.assertFalse(audit(root))


    def test_14_display_matches_saved_ticket(self):
        root, _, pred = self.root()
        rec = self.rec(root, pred)
        self.assertIn("ワイド 5-2", display(rec))
        self.assertIn("1点", display(rec))
        self.assertNotIn("円", display(rec))

    def test_15_report_uses_official_results_not_payout(self):
        root, g, pred = self.root()
        gate_path, art = self.artifacts(root, g, pred)
        result = {
            "race_id": RACE, "race_date_jst": DATE,
            "status": "OFFICIAL", "finish_groups": [[5], [2], [6], [4]],
            "scratched_horses": [], "place_places": 3,
            "source_url": "https://example.invalid/official",
            "retrieved_at_jst": DATE + "T12:30:00+09:00",
        }
        result_path = f"docs/validation/results/{DATE}/{RACE}.json"
        write(root, result_path, json.dumps(result))
        manifest = "docs/validation/results/report.json"
        write(root, manifest, json.dumps({"items": [{"gate_path": gate_path, "result_path": result_path}]}))
        output = report(root, root / manifest)
        self.assertEqual(output["by_type"]["WIDE"]["hit_tickets"], 1)
        self.assertEqual(output["by_type"]["WIDE"]["race_hit_rate"], 1.0)
        self.assertNotIn("roi", output)

    def test_16_reject_result_future_data_or_unverified_source(self):
        root, _, pred = self.root()
        rec = self.rec(root, pred)
        result = {"race_id": RACE, "race_date_jst": DATE,
                  "status": "OFFICIAL", "finish_groups": [[5], [2], [6]],
                  "place_places": 3, "scratched_horses": [],
                  "source_url": "https://example.invalid/results",
                  "retrieved_at_jst": DATE + "T09:00:00+09:00"}
        with self.assertRaisesRegex(ComplianceError, "before start"):
            settle(rec, result)
        result["retrieved_at_jst"] = DATE + "T11:00:00+09:00"
        result["source_url"] = ""
        with self.assertRaisesRegex(ComplianceError, "source_url"):
            settle(rec, result)

    def test_17_explicit_marks_only_and_pending(self):
        root, _, pred = self.root()
        for state in ("EXPLICIT_MARKS_ONLY", "PENDING"):
            scenario = self.scenario()
            scenario["status"] = state
            rec = self.rec(root, pred, scenario)
            self.assertEqual(rec["status"], state)
            self.assertEqual(rec["tickets"], [])
            validate_snapshot(root, rec)
            self.assertEqual(settle(rec, {"race_id": RACE,
                     "race_date_jst": DATE, "status": "OFFICIAL"})["status"], "NOT_APPLICABLE")


    def test_18_seal_revision_archives_previous_gate_without_double_count(self):
        root, g, pred = self.root()
        first_gate, first_path = self.artifacts(root, g, pred)
        prior = self.rec(root, pred)
        later = copy.deepcopy(prior)
        later["recommendation_id"] = REC_ID + "-02"
        later["revision"] = 2
        later["supersedes"] = REC_ID
        later["supersedes_sha256"] = sha256(root / first_path)
        later["fixed_at_jst"] = DATE + "T10:01:00+09:00"
        second_artifact = f"docs/validation/recommendations/{DATE}/{REC_ID}-02.json"
        write(root, second_artifact, json.dumps(later, ensure_ascii=False))
        intent_path = f"docs/validation/recommendation-intents/{DATE}/second.json"
        prediction_intent_path = f"docs/validation/persistence-intents/{DATE}/second.json"
        predeclared = {
            "schema_version": "prediction-persistence-intent-v1", "race_date_jst": DATE,
            "working_branch": f"prediction/{DATE}", "snapshot_id": pred["snapshot_id"],
            "required_race_ids": [RACE], "deadline_jst": POST,
            "artifact_path": later["prediction_ref"]["artifact_path"],
            "recommendation_scope": {
                "race_id": RACE, "recommendation_id": later["recommendation_id"],
                "artifact_path": second_artifact,
            },
        }
        write(root, prediction_intent_path, json.dumps(predeclared))
        intent = {"prediction_intent_path": prediction_intent_path,
                  "schema_version": INTENT_SCHEMA, "race_date_jst": DATE,
                  "race_id": RACE, "recommendation_id": later["recommendation_id"],
                  "artifact_path": second_artifact, "prediction_ref": later["prediction_ref"],
                  "deadline_jst": POST}
        write(root, intent_path, json.dumps(intent))
        rid = later["recommendation_id"] + "-RECEIPT"
        receipt = receipt_record(rid, later["recommendation_id"], second_artifact,
                                 verified=DATE + "T10:02:00+09:00", post=POST)
        receipt["receipt_verified_at_jst"] = DATE + "T10:03:00+09:00"
        receipt["content_sha256"] = sha256(root / second_artifact)
        receipt_path = root / f"docs/validation/persistence-receipts/{DATE}.md"
        fence = "\x60\x60\x60"
        receipt_path.write_text(receipt_path.read_text() +
                                fence + "persistence-receipt-v1\n" +
                                json.dumps(receipt) + "\n" + fence + "\n")
        saved = seal(root, second_artifact, "second", rid)
        self.assertEqual(saved, root / first_gate)
        archive = root / f"docs/validation/recommendation-gates/history/{DATE}/{REC_ID}.json"
        self.assertTrue(archive.is_file())
        self.assertEqual(verify(root, saved)["revision"], 2)
        self.assertEqual(verify(root, archive)["revision"], 1)
        self.assertTrue(audit(root))
        manifest = "docs/validation/results/history-report.json"
        write(root, manifest, json.dumps({"items": [{"gate_path": str(archive.relative_to(root))}]}))
        with self.assertRaisesRegex(ComplianceError, "superseded gate"):
            report(root, root / manifest)



    def test_19_formations_cover_all_seven_types_without_duplication(self):
        root, g, pred = self.root()
        # 選択候補は1〜2券種を入れ替えて各券種を直接生成する。
        scenarios = {
            "scenario_id": "joint", "description": "◎と上位の同時好走",
            "probability_status": "NOT_CALCULATED",
        }
        for kind, columns in {
            "WIN": [[5]], "PLACE": [[5]],
            "QUINELLA": [[5], [2, 6]],
            "WIDE": [[5], [2, 6]],
            "EXACTA": [[5], [2, 6]],
            "TRIO": [[5], [2, 6], [2, 6, 4]],
            "TRIFECTA": [[5], [2, 6], [2, 6, 4]],
        }.items():
            with self.subTest(kind=kind):
                pred2 = copy.deepcopy(pred)
                pred2["evidence_items"].extend([
                    {"horse_no": h, "factor": "ability", "fact": "検証済み",
                     "source_ref": "test-source", "observed_at_jst": DATE + "T09:40:00+09:00",
                     "direction": "plus", "strength": "medium"} for h in (4,)
                ])
                pred_path = f"docs/validation/snapshots/{DATE}/{pred['snapshot_id']}.json"
                write(root, pred_path, json.dumps(pred2))
                plan = self.scenario()
                plan["scenarios"] = [scenarios]
                plan["horse_roles"].extend([
                    {"horse_no": h, "finish_role": role, "source_ref": "test-source",
                     "observed_at_jst": DATE + "T09:40:00+09:00",
                     "scenario_id": "joint", "reason": "今回の着順適性"}
                    for h, role in ((6, "TOP2"), (4, "TOP3"))
                ])
                plan["ticket_formations"] = [
                    {"type": kind, "columns": columns, "scenario_id": "joint",
                     "reason": "能力と展開から成立を説明できる構成", "selected": True}
                ]
                rec = self.rec(root, pred2, plan)
                self.assertEqual(rec["status"], "RECOMMENDED")
                self.assertEqual(rec["main_ticket_types"], [kind])
                self.assertEqual(rec["unique_ticket_count"], 1 if len(columns) == 1 else (
                    2 if len(columns) == 2 else (3 if kind == "TRIO" else 4)))
                validate_snapshot(root, rec)

    def test_20_unordered_formations_deduplicate_ordered_do_not(self):
        root, _, pred = self.root()
        for typ, expected in (("TRIO", 1), ("TRIFECTA", 2)):
            with self.subTest(typ=typ):
                p = copy.deepcopy(pred)
                p["evidence_items"].append(
                    {"horse_no": 4, "factor": "ability", "fact": "適性あり",
                     "source_ref": "test-source", "observed_at_jst": DATE + "T09:40:00+09:00",
                     "direction": "plus", "strength": "medium"})
                pred_path = f"docs/validation/snapshots/{DATE}/{p['snapshot_id']}.json"
                write(root, pred_path, json.dumps(p))
                a = self.scenario()
                a["horse_roles"].extend([
                    {"horse_no": h, "finish_role": role, "source_ref": "test-source",
                     "observed_at_jst": DATE + "T09:40:00+09:00",
                     "scenario_id": "joint", "reason": "同時好走"}
                    for h, role in ((6, "TOP2"), (4, "TOP3"))])
                a["ticket_formations"] = [
                    {"type": typ, "columns": [[5], [2, 6], [2, 6]],
                     "scenario_id": "joint", "reason": "上位3頭内を評価", "selected": True}]
                rec = self.rec(root, p, a)
                # 重複列内の同一馬を除去。三連単は逆順を別券とする。
                self.assertEqual(rec["unique_ticket_count"], expected)
                validate_snapshot(root, rec)

    def test_21_formations_reject_three_types_and_non_anchor(self):
        root, _, pred = self.root()
        a = self.scenario()
        a["ticket_formations"] = [
            {"type": typ, "columns": [[h]], "scenario_id": "joint",
             "reason": "構成を検討", "selected": True}
            for typ, h in (("WIN", 5), ("PLACE", 5))]
        a["ticket_formations"].append(
            {"type": "WIDE", "columns": [[5], [2]], "scenario_id": "joint",
             "reason": "追加", "selected": True})
        with self.assertRaisesRegex(ComplianceError, "at most two"):
            self.rec(root, pred, a)
        a["ticket_formations"] = [
            {"type": "WIDE", "columns": [[2], [5]], "scenario_id": "joint",
             "reason": "非◎起点", "selected": True}]
        self.assertEqual(self.rec(root, pred, a)["unique_ticket_count"], 1)


    def test_22_missing_prediction_predeclaration_fails_recommendation_gate(self):
        root, g, pred = self.root()
        gate_path, art = self.artifacts(root, g, pred)
        intent_path = root / f"docs/validation/recommendation-intents/{DATE}/final.json"
        intent = json.loads(intent_path.read_text(encoding="utf-8"))
        original_path = root / intent["prediction_intent_path"]
        original_path.unlink()
        with self.assertRaisesRegex(ComplianceError, "prediction predeclaration missing"):
            verify(root, root / gate_path)
        self.assertFalse(audit(root))

    def test_23_prediction_predeclaration_cannot_swap_ticket_scope(self):
        root, g, pred = self.root()
        gate_path, art = self.artifacts(root, g, pred)
        intent_path = root / f"docs/validation/recommendation-intents/{DATE}/final.json"
        intent = json.loads(intent_path.read_text(encoding="utf-8"))
        original_path = root / intent["prediction_intent_path"]
        original = json.loads(original_path.read_text(encoding="utf-8"))
        original["recommendation_scope"]["recommendation_id"] = "DIFFERENT"
        write(root, original_path.relative_to(root), json.dumps(original))
        with self.assertRaisesRegex(ComplianceError, "pre-prediction declared scope"):
            verify(root, root / gate_path)



if __name__ == "__main__":
    unittest.main()
