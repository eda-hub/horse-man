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
                "eligible_ids": ["r1"],
                "ineligible_ids": ["r2"],
                "pending_ids": ["r3"],
            },
            "shadow": {
                "target_ids": ["r1", "r2"],
                "eligible_ids": ["r1"],
                "ineligible_ids": [],
                "pending_ids": ["r2"],
            },
        },
    }


def save(root, obj):
    fence = "```"
    body = fence + "prediction-day-v2\n" + json.dumps(obj, ensure_ascii=False) + "\n" + fence + "\n"
    return write(root, "docs/validation/records/2026-10-17.md", body)


class PredictionCycleV2Test(unittest.TestCase):
    def root(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        return Path(temp.name)

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
        obj["kpis"]["production"]["ineligible_ids"].append("r1")
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

    def test_wrong_release_rejected(self):
        root = self.root()
        obj = record()
        obj["manual_release"] = "v1.6.1"
        save(root, obj)
        with self.assertRaisesRegex(CycleValidationError, "manual_release must be v1.7.0"):
            run(root)


if __name__ == "__main__":
    unittest.main()
