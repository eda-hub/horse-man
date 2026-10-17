#!/usr/bin/env python3
"""10月17日36Rの事後全件結果、同着、KPI非適格、元予想参照の回帰試験。"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from check_cycle04_full_day_reconciliation import (
    check, FullDayReviewError, MORNING, DAY, RESULTS, SIX, DECISION,
)


class Cycle04FullDayRetrospectiveTest(unittest.TestCase):
    SOURCE_ROOT = Path(__file__).resolve().parent.parent

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for relative in (MORNING, DAY, RESULTS, SIX, DECISION):
            p = self.root / relative
            p.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(self.SOURCE_ROOT / relative, p)

    def read(self, path):
        return json.loads((self.root / path).read_text(encoding='utf-8'))

    def write(self, path, data):
        (self.root / path).write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + '\n',
            encoding='utf-8',
        )

    def test_all36_results_and_non_certification(self):
        report = check(self.root)
        self.assertEqual(report['verified_result_races'], 36)
        self.assertEqual(report['linked_six_predictions'], 6)
        self.assertEqual(report['without_fixed_final_prediction'], 30)
        self.assertEqual(report['tie_2nd_place'], 1)
        self.assertEqual(report['official_result_pages_verified'], 6)
        self.assertEqual(report['formal_eligible_denominators'],
                         {'prediction': 0, 'recommendation': 0, 'shadow': 0})
        self.assertEqual(report['formal_certification'], 'REJECTED_UNDER_V1_7_0')

    def test_certification_rejects_inflated_official_url_count(self):
        data = self.read(DECISION)
        data['coverage']['top3_official_page_urls'] = 36
        self.write(DECISION, data)
        with self.assertRaisesRegex(FullDayReviewError, 'official result URL count mismatch'):
            check(self.root)

    def test_certification_rejects_understated_official_url_count(self):
        data = self.read(DECISION)
        data['coverage']['top3_official_page_urls'] = 5
        self.write(DECISION, data)
        with self.assertRaisesRegex(FullDayReviewError, 'official result URL count mismatch'):
            check(self.root)

    def test_result_summary_disagreement_with_actual_urls_rejected(self):
        data = self.read(RESULTS)
        data['coverage']['result_top3_primary_jra_confirmed'] = 36
        self.write(RESULTS, data)
        with self.assertRaisesRegex(FullDayReviewError, 'official result URL count mismatch'):
            check(self.root)

    def test_certification_verified_page_count_disagreement_rejected(self):
        data = self.read(DECISION)
        data['coverage']['official_results_pages_verified'] = 36
        self.write(DECISION, data)
        with self.assertRaisesRegex(FullDayReviewError, 'official result URL count mismatch'):
            check(self.root)

    def test_removed_result_rejected(self):
        data = self.read(RESULTS)
        data['races'].pop()
        self.write(RESULTS, data)
        with self.assertRaisesRegex(FullDayReviewError, '36-race'):
            check(self.root)

    def test_different_top3_from_day_index_rejected(self):
        data = self.read(RESULTS)
        data['races'][0]['result']['top3_horse_numbers'][0] = 99
        self.write(RESULTS, data)
        with self.assertRaises(FullDayReviewError):
            check(self.root)

    def test_original_six_results_cannot_be_revised(self):
        data = self.read(RESULTS)
        row = next(x for x in data['races'] if x['race_id'] == '2026-10-17-TOKYO-11')
        row['result']['top3_horse_numbers'][0] = 99
        row['result']['top_finishers'][0]['horse_no'] = 99
        self.write(RESULTS, data)
        with self.assertRaisesRegex(FullDayReviewError, 'original day index differs'):
            check(self.root)

    def test_kyoto12_tied_second_cannot_be_changed(self):
        data = self.read(RESULTS)
        row = next(x for x in data['races'] if x['race_id'] == '2026-10-17-KYOTO-12')
        row['result']['top_finishers'][2]['position'] = 3
        self.write(RESULTS, data)
        with self.assertRaisesRegex(FullDayReviewError, 'dead-heat'):
            check(self.root)

    def test_missing_official_page_rejected(self):
        data = self.read(RESULTS)
        row = next(x for x in data['races']
                   if x['race_id'] == '2026-10-17-TOKYO-11')
        row['source']['official_url'] = 'https://example.invalid'
        self.write(RESULTS, data)
        with self.assertRaisesRegex(FullDayReviewError,
                                    'original day index differs|verified JRA source mismatch'):
            check(self.root)

    def test_secondary_result_cannot_claim_jra_verification(self):
        data = self.read(RESULTS)
        data['races'][0]['source']['official_individual_page_verified'] = True
        self.write(RESULTS, data)
        with self.assertRaisesRegex(FullDayReviewError, 'secondary results must not claim'):
            check(self.root)

    def test_result_invented_prediction_for_unforecast_race_rejected(self):
        data = self.read(RESULTS)
        data['races'][0]['pre_off_forecast']['path'] = 'docs/validation/fake.json'
        self.write(RESULTS, data)
        with self.assertRaisesRegex(FullDayReviewError, 'invented result-time forecast'):
            check(self.root)

    def test_formal_prediction_kpi_promotion_rejected(self):
        data = self.read(DECISION)
        data['decisions'][0]['prediction']['status'] = 'ELIGIBLE'
        data['decisions'][0]['prediction']['score'] = 1.0
        self.write(DECISION, data)
        with self.assertRaisesRegex(FullDayReviewError, 'formal KPI promotion'):
            check(self.root)

    def test_formal_rate_zero_instead_of_null_rejected(self):
        data = self.read(DECISION)
        data['certification']['rates']['prediction_win_brier'] = 0.0
        self.write(DECISION, data)
        with self.assertRaisesRegex(FullDayReviewError, 'formal KPI status'):
            check(self.root)

    def test_disallow_postrace_created_formal_ledger(self):
        name = self.root / 'docs/validation/records/cycle_04/2026-10-17.json'
        name.parent.mkdir(parents=True, exist_ok=True)
        name.write_text('{}\n', encoding='utf-8')
        with self.assertRaisesRegex(FullDayReviewError, 'formal day ledger unexpectedly'):
            check(self.root)

    def test_scope_change_rejected(self):
        data = self.read(MORNING)
        data['required_race_ids'][0] = '2026-10-17-TOKYO-99'
        self.write(MORNING, data)
        with self.assertRaisesRegex(FullDayReviewError, 'scope'):
            check(self.root)


if __name__ == '__main__':
    unittest.main()
