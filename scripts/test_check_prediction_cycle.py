import json
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
from check_prediction_cycle import CycleValidationError, run


def write(root, rel, content):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def record():
    races = ["r1", "r2", "r3"]
    return {
        "race_date_jst": "2026-10-17",
        "cycle_id": "cycle_04",
        "manual_release": "v1.7.0",
        "initial_scope": races,
        "final_scope": ["r1", "r2"],
        "reviewed_scope": races,
        "kpis": {
            "production": {
                "target_ids": races,
                "eligible_ids": [],
                "ineligible_ids": ["r1", "r2"],
                "pending_ids": ["r3"],
            },
            "shadow": {
                "target_ids": ["r1", "r2"],
                "eligible_ids": [],
                "ineligible_ids": ["r1"],
                "pending_ids": ["r2"],
            },
        },
    }


def save(root, obj):
    fence = "```"
    body = fence + "prediction-day-v2\n" + json.dumps(obj, ensure_ascii=False) + "\n" + fence + "\n"
    return write(root, "docs/validation/records/2026-10-17.md", body)


def write_active_contract(root, effective="2026-10-13"):
    write(root, "docs/manual/README.md", "# manual\n- **現行リリース**: `v1.7.0`\n")
    state = {
        "schema_version": "prediction-contract-state-v1",
        "next_release": "v1.7.0",
        "next_gate_schema": "prediction-compliance-v2",
        "status": "ACTIVE",
        "earliest_race_date": "2026-10-13",
        "effective_race_date": effective,
        "activated_at_jst": "2026-10-12T18:00:00+09:00",
    }
    write(root, "docs/validation/execution-gates/contract-state.json", json.dumps(state))


def write_receipt(root, receipt_id, artifact_id, artifact_path, date="2026-10-17"):
    receipt = {
        "receipt_id": receipt_id,
        "artifact_id": artifact_id,
        "artifact_path": artifact_path,
        "timing_eligibility": "PRE_RACE_ELIGIBLE",
        "artifact_persist_status": "PERSIST_VERIFIED",
        "receipt_persist_status": "RECEIPT_VERIFIED",
        "persist_verified_at_jst": f"{date}T09:56:00+09:00",
        "scheduled_post_time_jst": f"{date}T10:10:00+09:00",
    }
    fence = "```"
    path = root / f"docs/validation/persistence-receipts/{date}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    prior = path.read_text(encoding="utf-8") if path.exists() else ""
    path.write_text(prior + fence + "persistence-receipt-v1\n" + json.dumps(receipt) + "\n" + fence + "\n", encoding="utf-8")


def evidence_ref(artifact_path, artifact_id, date="2026-10-17"):
    return {
        "artifact_path": artifact_path,
        "artifact_id": artifact_id,
        "receipt_path": f"docs/validation/persistence-receipts/{date}.md",
        "receipt_id": artifact_id + "-R01",
        "timing_eligibility": "PRE_RACE_ELIGIBLE",
        "persist_verified_at_jst": f"{date}T09:56:00+09:00",
    }


def write_valid_gate(root, race="r1", production="ELIGIBLE", shadow="ELIGIBLE", date="2026-10-17"):
    ranking = [5, 2, 6, 4]
    probabilities = [
        {"horse_no": 5, "win_probability": 0.22, "top2_probability": 0.39, "top3_probability": 0.53},
        {"horse_no": 2, "win_probability": 0.18, "top2_probability": 0.34, "top3_probability": 0.49},
        {"horse_no": 6, "win_probability": 0.14, "top2_probability": 0.29, "top3_probability": 0.43},
    ]
    evidence_items = [
        {"horse_no": h, "factor": "ability", "fact": f"fact {h}", "source_ref": "test",
         "observed_at_jst": f"{date}T09:40:00+09:00", "direction": "plus", "strength": "medium"}
        for h in ranking[:3]
    ]
    production_obj = {
        "baseline_forecast_id": race + "-P001",
        "ranking": ranking,
        "marks": {"honmei": 5, "taikou": 2, "tanana": 6, "renka": [4]},
        "probabilities": probabilities,
        "prediction_confidence": "B",
        "evidence_items": evidence_items,
        "fixed_at_jst": f"{date}T09:55:00+09:00",
    }
    gate = {
        "schema_version": "prediction-compliance-v2",
        "race_id": race,
        "race_date_jst": date,
        "mode": "FORWARD",
        "working_branch": f"prediction/{date}",
        "manual_release": "v1.7.0",
        "manual_ref_commit": "b" * 40,
        "scheduled_post_time_jst": f"{date}T10:10:00+09:00",
        "data_cutoff": f"{date}T09:50:00+09:00",
        "timing_route": "SNAPSHOT_CANDIDATE",
        "production": production_obj,
        "kpi_eligibility": {"production": production, "shadow": shadow},
        "shadow_items": [],
        "review": {"status": "NOT_STARTED"},
    }
    if production == "ELIGIBLE":
        snapshot_id = race + "-P001-S01"
        artifact_path = f"docs/validation/snapshots/{date}/{snapshot_id}.json"
        snapshot = {
            "schema_version": "prediction-snapshot-v2",
            "snapshot_id": snapshot_id,
            "race_id": race,
            "working_branch": gate["working_branch"],
            "scheduled_post_time_jst": gate["scheduled_post_time_jst"],
            "manual_release": "v1.7.0",
            "manual_ref_commit": "b" * 40,
            "baseline_forecast_id": production_obj["baseline_forecast_id"],
            "data_cutoff": gate["data_cutoff"],
            "ranking": ranking,
            "marks": production_obj["marks"],
            "probabilities": probabilities,
            "prediction_confidence": "B",
            "evidence_items": evidence_items,
            "fixed_at_jst": production_obj["fixed_at_jst"],
        }
        write(root, artifact_path, json.dumps(snapshot))
        write_receipt(root, snapshot_id + "-R01", snapshot_id, artifact_path, date)
        production_obj["evidence_ref"] = evidence_ref(artifact_path, snapshot_id, date)
    if shadow == "ELIGIBLE":
        artifact_id = race + "-SHADOW-S01"
        artifact_path = f"docs/validation/snapshots/{date}/{artifact_id}.txt"
        write(root, artifact_path, "artifact " + artifact_id)
        write_receipt(root, artifact_id + "-R01", artifact_id, artifact_path, date)
        gate["shadow_items"] = [{
            "item_id": "S-01",
            "kpi_eligibility": "ELIGIBLE",
            "evidence_ref": evidence_ref(artifact_path, artifact_id, date),
        }]
    gate_path = f"docs/validation/execution-gates/{date}/{race}.json"
    write(root, gate_path, json.dumps(gate))
    return gate


