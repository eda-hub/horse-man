import copy
import hashlib
import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch
import test_class_transition as inputs
import test_cycle04_acceptance as originals
from class_transition_shadow import fixed_cases,diagnostic_pair,collection,verified_pair,main
from check_prediction_compliance import ComplianceError,validate_gate

ROOT=Path(__file__).resolve().parents[1]


class ClassTransitionShadowTest(unittest.TestCase):
    def plan(self):return json.loads((ROOT/'docs/validation/class-transition/forward-plan.json').read_text())
    def cases(self):return json.loads((ROOT/'docs/validation/class-transition/fixed-cases.json').read_text())['cases']
    def pair(self):
        assessment=inputs.fixture();assessment['comparison_evidence']=[inputs.evidence()]
        rates=[{'horse_no':h,'win_probability':w,'top2_probability':p2,'top3_probability':p3} for h,w,p2,p3 in [(1,.4,.7,.9),(2,.3,.6,.8),(3,.2,.5,.7),(4,.1,.2,.6)]]
        forecast={'ranking':[1,2,3,4],'probabilities':rates,'data_cutoff':assessment['data_cutoff'],'common_input_sha256':'a'*64}
        pair={'schema_version':'class-transition-shadow-pair-v1','mode':'SYNTHETIC','race_id':assessment['race_id'],'race_date_jst':'2026-10-17',
              'data_cutoff':assessment['data_cutoff'],'scheduled_post_time_jst':'2026-10-17T10:10:00+09:00',
              'baseline':forecast,'shadow':copy.deepcopy(forecast),'common_input_sha256':'a'*64,'assessment':assessment,
              'comparison_method_id':'class-transition-evidence-v1','change_reason':'合成比較の根拠と保護を記録'}
        result={'status':'OFFICIAL','race_id':pair['race_id'],'race_date_jst':pair['race_date_jst'],
                'source_url':'https://www.jra.go.jp/synthetic-result','retrieved_at_jst':'2026-10-17T11:00:00+09:00',
                'finish_groups':[[1],[2],[3],[4]],'place_places':3}
        return pair,result

    def verified_fixture(self):
        f=originals.Cycle04Acceptance();f.addCleanup=self.addCleanup;day,_=f.complete_day();root=f.root
        row=day['races'][originals.RACE];path=row['prediction_gate_path'];gate=validate_gate(root,root/path)
        production=gate['production'];prediction_hash=hashlib.sha256((root/production['evidence_ref']['artifact_path']).read_bytes()).hexdigest();assessment=inputs.fixture();assessment['race_id']=gate['race_id'];assessment['data_cutoff']=gate['data_cutoff'];assessment['horse_no']=5;assessment['comparison_evidence']=[inputs.evidence()]
        common=f.artifact('shadow-common','shadow/common.json',{'schema_version':'class-transition-common-input-v1','race_id':gate['race_id'],'data_cutoff':gate['data_cutoff'],'assessments':[assessment]},at='09:51')
        binding=f.artifact('shadow-binding','shadow/binding.json',{'schema_version':'class-transition-input-binding-v1','race_id':gate['race_id'],'data_cutoff':gate['data_cutoff'],'baseline_prediction_sha256':prediction_hash,'common_input_sha256':common['sha256']},at='09:57')
        base={'ranking':production['ranking'],'probabilities':production['probabilities'],'data_cutoff':gate['data_cutoff'],'common_input_sha256':common['sha256']}
        pair={'schema_version':'class-transition-shadow-pair-v1','mode':'FORWARD','race_id':gate['race_id'],'race_date_jst':gate['race_date_jst'],'data_cutoff':gate['data_cutoff'],
              'scheduled_post_time_jst':gate['scheduled_post_time_jst'],'baseline_forecast_id':production['baseline_forecast_id'],'baseline_prediction_sha256':prediction_hash,
              'baseline':base,'shadow':copy.deepcopy(base),'assessment':assessment,'common_input_ref':common,'common_input_sha256':common['sha256'],'baseline_input_binding_ref':binding,
              'comparison_method_id':'class-transition-evidence-v1','change_reason':'入力証拠を照合し基準値を保護した合成中立比較'}
        ref=f.artifact('shadow-pair','shadow/pair.json',pair,at='09:58')
        ref.update(timing_eligibility='PRE_RACE_ELIGIBLE',persist_verified_at_jst='2026-10-17T09:58:00+09:00')
        gate['kpi_eligibility']['shadow']='ELIGIBLE';gate['shadow_items']=[{'item_id':'class-transition-trial','kpi_eligibility':'ELIGIBLE','evidence_ref':ref}]
        (root/path).write_text(json.dumps(gate))
        result={'status':'OFFICIAL','race_id':gate['race_id'],'race_date_jst':gate['race_date_jst'],'source_url':'https://www.jra.go.jp/synthetic-result',
                'retrieved_at_jst':'2026-10-17T11:00:00+09:00','finish_groups':[[5],[2],[6],[4],[1],[3]],'place_places':3}
        (root/'result.json').write_text(json.dumps(result))
        item={'gate_path':path,'shadow_item_id':'class-transition-trial','result_path':'result.json'}
        return root,item,pair,ref,gate

    def test_three_fixed_conditions_distinct_and_not_forward(self):
        results=fixed_cases(self.cases());self.assertEqual(len(results),3)
        self.assertIs(results[0]['assessment']['first_older_encounter'],True);self.assertIs(results[0]['assessment']['class_promotion'],False)
        self.assertIs(results[1]['assessment']['first_older_encounter'],False);self.assertIs(results[1]['assessment']['class_promotion'],True)
        self.assertEqual(results[2]['assessment']['comparison_sufficiency'],'NOT_COMPARABLE')
        self.assertTrue(all(not r['forward_kpi_eligible'] and r['non_degradation']=='NOT_MEASURED' for r in results))

    def test_fixed_batch_limit_duplicates_and_fake_forward_rejected(self):
        for mutation in ('four','duplicate','forward'):
            cases=self.cases()
            if mutation=='four':cases.append(copy.deepcopy(cases[0]))
            elif mutation=='duplicate':cases[1]['case_id']=cases[0]['case_id']
            else:cases[0]['mode']='FORWARD'
            with self.assertRaises(ComplianceError):fixed_cases(cases)

    def test_neutral_metrics_and_no_authentication_from_diagnostic(self):
        p,r=self.pair();before=copy.deepcopy(p);report=diagnostic_pair(p,r)
        self.assertEqual(report['paired_observation'],'NEUTRAL');self.assertFalse(report['forward_kpi_eligible']);self.assertEqual(p,before)
        self.assertAlmostEqual(report['metrics']['baseline']['win_probability'],.125)

    def test_improvement_worsening_and_mixed_changes(self):
        p,r=self.pair();p['shadow']['probabilities'][0]['win_probability']=.5;p['shadow']['probabilities'][1]['win_probability']=.2
        self.assertEqual(diagnostic_pair(p,r)['paired_observation'],'IMPROVED')
        p,r=self.pair();p['shadow']['probabilities'][0]['win_probability']=.3;p['shadow']['probabilities'][1]['win_probability']=.4
        self.assertEqual(diagnostic_pair(p,r)['paired_observation'],'WORSENED')
        p,r=self.pair();p['shadow']['ranking']=[4,3,2,1]
        self.assertEqual(diagnostic_pair(p,r)['paired_observation'],'WORSENED')

    def test_cutoff_common_input_horse_and_probability_mismatches(self):
        for field in ('cutoff','input','horse','sum','null'):
            p,r=self.pair()
            if field=='cutoff':p['shadow']['data_cutoff']='2026-10-17T09:01:00+09:00'
            elif field=='input':p['shadow']['common_input_sha256']='b'*64
            elif field=='horse':p['shadow']['ranking'][0]=99
            elif field=='sum':p['shadow']['probabilities'][0]['win_probability']=.6
            else:p['shadow']['probabilities'][0]['win_probability']=None
            with self.assertRaises(ComplianceError):diagnostic_pair(p,r)

    def test_comparison_method_and_reason_are_required(self):
        for field in ('comparison_method_id','change_reason'):
            p,r=self.pair();p.pop(field)
            with self.assertRaises(ComplianceError):diagnostic_pair(p,r)

    def test_replay_never_forward_and_cancelled_tie_excluded(self):
        p,r=self.pair();p['mode']='REPLAY';self.assertFalse(diagnostic_pair(p,r)['forward_kpi_eligible'])
        r['finish_groups']=[[1,2],[3],[4]];self.assertEqual(diagnostic_pair(p,r)['status'],'NOT_COMPARABLE')
        p,r=self.pair();r['finish_groups']=[[1],[2],[3]];r['scratched_horses']=[4]
        self.assertEqual(diagnostic_pair(p,r)['status'],'NOT_COMPARABLE')

    def test_empty_collection_not_zero_measured_and_scope_confirmed(self):
        r=collection(ROOT,[],self.plan(),as_of='2026-10-13T21:00:00+09:00')
        self.assertIsNone(r['eligible_pair_count']);self.assertIsNone(r['mean_delta']);self.assertFalse(r['period_complete'])
        self.assertEqual(r['non_degradation'],'NOT_ACCEPTED_OWNER_REVIEW_REQUIRED')

    def test_period_japan_date_and_scope_tampering(self):
        self.assertTrue(collection(ROOT,[],self.plan(),as_of='2026-10-25T15:01:00+00:00')['period_complete'])
        bad=self.plan();bad['race_dates']=['2026-10-17']
        with self.assertRaises(ComplianceError):collection(ROOT,[],bad)

    def test_elapsed_window_not_complete_trial_and_invalid_reference_excluded(self):
        r=collection(ROOT,[None],self.plan(),as_of='2026-10-26T12:00:00+09:00')
        self.assertTrue(r['period_complete']);self.assertFalse(r['trial_complete']);self.assertFalse(r['sample_coverage_verified'])
        self.assertEqual(len(r['excluded_reports']),1)

    def test_verified_pair_reuses_gate_receipts_and_preserves_files(self):
        root,item,_,_,_=self.verified_fixture();before={p:p.read_bytes() for p in root.rglob('*') if p.is_file()}
        report=collection(root,[item],self.plan(),as_of='2026-10-17T12:00:00+09:00')
        self.assertEqual(report['eligible_pair_count'],1);self.assertEqual(report['paired_reports'][0]['status'],'VERIFIED_PAIR')
        self.assertEqual(report['performance_promotion'],'NOT_APPROVED')
        self.assertTrue(all(p.read_bytes()==b for p,b in before.items()))

    def test_receipt_tampering_and_unknown_shadow_item_excluded(self):
        root,item,_,ref,_=self.verified_fixture();(root/ref['artifact_path']).write_text('{}')
        self.assertEqual(collection(root,[item],self.plan(),as_of='2026-10-17T12:00:00+09:00')['eligible_pair_count'],0)
        item['shadow_item_id']='wrong';self.assertEqual(collection(root,[item],self.plan(),as_of='2026-10-17T12:00:00+09:00')['eligible_pair_count'],0)

    def test_unheld_baseline_and_replay_pair_excluded(self):
        root,item,pair,ref,gate=self.verified_fixture()
        with patch('class_transition_shadow.verified_artifact') as read:
            altered=copy.deepcopy(pair);altered['baseline']['probabilities'][0]['win_probability']=.5;read.return_value=(altered,{})
            self.assertEqual(collection(root,[item],self.plan(),as_of='2026-10-17T12:00:00+09:00')['eligible_pair_count'],0)
            altered=copy.deepcopy(pair);altered['mode']='REPLAY';read.return_value=(altered,{})
            self.assertEqual(collection(root,[item],self.plan(),as_of='2026-10-17T12:00:00+09:00')['eligible_pair_count'],0)

    def test_missing_binding_and_future_result_excluded(self):
        root,item,pair,_,_=self.verified_fixture();(root/pair['baseline_input_binding_ref']['artifact_path']).unlink()
        self.assertEqual(collection(root,[item],self.plan(),as_of='2026-10-17T12:00:00+09:00')['eligible_pair_count'],0)
        root,item,_,_,_=self.verified_fixture()
        self.assertEqual(collection(root,[item],self.plan(),as_of='2026-10-13T21:00:00+09:00')['eligible_pair_count'],0)

    def test_duplicate_race_not_counted_twice(self):
        root,item,_,_,_=self.verified_fixture();r=collection(root,[item,item],self.plan(),as_of='2026-10-17T12:00:00+09:00')
        self.assertEqual(r['eligible_pair_count'],1);self.assertEqual(len(r['excluded_reports']),1)

    def test_binding_before_original_readback_excluded(self):
        root,item,pair,_,_=self.verified_fixture();path=root/pair['baseline_input_binding_ref']['receipt_path']
        text=path.read_text();text=text.replace('2026-10-17T09:57:00+09:00','2026-10-17T09:52:00+09:00');path.write_text(text)
        r=collection(root,[item],self.plan(),as_of='2026-10-17T12:00:00+09:00')
        self.assertEqual(r['eligible_pair_count'],0);self.assertIn('保存順序',r['excluded_reports'][0]['reason'])

    def test_other_common_future_information_excluded(self):
        root,item,pair,ref,_=self.verified_fixture()
        from class_transition_shadow import verified_artifact as original_read
        def read(*args,**kwargs):
            data,receipt=original_read(*args,**kwargs)
            if args[1].get('artifact_id')=='shadow-common':
                data=copy.deepcopy(data);data['other_facts']=[{'horse_no':5,'factor':'ability','fact':'未来成績','source_ref':'synthetic','observed_at_jst':'2026-10-18T12:00:00+09:00','direction':'plus','strength':'strong'}]
            return data,receipt
        with patch('class_transition_shadow.verified_artifact',side_effect=read):r=collection(root,[item],self.plan(),as_of='2026-10-17T12:00:00+09:00')
        self.assertEqual(r['eligible_pair_count'],0)

    def test_cli_reads_fixed_cases_without_writing(self):
        path=ROOT/'docs/validation/class-transition/fixed-cases.json';before=path.read_bytes()
        with redirect_stdout(io.StringIO()):self.assertEqual(main([str(path)]),0)
        self.assertEqual(path.read_bytes(),before)


if __name__=='__main__':unittest.main()
