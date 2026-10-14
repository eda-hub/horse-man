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
        scope['submitted_pair_bindings']={gate['race_id']:{
            'phase':'INITIAL','prediction_gate_sha256':item['gate_ref']['sha256'],
            'data_cutoff':pair['data_cutoff'],'baseline_forecast_id':pair['baseline_forecast_id'],
            'shadow_item_id':item['shadow_item_id']}}
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

    def fixed_phase_fixture(self,phase):
        case=shadow_fixtures.ClassTransitionShadowTest();case.addCleanup=self.addCleanup
        root,item,pair,_,gate=case.verified_fixture()
        now='2026-10-17T12:00:00+09:00'
        report=verified_pair(root,item,case.plan(),iso(now,'test time'))
        item.update(gate_ref={'artifact_path':item['gate_path'],
                             'sha256':fingerprint((root/item['gate_path']).read_bytes())},
                    result_ref={'artifact_path':item['result_path'],
                                'sha256':fingerprint((root/item['result_path']).read_bytes())})
        rec_path='docs/validation/recommendation-gates/2026-10-17/'+gate['race_id']+'.json'
        day_path='docs/validation/records/cycle_04/2026-10-17.json'
        (root/day_path).parent.mkdir(parents=True,exist_ok=True)
        (root/day_path).write_text(json.dumps({'races':{
            gate['race_id']:{'recommendation_gate_path':rec_path}}}))
        manifest={'plan':case.plan(),
                  'days':[{'artifact_path':day_path,'sha256':fingerprint((root/day_path).read_bytes())}],
                  'assessments':[],'items':[item]}
        binding={'phase':phase,'prediction_gate_sha256':item['gate_ref']['sha256'],
                 'data_cutoff':pair['data_cutoff'],'baseline_forecast_id':pair['baseline_forecast_id'],
                 'shadow_item_id':item['shadow_item_id']}
        scope={'initial_scope':[gate['race_id']],'accepted_ids':[gate['race_id']],
               'sample_coverage_verified':True,
               'submitted_pair_bindings':{gate['race_id']:binding},
               'collection':{'paired_reports':[report],'mean_delta':report['metrics']['delta']}}
        return root,manifest,scope,now,gate['race_id']

    def test_initial_fixed_pair_ignores_later_final_recommendation_cutoff(self):
        root,manifest,scope,now,race=self.fixed_phase_fixture('INITIAL')
        # 最新FINAL推奨は独立検証済みでもINITIAL比較への対応推奨ではない。
        # 9:50の初回比較と9:51の最終推奨を混ぜない。別時点の推奨を参照しない。
        from recommendation import verify as original_verify
        from cycle04_operations import safe_path
        recpath='docs/validation/recommendation-gates/2026-10-17/'+race+'.json'
        rec=original_verify(root,safe_path(root,recpath))
        self.assertEqual(rec['phase'],'FINAL')
        self.assertEqual(scope['submitted_pair_bindings'][race]['data_cutoff'],
                         '2026-10-17T09:50:00+09:00')
        before={str(p):p.read_bytes() for p in root.rglob('*') if p.is_file()}
        later_final=dict(rec,data_cutoff='2026-10-17T09:51:00+09:00')
        with patch('chat_calibration_review.coverage',return_value=scope), \
             patch('chat_calibration_review.verify_recommendation',return_value=later_final) as latest:
            out=export_inputs(root,manifest,now)
            latest.assert_not_called()
        self.assertEqual(out['pair_count'],1)
        self.assertEqual(out['pairs'][0]['comparison_phase'],'INITIAL')
        self.assertIsNone(out['pairs'][0]['recommendation_input'])
        self.assertEqual(out['pairs'][0]['recommendation_binding_status'],'DIFFERENT_PHASE')
        self.assertEqual(before,{str(p):p.read_bytes() for p in root.rglob('*') if p.is_file()})

    def test_final_same_fixed_prediction_can_bind_independent_recommendation(self):
        root,manifest,scope,now,_=self.fixed_phase_fixture('FINAL')
        with patch('chat_calibration_review.coverage',return_value=scope):
            out=export_inputs(root,manifest,now)
        pair=out['pairs'][0]
        self.assertEqual(pair['recommendation_binding_status'],'MATCHED_FINAL')
        self.assertIsNotNone(pair['recommendation_input'])
        self.assertEqual(pair['comparison_phase'],'FINAL')

    def test_final_mismatched_recommendation_cutoff_is_rejected(self):
        root,manifest,scope,now,race=self.fixed_phase_fixture('FINAL')
        from recommendation import verify as original_verify
        from cycle04_operations import safe_path
        recpath='docs/validation/recommendation-gates/2026-10-17/'+race+'.json'
        rec=original_verify(root,safe_path(root,recpath))
        rec['data_cutoff']='2026-10-17T09:51:00+09:00'
        with patch('chat_calibration_review.coverage',return_value=scope), \
             patch('chat_calibration_review.verify_recommendation',return_value=rec):
            with self.assertRaisesRegex(ValueError,'recommendation comparison cutoff/phase/baseline differs'):
                export_inputs(root,manifest,now)

    def test_missing_accepted_pair_phase_binding_is_rejected(self):
        root,manifest,scope,now,_=self.fixed_phase_fixture('INITIAL')
        scope['submitted_pair_bindings'].clear()
        with patch('chat_calibration_review.coverage',return_value=scope):
            with self.assertRaisesRegex(ValueError,'calibration pair differs from fixed phase'):
                export_inputs(root,manifest,now)

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