class PredictionCycleV2Test(unittest.TestCase):
    def root(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        write_active_contract(root)
        return root

    def test_valid_record(self):
        root = self.root()
        save(root, record())
        self.assertEqual(run(root), 1)

    def test_final_must_be_subset_of_initial(self):
        root = self.root()
        obj = record()
        obj["final_scope"].append("outside")
        save(root, obj)
        with self.assertRaisesRegex(CycleValidationError, "final_scope must be subset"):
            run(root)

    def test_reviewed_scope_must_cover_initial(self):
        root = self.root()
        obj = record()
        obj["reviewed_scope"] = ["r1", "r2"]
        save(root, obj)
        with self.assertRaisesRegex(CycleValidationError, "reviewed_scope must equal"):
            run(root)

    def test_kpi_partition_must_cover_target(self):
        root = self.root()
        obj = record()
        obj["kpis"]["production"]["pending_ids"] = []
        save(root, obj)
        with self.assertRaisesRegex(CycleValidationError, "target partition mismatch"):
            run(root)

    def test_kpi_partitions_cannot_overlap(self):
        root = self.root()
        obj = record()
        obj["kpis"]["production"]["ineligible_ids"].append("r3")
        save(root, obj)
        with self.assertRaisesRegex(CycleValidationError, "partitions overlap"):
            run(root)

    def test_market_sidecar_is_optional(self):
        root = self.root()
        save(root, record())
        run(root)

    def test_market_sidecar_partition_is_independent(self):
        root = self.root()
        obj = record()
        obj["market_validation"] = {
            "target_ids": ["r2"],
            "eligible_ids": [],
            "ineligible_ids": [],
            "pending_ids": ["r2"],
        }
        save(root, obj)
        run(root)

    def test_production_eligible_requires_execution_gate(self):
        root = self.root()
        obj = record()
        obj["kpis"]["production"]["eligible_ids"] = ["r1"]
        obj["kpis"]["production"]["ineligible_ids"] = ["r2"]
        save(root, obj)
        with self.assertRaisesRegex(CycleValidationError, "ELIGIBLE production lacks execution gate"):
            run(root)

    def test_shadow_eligible_requires_execution_gate(self):
        root = self.root()
        obj = record()
        obj["kpis"]["shadow"]["eligible_ids"] = ["r1"]
        obj["kpis"]["shadow"]["ineligible_ids"] = []
        save(root, obj)
        with self.assertRaisesRegex(CycleValidationError, "ELIGIBLE shadow lacks execution gate"):
            run(root)

    def test_gate_state_mismatch_rejected(self):
        root = self.root()
        obj = record()
        write_valid_gate(root, "r1", production="PENDING", shadow="INELIGIBLE")
        save(root, obj)
        with self.assertRaisesRegex(CycleValidationError, "gate state mismatch"):
            run(root)

    def test_eligible_production_and_shadow_with_valid_gate_pass(self):
        root = self.root()
        obj = record()
        obj["kpis"]["production"]["eligible_ids"] = ["r1"]
        obj["kpis"]["production"]["ineligible_ids"] = ["r2"]
        obj["kpis"]["shadow"]["eligible_ids"] = ["r1"]
        obj["kpis"]["shadow"]["ineligible_ids"] = []
        write_valid_gate(root, "r1", production="ELIGIBLE", shadow="ELIGIBLE")
        save(root, obj)
        run(root)

    def test_wrong_release_rejected(self):
        root = self.root()
        obj = record()
        obj["manual_release"] = "v1.6.1"
        save(root, obj)
        with self.assertRaisesRegex(CycleValidationError, "manual_release must be v1.7.0"):
            run(root)


if __name__ == "__main__":
    unittest.main()
