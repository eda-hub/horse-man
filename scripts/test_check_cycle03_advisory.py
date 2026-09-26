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


def pairs(warnings):
    return {(item["code"], item["race_id"]) for item in warnings}


class AdvisoryChecks(unittest.TestCase):
    def test_missing_final_is_reported(self):
        self.assertIn(
            ("FINAL_NOT_COMPLETED", "race-b"),
            pairs(inspect(day(), "", "", "")),
        )

    def test_initial_gap_is_not_hidden_by_final_values(self):
        snapshot = """## race-a 初回予想
snapshot_type: INITIAL
race_id: race-a
snapshot_id: initial-a
baseline_forecast_id: MISSING_IN_INITIAL_SNAPSHOT
推定確率（勝率/連対率/3着内率）: UNAVAILABLE

## race-a 最終予想
snapshot_type: FINAL
race_id: race-a
snapshot_id: final-a
baseline_forecast_id: base-added-later
candidate_class: validation_only
推定確率（勝率/連対率/3着内率）: 20% / 35% / 50%
"""
        receipt = """## persistence_receipt
artifact_id: final-a
receipt_persist_status: RECEIPT_VERIFIED
timing_eligibility: PRE_RACE_ELIGIBLE
"""
        found = pairs(inspect(day(), snapshot, receipt, ""))
        self.assertIn(("BASELINE_ID_MISSING", "race-a"), found)
        self.assertIn(("PROBABILITY_EVIDENCE_MISSING", "race-a"), found)

    def test_initial_receipt_does_not_hide_missing_final_receipt(self):
        snapshot = """## race-a 初回予想
snapshot_type: INITIAL
race_id: race-a
snapshot_id: initial-a
baseline_forecast_id: base-a
推定確率（勝率/連対率/3着内率）: 20% / 35% / 50%

## race-a 最終予想
snapshot_type: FINAL
race_id: race-a
snapshot_id: final-a
candidate_class: validation_only
"""
        receipt = """## persistence_receipt
artifact_id: initial-a
receipt_persist_status: RECEIPT_VERIFIED
timing_eligibility: PRE_RACE_ELIGIBLE
"""
        self.assertIn(
            ("PRE_RACE_RECEIPT_MISSING", "race-a"),
            pairs(inspect(day(), snapshot, receipt, "")),
        )

    def test_verified_final_prerace_receipt_clears_receipt_warning(self):
        snapshot = """## race-a 初回予想
snapshot_type: INITIAL
race_id: race-a
snapshot_id: initial-a
baseline_forecast_id: base-a
推定確率（勝率/連対率/3着内率）: 20% / 35% / 50%

## race-a 最終予想
snapshot_type: FINAL
race_id: race-a
snapshot_id: final-a
candidate_class: validation_only
"""
        receipt = """## persistence_receipt
artifact_id: final-a
receipt_persist_status: RECEIPT_VERIFIED
timing_eligibility: PRE_RACE_ELIGIBLE
"""
        self.assertNotIn(
            ("PRE_RACE_RECEIPT_MISSING", "race-a"),
            pairs(inspect(day(), snapshot, receipt, "")),
        )

    def test_multiline_probability_bullets_are_detected(self):
        snapshot = """## race-a 初回予想
snapshot_type: INITIAL
race_id: race-a
snapshot_id: initial-a
baseline_forecast_id: base-a
推定確率（勝率/連対率/3着内率）:
  - 1 Horse A: 16% / 30% / 42%
  - 2 Horse B: 15% / 29% / 41%
"""
        self.assertNotIn(
            ("PROBABILITY_EVIDENCE_MISSING", "race-a"),
            pairs(inspect(day(), snapshot, "", "")),
        )

    def test_probability_table_is_detected(self):
        snapshot = """## race-a 初回予想
snapshot_type: INITIAL
race_id: race-a
snapshot_id: initial-a
baseline_forecast_id: base-a
推定確率
| 馬 | 勝率 | 連対率 | 3着内率 |
|---|---:|---:|---:|
| Horse A | 16% | 30% | 42% |
"""
        self.assertNotIn(
            ("PROBABILITY_EVIDENCE_MISSING", "race-a"),
            pairs(inspect(day(), snapshot, "", "")),
        )

    def test_percent_symbol_without_number_is_not_probability_evidence(self):
        snapshot = """## race-a 初回予想
snapshot_type: INITIAL
race_id: race-a
snapshot_id: initial-a
baseline_forecast_id: base-a
勝率: 未取得（%）
"""
        self.assertIn(
            ("PROBABILITY_EVIDENCE_MISSING", "race-a"),
            pairs(inspect(day(), snapshot, "", "")),
        )

    def test_late_preservation_is_explicitly_reported(self):
        preservation = """## race-a preservation
race_id: race-a
preservation_id: late-a
baseline_forecast_id: MISSING_IN_INITIAL_SNAPSHOT
candidate_class: validation_only
timing_eligibility: LATE_PRESERVATION
"""
        found = pairs(inspect(day(), "", "", preservation))
        self.assertIn(("LATE_PRESERVATION", "race-a"), found)
        self.assertIn(("PRE_RACE_RECEIPT_MISSING", "race-a"), found)

    def test_japanese_candidate_class_is_accepted(self):
        snapshot = """## race-a 最終予想
snapshot_type: FINAL
race_id: race-a
snapshot_id: final-a
候補区分: validation_only
"""
        self.assertNotIn(
            ("CANDIDATE_CLASS_MISSING", "race-a"),
            pairs(inspect(day(), snapshot, "", "")),
        )

    def test_shadow_ineligible_is_reported(self):
        self.assertIn(
            ("SHADOW_INELIGIBLE", "race-a"),
            pairs(inspect(day(), "", "", "")),
        )


if __name__ == "__main__":
    unittest.main()
