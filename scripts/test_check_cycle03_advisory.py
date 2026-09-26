import unittest

from check_cycle03_advisory import inspect


def day():
    return {
        "initial_scope": ["race-a", "race-b"],
        "validation_candidates": ["race-a"],
        "purchase_candidates": ["race-b"],
        "final_completed_scope": ["race-a"],
        "kpis": {
            "shadow": {
                "ineligible_ids": ["race-a"],
                "pending_ids": [],
            }
        },
    }


class AdvisoryChecks(unittest.TestCase):
    def test_missing_final_is_reported(self):
        warnings = inspect(day(), "", "", "")
        pairs = {(item["code"], item["race_id"]) for item in warnings}
        self.assertIn(("FINAL_NOT_COMPLETED", "race-b"), pairs)

    def test_missing_baseline_probability_candidate_and_receipt_are_reported(self):
        snapshot = """## race-a final
race_id: race-a
snapshot_id: snap-a
baseline_forecast_id: MISSING_IN_INITIAL_SNAPSHOT
candidate_class: validation_only
勝率 / 連対率 / 3着内率: UNAVAILABLE
"""
        warnings = inspect(day(), snapshot, "", "")
        pairs = {(item["code"], item["race_id"]) for item in warnings}
        self.assertIn(("BASELINE_ID_MISSING", "race-a"), pairs)
        self.assertIn(("PROBABILITY_EVIDENCE_MISSING", "race-a"), pairs)
        self.assertIn(("PRE_RACE_RECEIPT_MISSING", "race-a"), pairs)
        self.assertIn(("CANDIDATE_CLASS_MISSING", "race-b"), pairs)

    def test_verified_prerace_receipt_clears_receipt_warning(self):
        snapshot = """## race-a initial/final
race_id: race-a
snapshot_id: snap-a
baseline_forecast_id: base-a
candidate_class: validation_only
推定確率（勝率/連対率/3着内率）: 20% / 35% / 50%
"""
        receipt = """## persistence_receipt
artifact_id: snap-a
receipt_persist_status: RECEIPT_VERIFIED
timing_eligibility: PRE_RACE_ELIGIBLE
"""
        warnings = inspect(day(), snapshot, receipt, "")
        pairs = {(item["code"], item["race_id"]) for item in warnings}
        self.assertNotIn(("PRE_RACE_RECEIPT_MISSING", "race-a"), pairs)

    def test_late_preservation_is_explicitly_reported(self):
        preservation = """## race-a preservation
race_id: race-a
preservation_id: late-a
baseline_forecast_id: MISSING_IN_INITIAL_SNAPSHOT
candidate_class: validation_only
timing_eligibility: LATE_PRESERVATION
"""
        warnings = inspect(day(), "", "", preservation)
        pairs = {(item["code"], item["race_id"]) for item in warnings}
        self.assertIn(("LATE_PRESERVATION", "race-a"), pairs)
        self.assertIn(("PRE_RACE_RECEIPT_MISSING", "race-a"), pairs)

    def test_shadow_ineligible_is_reported(self):
        warnings = inspect(day(), "", "", "")
        pairs = {(item["code"], item["race_id"]) for item in warnings}
        self.assertIn(("SHADOW_INELIGIBLE", "race-a"), pairs)


if __name__ == "__main__":
    unittest.main()
