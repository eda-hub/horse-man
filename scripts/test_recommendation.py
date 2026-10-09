import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from check_prediction_compliance import ComplianceError, validate_gate
from recommendation import (CONTRACT, GATE_SCHEMA, INTENT_SCHEMA, audit, build,
                            settle, ticket_key, validate_snapshot, verify, sha256)
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
        intent = {
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
        fence = "\x60\x60\x60"
        write(root, receipt_rel, prior + fence + "persistence-receipt-v1\n" +
              json.dumps(receipt, ensure_ascii=False) + "\n" + fence + "\n")
        gate = {
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
            "status": "OFFICIAL", "finish_groups": [[5], [2], [6], [4]],
            "scratched_horses": [], "place_places": 3,
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
        result = {"status": "OFFICIAL", "finish_groups": [[2, 5], [6], [4]],
                  "place_places": 3, "scratched_horses": []}
        self.assertTrue(settle(rec, result)["race_hit"])
        result["scratched_horses"] = [2]
        self.assertEqual(settle(rec, result)["status"], "INVALID")
        self.assertEqual(settle(rec, {"status": "UNCONFIRMED"})["status"], "PENDING")

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


if __name__ == "__main__":
    unittest.main()
