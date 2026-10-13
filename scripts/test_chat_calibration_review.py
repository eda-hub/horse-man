import json
import unittest
from pathlib import Path
from chat_calibration_review import export_inputs
import test_chat_forward_coverage as coverage_fixtures
import test_class_transition_shadow as shadow_fixtures
from class_transition_shadow import verified_pair
from check_prediction_compliance import iso
from cycle04_operations import fingerprint
from unittest.mock import patch


class CalibrationReview(unittest.TestCase):
    def test_fixed_pair_exports_probabilities_outcomes_brier_and_strata_without_mutation(self):
        case=shadow_fixtures.ClassTransitionShadowTest();case.addCleanup=self.addCleanup
        root,item,pair,ref,gate=case.verified_fixture()
        plan=case.plan();now='2026-10-17T12:00:00+09:00'
        report=verified_pair(root,item,plan,iso(now,'test time'))
        scope={'initial_scope':[gate['race_id']],'accepted_ids':[gate['race_id']],
               'sample_coverage_verified':True,'collection':{'paired_reports':[report],'mean_delta':report['metrics']['delta']}}
        item.update(gate_ref={'artifact_path':item['gate_path'],'sha256':fingerprint((root/item['gate_path']).read_bytes())},
                    result_ref={'artifact_path':item['result_path'],'sha256':fingerprint((root/item['result_path']).read_bytes())})
        manifest={'plan':plan,'days':[],'assessments':[],'items':[item]}
        before={str(p):p.read_bytes() for p in root.rglob('*') if p.is_file()}
        # Scope aggregation is tested separately; this tests the real fixed pair/export connection.
        with patch('chat_calibration_review.coverage',return_value=scope):
            out=export_inputs(root,manifest,now)
        self.assertEqual(out['pair_count'],1);self.assertEqual(len(out['pairs'][0]['horse_observations']),6)
        winner=next(r for r in out['pairs'][0]['horse_observations'] if r['horse_no']==5)
        self.assertEqual(winner['outcomes']['win_probability'],1)
        self.assertEqual(out['pairs'][0]['paired_metrics'],report['metrics'])
        self.assertEqual(out['strata'][0]['pair_count'],1)
        self.assertEqual(out['non_degradation'],'OWNER_REVIEW_REQUIRED')
        self.assertEqual(before,{str(p):p.read_bytes() for p in root.rglob('*') if p.is_file()})

    def test_no_data_has_null_metrics_no_threshold_or_roi(self):
        plan=json.loads((Path(__file__).resolve().parents[1]/'docs/validation/class-transition/forward-plan.json').read_text())
        out=export_inputs(Path('.'),{'plan':plan,'days':[],'assessments':[],'items':[]},'2026-10-14T12:00:00+09:00')
        self.assertIsNone(out['pair_count']);self.assertIsNone(out['mean_delta'])
        self.assertIsNone(out['probability_lower_bound']);self.assertIsNone(out['new_threshold'])
        self.assertIsNone(out['market_roi']);self.assertFalse(out['owner_review_ready'])

    def test_missing_pair_remains_missing_not_calibrated(self):
        case=coverage_fixtures.ForwardCoverage();case.setUp();self.addCleanup(case.doCleanups)
        case.add_assessment()
        out=export_inputs(case.root,case.manifest,case.now)
        self.assertFalse(out['owner_review_ready']);self.assertEqual(out['coverage']['missing_ids'],out['coverage']['applicable_ids'])
        self.assertEqual(out['pairs'],[]);self.assertIsNone(out['mean_delta'])
        self.assertEqual(out['calibration'],'NOT_ACCEPTED')
        self.assertEqual(out['performance_promotion'],'NOT_APPROVED')


if __name__=='__main__':unittest.main()
