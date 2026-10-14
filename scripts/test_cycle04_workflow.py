"""実測を捏造せず、独立証跡を使って初回から結果照合まで通す。"""
import copy
import json
import unittest
from datetime import datetime

import test_cycle04_acceptance as fixtures
from test_recommendation import DATE, RACE, POST
from test_next_prediction_compliance import write
from check_cycle04 import CONTRACT_PATH
from check_prediction_compliance import ComplianceError
import cycle04_workflow as workflow


class OperationalWorkflow(unittest.TestCase):
    def setUp(self):
        # 将来開催日の合成証跡は検査時刻も合成固定し、実時刻を偽装した恒久記録を作らない。
        from unittest.mock import patch
        class SyntheticShadowClock(datetime):
            @classmethod
            def now(cls, tz=None):
                instant = datetime.fromisoformat(DATE+'T12:00:00+09:00')
                return instant.astimezone(tz) if tz else instant.replace(tzinfo=None)
        clock = patch('check_prediction_compliance.datetime', SyntheticShadowClock)
        clock.start()
        self.addCleanup(clock.stop)
        self.fixture=fixtures.Cycle04Acceptance()
        self.fixture.addCleanup=self.addCleanup
        self.fixture.setUp()
        self.complete,contract=self.fixture.complete_day()
        self.root=self.fixture.root
        state_path=self.root/"docs/validation/execution-gates/contract-state.json"
        state=json.loads(state_path.read_text());state["full_horse_contract"]="REQUIRED"
        state_path.write_text(json.dumps(state))
        contract.update(race_dates=workflow.DATES)
        write(self.root,CONTRACT_PATH,json.dumps(contract))
        self.entry=copy.deepcopy(self.complete['races'][RACE])
        self.entry.update(race_id=RACE,phase='INITIAL')
        self.entry['shadow_applicability']={'status':'NOT_APPLICABLE',
              'reason':'合成fixtureに該当Shadowなし','item_ids':[]}
        self.scope={'schema_version':'cycle04-official-scope-v1','race_date_jst':DATE,
                    'source_url':'https://www.jra.go.jp/test/official-scope',
                    'observed_at_jst':DATE+'T09:30:00+09:00',
                    'races':[{'race_id':RACE,'scheduled_post_time_jst':POST}]}
        self.now=datetime.fromisoformat(DATE+'T09:38:00+09:00')

    def register(self):
        return workflow.register_scope(self.root,self.scope,now=self.now)

    def select(self):
        workflow.select(self.root,DATE,{'race_id':RACE,'selection_ref':self.entry['operations']['selection_ref']})

    def test_scope_initial_final_official_review_and_independent_denominators(self):
        self.register()
        workflow.record_prediction(self.root,DATE,self.entry)
        self.assertEqual(workflow.summary(self.root)['kpis']['recommendation']['target_ids'],0)
        self.select()
        self.entry['phase']='FINAL'
        workflow.record_prediction(self.root,DATE,self.entry)
        before=workflow.summary(self.root)
        self.assertEqual(before['prediction_performance']['eligible_reviewed'],0)
        self.assertIsNone(before['prediction_performance']['honmei_win'])
        result={'race_id':RACE,'race_date_jst':DATE,'status':'OFFICIAL',
                'source_url':'https://www.jra.go.jp/test/result','retrieved_at_jst':DATE+'T11:00:00+09:00',
                'finish_groups':[[5],[2],[6],[4],[1],[3]],'place_places':3}
        write(self.root,'result.json',json.dumps(result))
        workflow.review(self.root,DATE,{'race_id':RACE,'result_path':'result.json',
                        'review':{'error_classification':'軸と上位一致','non_degradation':'未取得入力の影響は保留',
                                  'next_validation':'次回も同じ契約で確認'}})
        after=workflow.summary(self.root)
        self.assertEqual(after['initial_races'],1)
        self.assertEqual(after['reviewed_races'],1)
        self.assertEqual(after['prediction_performance']['honmei_win'],1)
        self.assertEqual(after['recommendation_performance']['hit_race_rate'],1)
        self.assertEqual(after['kpis']['market']['eligible_ids'],0)
        self.assertEqual(len(workflow.read_day(self.root,DATE)[0]['races'][RACE]['prediction_history']),2)

    def shadow_gate(self, name='first-shadow', path=None):
        from test_next_prediction_compliance import write
        original=self.root/self.entry['prediction_gate_path']
        gate=json.loads(original.read_text())
        proof=self.fixture.artifact(name,'shadow/'+name+'.json',
            {'schema_version':'shadow-comparison-test-v1','artifact_id':name,'race_id':RACE,
             'race_date_jst':DATE,'mode':'FORWARD','data_cutoff':gate['data_cutoff'],
             'baseline_forecast_id':gate['production']['baseline_forecast_id']},at='10:00')
        proof.update(timing_eligibility='PRE_RACE_ELIGIBLE',
                     persist_verified_at_jst=DATE+'T10:00:00+09:00')
        gate['shadow_items']=[{'item_id':'TEST-SHADOW','state':'FIXED',
                              'kpi_eligibility':'ELIGIBLE','evidence_ref':proof}]
        gate['kpi_eligibility']['shadow']='ELIGIBLE'
        write(self.root,path or self.entry['prediction_gate_path'],json.dumps(gate))
        return gate

    def final_without_shadow(self, gate):
        from test_next_prediction_compliance import write
        final=copy.deepcopy(gate);final['shadow_items']=[]
        final['kpi_eligibility']['shadow']='NOT_APPLICABLE'
        path='docs/validation/execution-gates/'+DATE+'/final-no-shadow.json'
        write(self.root,path,json.dumps(final))
        self.entry['phase']='FINAL';self.entry['prediction_gate_path']=path
        return path

    def test_initial_eligible_final_explicitly_not_applicable_keeps_history(self):
        self.register();gate=self.shadow_gate()
        self.entry['shadow_applicability']={'status':'APPLICABLE','reason':'初回比較を保存',
                                            'item_ids':['TEST-SHADOW']}
        workflow.record_prediction(self.root,DATE,self.entry);self.select()
        path=self.final_without_shadow(gate)
        self.entry['shadow_applicability']={'status':'NOT_APPLICABLE',
              'reason':'最終時点の比較条件を再評価し、該当なし',
              'item_ids':[],'previous_item_dispositions':{
                  'TEST-SHADOW':{'status':'NOT_APPLICABLE','reason':'最終条件で対象外'}}}
        workflow.record_prediction(self.root,DATE,self.entry)
        day,_=workflow.read_day(self.root,DATE)
        self.assertEqual(day['final_scope'],[RACE])
        self.assertEqual(day['kpis']['shadow']['target_ids'],[])
        self.assertEqual(day['kpis']['recommendation']['eligible_ids'],[RACE])
        history=day['races'][RACE]['shadow_history']
        self.assertEqual(len(history),2)
        self.assertEqual(history[0]['items'][0]['item_id'],'TEST-SHADOW')
        self.assertEqual(history[0]['kpi_state'],'ELIGIBLE')
        self.assertEqual(history[1]['kpi_state'],'NOT_APPLICABLE')
        self.assertEqual(history[1]['prediction_gate_path'],path)

    def test_initial_eligible_final_unknown_is_pending_without_blocking_final(self):
        self.register();gate=self.shadow_gate()
        self.entry['shadow_applicability']={'status':'APPLICABLE','reason':'初回固定比較',
                                            'item_ids':['TEST-SHADOW']}
        workflow.record_prediction(self.root,DATE,self.entry);self.select()
        self.final_without_shadow(gate)
        self.entry['shadow_applicability']={'status':'UNKNOWN','reason':'最終の対象条件が未確認',
             'item_ids':[],'previous_item_dispositions':{
                 'TEST-SHADOW':{'status':'UNKNOWN','reason':'最終時点の条件未確認'}}}
        workflow.record_prediction(self.root,DATE,self.entry)
        day,_=workflow.read_day(self.root,DATE)
        self.assertEqual(day['final_scope'],[RACE])
        self.assertEqual(day['kpis']['shadow']['pending_ids'],[RACE])
        self.assertEqual(day['kpis']['recommendation']['eligible_ids'],[RACE])

    def test_initial_eligible_final_ineligible_is_local_to_shadow(self):
        from test_next_prediction_compliance import write
        self.register();gate=self.shadow_gate()
        self.entry['shadow_applicability']={'status':'APPLICABLE','reason':'初回の適格比較',
                                            'item_ids':['TEST-SHADOW']}
        workflow.record_prediction(self.root,DATE,self.entry);self.select()
        final=copy.deepcopy(gate)
        final['shadow_items']=[{'item_id':'TEST-SHADOW','state':'EVIDENCE_UNVERIFIED',
                                'kpi_eligibility':'INELIGIBLE'}]
        final['kpi_eligibility']['shadow']='INELIGIBLE'
        path='docs/validation/execution-gates/'+DATE+'/final-ineligible.json'
        write(self.root,path,json.dumps(final))
        self.entry.update(phase='FINAL',prediction_gate_path=path,
                          shadow_applicability={'status':'APPLICABLE',
                              'reason':'最終Shadow原本の確認不足','item_ids':['TEST-SHADOW']})
        workflow.record_prediction(self.root,DATE,self.entry)
        day,_=workflow.read_day(self.root,DATE)
        self.assertEqual(day['kpis']['shadow']['ineligible_ids'],[RACE])
        self.assertEqual(day['kpis']['recommendation']['eligible_ids'],[RACE])
        self.assertEqual(day['races'][RACE]['shadow_history'][0]['kpi_state'],'ELIGIBLE')

    def test_initial_no_shadow_can_register_first_eligible_final_shadow(self):
        self.register();workflow.record_prediction(self.root,DATE,self.entry);self.select()
        path='docs/validation/execution-gates/'+DATE+'/final-with-shadow.json'
        self.shadow_gate(name='final-shadow',path=path)
        self.entry.update(phase='FINAL',prediction_gate_path=path,
                          shadow_applicability={'status':'APPLICABLE',
                              'reason':'最終で条件に該当','item_ids':['TEST-SHADOW']})
        workflow.record_prediction(self.root,DATE,self.entry)
        day,_=workflow.read_day(self.root,DATE)
        self.assertEqual(day['kpis']['shadow']['eligible_ids'],[RACE])
        self.assertEqual([h['kpi_state'] for h in
                         day['races'][RACE]['shadow_history']],['NOT_APPLICABLE','ELIGIBLE'])

    def test_existing_initial_history_can_be_preserved_without_invented_applicability(self):
        path=self.register();gate=self.shadow_gate()
        self.entry['shadow_applicability']={'status':'APPLICABLE','reason':'旧初回',
                                            'item_ids':['TEST-SHADOW']}
        workflow.record_prediction(self.root,DATE,self.entry);self.select()
        legacy=json.loads(path.read_text())
        row=legacy['races'][RACE]
        row.pop('shadow_history');row.pop('shadow_tracking_version')
        path.write_text(json.dumps(legacy))
        self.final_without_shadow(gate)
        self.entry['shadow_applicability']={'status':'NOT_APPLICABLE',
            'reason':'最終対象外を個別判定','item_ids':[],
            'previous_item_dispositions':{
                'TEST-SHADOW':{'status':'NOT_APPLICABLE','reason':'最終時点で条件不成立'}}}
        workflow.record_prediction(self.root,DATE,self.entry)
        day,_=workflow.read_day(self.root,DATE)
        final=day['races'][RACE]
        self.assertEqual(len(final['prediction_history']),2)
        self.assertEqual(len(final['shadow_history']),1)
        self.assertEqual(final['shadow_history'][0]['phase'],'FINAL')
        self.assertEqual(day['kpis']['shadow']['target_ids'],[])

    def test_shadow_applicability_cannot_be_inferred_from_empty_gate(self):
        path=self.register();original=path.read_bytes()
        self.entry.pop('shadow_applicability')
        with self.assertRaisesRegex(ComplianceError,'explicit shadow applicability'):
            workflow.record_prediction(self.root,DATE,self.entry)
        self.assertEqual(path.read_bytes(),original)

    def test_repeated_final_gate_preserves_single_shadow_record(self):
        self.register();workflow.record_prediction(self.root,DATE,self.entry);self.select()
        self.entry['phase']='FINAL'
        workflow.record_prediction(self.root,DATE,self.entry)
        first=workflow.read_day(self.root,DATE)[0]['races'][RACE]['shadow_history']
        workflow.record_prediction(self.root,DATE,self.entry)
        after=workflow.read_day(self.root,DATE)[0]['races'][RACE]['shadow_history']
        self.assertEqual(first,after);self.assertEqual(len(after),2)
        self.entry['shadow_applicability']['reason']='後から別理由に変更'
        with self.assertRaisesRegex(ComplianceError,'same prediction gate'):
            workflow.record_prediction(self.root,DATE,self.entry)

    def test_partial_shadow_items_pending_do_not_mark_whole_race_eligible(self):
        from test_next_prediction_compliance import write
        self.register();gate=self.shadow_gate()
        gate['shadow_items'].append({'item_id':'TEST-PENDING','state':'AWAITING_EVIDENCE',
                                     'kpi_eligibility':'PENDING'})
        write(self.root,self.entry['prediction_gate_path'],json.dumps(gate))
        self.entry['shadow_applicability']={'status':'APPLICABLE','reason':'片方の証跡が保留',
                                          'item_ids':['TEST-SHADOW','TEST-PENDING']}
        workflow.record_prediction(self.root,DATE,self.entry)
        day,_=workflow.read_day(self.root,DATE)
        self.assertEqual(day['kpis']['shadow']['eligible_ids'],[])
        self.assertEqual(day['kpis']['shadow']['pending_ids'],[RACE])
        self.assertEqual(day['races'][RACE]['shadow_history'][0]['items'][1]['kpi_eligibility'],'PENDING')

    def test_shadow_record_and_latest_kpi_tampering_are_rejected(self):
        path=self.register();workflow.record_prediction(self.root,DATE,self.entry)
        original=path.read_bytes();day=json.loads(original)
        day['races'][RACE]['shadow_history'][0]['kpi_state']='ELIGIBLE'
        path.write_text(json.dumps(day))
        with self.assertRaisesRegex(ComplianceError,'shadow history evidence/state mismatch'):
            workflow.read_day(self.root,DATE)
        path.write_bytes(original)
        day=json.loads(original);day['races'][RACE]['shadow_history'][0]['prediction_gate_sha256']='0'*64
        path.write_text(json.dumps(day))
        with self.assertRaisesRegex(ComplianceError,'shadow history identity/hash mismatch'):
            workflow.read_day(self.root,DATE)

    def test_dropped_eligible_shadow_needs_individual_final_disposition(self):
        path=self.register();gate=self.shadow_gate()
        self.entry['shadow_applicability']={'status':'APPLICABLE','reason':'初回比較',
                                            'item_ids':['TEST-SHADOW']}
        workflow.record_prediction(self.root,DATE,self.entry);self.select()
        self.final_without_shadow(gate)
        self.entry['shadow_applicability']={'status':'NOT_APPLICABLE','reason':'最終では該当なし',
                                            'item_ids':[]}
        before=path.read_bytes()
        with self.assertRaisesRegex(ComplianceError,'removed shadow items need explicit dispositions'):
            workflow.record_prediction(self.root,DATE,self.entry)
        self.assertEqual(path.read_bytes(),before)

    def test_two_axis_comparison_uses_verified_recommendation_cancellations(self):
        from unittest.mock import patch
        self.register();self.select();self.entry['phase']='FINAL'
        verified=workflow.verify_recommendation(self.root,self.root/self.entry['recommendation_gate_path'])
        verified=copy.deepcopy(verified);verified['cancelled_horses']=[2]
        with patch.object(workflow,'verify_recommendation',return_value=verified), patch.object(workflow,'compare_two_axis',wraps=workflow.compare_two_axis) as compare:
            workflow.record_prediction(self.root,DATE,self.entry)
        self.assertEqual(compare.call_args.kwargs,{'cancelled_horses':[2]})

    def test_final_before_selection_is_rejected_without_ledger_write(self):
        path=self.register();original=path.read_bytes()
        self.entry['phase']='FINAL'
        with self.assertRaisesRegex(ComplianceError,'prior selected'):
            workflow.record_prediction(self.root,DATE,self.entry)
        self.assertEqual(path.read_bytes(),original)

    def test_scope_after_start_and_scope_overwrite_are_rejected(self):
        with self.assertRaisesRegex(ComplianceError,'after'):
            workflow.register_scope(self.root,self.scope,now=datetime.fromisoformat(POST))
        path=self.register();original=path.read_bytes()
        with self.assertRaisesRegex(ComplianceError,'already exists'):
            self.register()
        self.assertEqual(path.read_bytes(),original)

    def test_changed_fixed_prediction_cannot_replace_the_prior_ledger(self):
        path=self.register();workflow.record_prediction(self.root,DATE,self.entry)
        original=path.read_bytes();ref=self.entry['operations']['prediction_ref']
        p=self.root/ref['artifact_path'];p.write_text(p.read_text()+' ')
        with self.assertRaises(ComplianceError):
            workflow.record_prediction(self.root,DATE,self.entry)
        self.assertEqual(path.read_bytes(),original)

    def test_postrace_result_cannot_be_recorded_as_prerace_result(self):
        path=self.register();original=path.read_bytes()
        result={'race_id':RACE,'race_date_jst':DATE,'status':'OFFICIAL',
                'retrieved_at_jst':DATE+'T09:00:00+09:00'}
        write(self.root,'result.json',json.dumps(result))
        with self.assertRaisesRegex(ComplianceError,'before race'):
            workflow.review(self.root,DATE,{'race_id':RACE,'result_path':'result.json','review':{}})
        self.assertEqual(path.read_bytes(),original)

    def test_partial_official_result_cannot_produce_a_complete_review(self):
        path=self.register();workflow.record_prediction(self.root,DATE,self.entry)
        original=path.read_bytes()
        result={'race_id':RACE,'race_date_jst':DATE,'status':'OFFICIAL',
                'source_url':'https://www.jra.go.jp/test/result','retrieved_at_jst':DATE+'T11:00:00+09:00',
                'finish_groups':[[5],[2],[6]],'place_places':3}
        write(self.root,'result.json',json.dumps(result))
        with self.assertRaisesRegex(ComplianceError,'full-field result'):
            workflow.review(self.root,DATE,{'race_id':RACE,'result_path':'result.json',
                            'review':{'error_classification':'test','non_degradation':'test','next_validation':'test'}})
        self.assertEqual(path.read_bytes(),original)

    def test_initial_cannot_roll_back_completed_final(self):
        path=self.register();workflow.record_prediction(self.root,DATE,self.entry);self.select()
        self.entry['phase']='FINAL';workflow.record_prediction(self.root,DATE,self.entry)
        original=path.read_bytes();self.entry['phase']='INITIAL'
        with self.assertRaisesRegex(ComplianceError,'replace a completed FINAL'):
            workflow.record_prediction(self.root,DATE,self.entry)
        self.assertEqual(path.read_bytes(),original)

    def selected_ref(self,history,name):
        return self.fixture.artifact(name,'histories/'+name+'.json',history,at='09:44')

    def test_select_only_does_not_require_a_fixed_ticket_plan(self):
        self.register()
        history=json.loads((self.root/self.entry["operations"]["selection_ref"]["artifact_path"]).read_text());history['events']=history['events'][:1]
        ref=self.selected_ref(history,'select-only')
        workflow.select(self.root,DATE,{'race_id':RACE,'selection_ref':ref})
        day,_=workflow.read_day(self.root,DATE)
        self.assertEqual(day['selected_scope'],[RACE])
        self.assertEqual(day['final_scope'],[])

    def test_additional_request_preserves_prior_day_and_uses_new_race_deadline(self):
        self.register();workflow.record_prediction(self.root,DATE,self.entry)
        prior=copy.deepcopy(workflow.read_day(self.root,DATE)[0]['races'][RACE])
        extra=copy.deepcopy(self.scope)
        extra['races']=[{'race_id':'20261017-TOK-02','scheduled_post_time_jst':DATE+'T10:45:00+09:00'}]
        extra['observed_at_jst']=DATE+'T10:20:00+09:00'
        workflow.register_scope(self.root,extra,now=datetime.fromisoformat(DATE+'T10:21:00+09:00'),extend=True)
        day,_=workflow.read_day(self.root,DATE)
        self.assertEqual(day['races'][RACE],prior)
        self.assertEqual(len(day['initial_scope']),2)
        self.assertEqual(day['kpis']['production']['pending_ids'],['20261017-TOK-02'])
        with self.assertRaisesRegex(ComplianceError,'redefine'):
            workflow.register_scope(self.root,extra,now=datetime.fromisoformat(DATE+'T10:22:00+09:00'),extend=True)

    def test_deselection_retains_revision_history_and_allows_reselection(self):
        from selection_history import digest
        self.register()
        history=json.loads((self.root/self.entry["operations"]["selection_ref"]["artifact_path"]).read_text());history['events']=history['events'][:1]
        ref=self.selected_ref(history,'selection')
        workflow.select(self.root,DATE,{'race_id':RACE,'selection_ref':ref})
        event={'revision':2,'previous_sha256':digest({k:v for k,v in history['events'][0].items() if k!='evidence'}),
               'race_id':RACE,'purpose':'RECOMMENDATION','action':'DESELECT','selection_revision':1,
               'at':DATE+'T09:43:00+09:00','reason':'利用者の明示取消'}
        event['evidence']=self.fixture.artifact('deselect-event','events/deselect.json',event,at='09:44')
        history['events'].append(event)
        ref=self.selected_ref(history,'deselection')
        workflow.select(self.root,DATE,{'race_id':RACE,'selection_ref':ref})
        day,_=workflow.read_day(self.root,DATE)
        self.assertEqual(day['selected_scope'],[])
        self.assertEqual(len(day['races'][RACE]['selection_history']),2)
        old=self.selected_ref({'schema_version':'selection-history-v1','scheduled_posts':{RACE:POST},
                               'events':history['events'][:1]},'rollback')
        with self.assertRaisesRegex(ComplianceError,'roll back'):
            workflow.select(self.root,DATE,{'race_id':RACE,'selection_ref':old})
        core={'revision':3,'previous_sha256':digest({k:v for k,v in event.items() if k!='evidence'}),
              'race_id':RACE,'purpose':'RECOMMENDATION','action':'SELECT',
              'at':DATE+'T09:44:00+09:00','reason':'利用者の再選定'}
        evidence=self.fixture.artifact('reselect-event','events/reselect.json',core,at='09:45')
        history['events'].append({**core,'evidence':evidence})
        new=self.fixture.artifact('reselected','histories/reselected.json',history,at='09:46')
        workflow.select(self.root,DATE,{'race_id':RACE,'selection_ref':new})
        self.assertEqual(workflow.read_day(self.root,DATE)[0]['selected_scope'],[RACE])

    def test_final_cannot_use_a_different_selection_artifact(self):
        path=self.register();self.select();original=path.read_bytes()
        self.entry['phase']='FINAL'
        self.entry['operations']['selection_ref']=self.fixture.artifact('same-content-new-ref','histories/new.json',
                                                                       json.loads((self.root/self.entry["operations"]["selection_ref"]["artifact_path"]).read_text()),at='09:44')
        with self.assertRaisesRegex(ComplianceError,'latest selected'):
            workflow.record_prediction(self.root,DATE,self.entry)
        self.assertEqual(path.read_bytes(),original)

    def reviewed(self):
        path=self.register();workflow.record_prediction(self.root,DATE,self.entry);self.select()
        self.entry['phase']='FINAL';workflow.record_prediction(self.root,DATE,self.entry)
        result={'race_id':RACE,'race_date_jst':DATE,'status':'OFFICIAL','source_url':'https://www.jra.go.jp/test/result',
                'retrieved_at_jst':DATE+'T11:00:00+09:00','finish_groups':[[5],[2],[6],[4],[1],[3]],'place_places':3}
        write(self.root,'result.json',json.dumps(result))
        entry={'race_id':RACE,'result_path':'result.json',
               'review':{'error_classification':'test','non_degradation':'test','next_validation':'test'}}
        workflow.review(self.root,DATE,entry)
        return path,entry

    def test_review_and_reviewed_forecast_cannot_be_rewritten(self):
        path,entry=self.reviewed();original=path.read_bytes()
        with self.assertRaisesRegex(ComplianceError,'reviewed prediction is immutable'):
            workflow.record_prediction(self.root,DATE,self.entry)
        entry['review']['error_classification']='事後改変'
        with self.assertRaisesRegex(ComplianceError,'reviewed result is immutable'):
            workflow.review(self.root,DATE,entry)
        self.assertEqual(path.read_bytes(),original)

    def test_validator_recomputes_settlement_instead_of_trusting_the_ledger(self):
        path,_=self.reviewed();day=json.loads(path.read_text())
        day['races'][RACE]['recommendation_result']['hit_tickets']=99
        path.write_text(json.dumps(day))
        with self.assertRaisesRegex(ComplianceError,'settlement mismatch'):
            workflow.summary(self.root)

    def test_validator_rejects_partial_results_even_when_rehashed_in_the_ledger(self):
        import hashlib
        path,_=self.reviewed();day=json.loads(path.read_text())
        result_path=self.root/'result.json';result=json.loads(result_path.read_text())
        result['finish_groups']=result['finish_groups'][:3];result_path.write_text(json.dumps(result))
        day['races'][RACE]['result_ref']['sha256']=hashlib.sha256(result_path.read_bytes()).hexdigest()
        path.write_text(json.dumps(day))
        with self.assertRaisesRegex(ComplianceError,'full-field result'):
            workflow.summary(self.root)

    def test_empty_review_is_not_a_completed_review(self):
        path,_=self.reviewed();day=json.loads(path.read_text());day['races'][RACE]['review']={}
        path.write_text(json.dumps(day))
        with self.assertRaisesRegex(ComplianceError,'requires error'):
            workflow.summary(self.root)

    def test_writer_failure_and_concurrent_writer_preserve_the_prior_ledger(self):
        from unittest.mock import patch
        path=self.register();original=path.read_bytes()
        with patch('cycle04_workflow.os.replace',side_effect=OSError('simulated write failure')):
            with self.assertRaises(OSError):workflow.record_prediction(self.root,DATE,self.entry)
        self.assertEqual(path.read_bytes(),original)
        lock=path.with_suffix('.lock');lock.write_text('別writer')
        with self.assertRaisesRegex(ValueError,'writer already active'):
            workflow.record_prediction(self.root,DATE,self.entry)
        self.assertEqual(path.read_bytes(),original)
        self.assertTrue(lock.exists())
        lock.unlink()

    def test_writes_require_the_requested_daily_branch(self):
        import subprocess
        subprocess.run(['git','init','-q',str(self.root)],check=True)
        for branch in ('main','prediction/2026-10-18'):
            subprocess.run(['git','symbolic-ref','HEAD','refs/heads/'+branch],cwd=self.root,check=True)
            with self.assertRaisesRegex(ComplianceError,'matching prediction'):
                workflow.check_working_branch(self.root,DATE)
        subprocess.run(['git','symbolic-ref','HEAD','refs/heads/prediction/'+DATE],cwd=self.root,check=True)
        workflow.check_working_branch(self.root,DATE)

    def test_cancelled_field_does_not_create_false_losses_or_probability_scores(self):
        self.register();workflow.record_prediction(self.root,DATE,self.entry);self.select()
        self.entry['phase']='FINAL';workflow.record_prediction(self.root,DATE,self.entry)
        result={'race_id':RACE,'race_date_jst':DATE,'status':'OFFICIAL','source_url':'https://www.jra.go.jp/test/result',
                'retrieved_at_jst':DATE+'T11:00:00+09:00','finish_groups':[[2],[6],[4],[1],[3]],
                'scratched_horses':[5],'place_places':2}
        write(self.root,'result.json',json.dumps(result))
        workflow.review(self.root,DATE,{'race_id':RACE,'result_path':'result.json',
                        'review':{'error_classification':'取消','non_degradation':'比較不能','next_validation':'取消対応'}})
        summary=workflow.summary(self.root)
        self.assertEqual(summary['prediction_performance']['eligible_reviewed'],0)
        self.assertIsNone(summary['prediction_performance']['honmei_win'])
        self.assertEqual(summary['prediction_performance']['excluded_races'][0]['race_id'],RACE)
        self.assertEqual(summary['recommendation_performance']['eligible_settled'],0)

    def test_immutable_gate_history_detects_a_changed_initial_gate(self):
        path=self.register();workflow.record_prediction(self.root,DATE,self.entry)
        gate_path=self.root/self.entry['prediction_gate_path'];gate=json.loads(gate_path.read_text())
        gate['extra_untrusted_note']='事後追記';gate_path.write_text(json.dumps(gate))
        with self.assertRaisesRegex(ComplianceError,'history gate hash mismatch'):
            workflow.summary(self.root)

    def test_scope_registration_time_and_initial_scope_cannot_be_rewritten(self):
        path=self.register();day=json.loads(path.read_text())
        day['official_scope']['registered_at_jst']=POST;path.write_text(json.dumps(day))
        with self.assertRaisesRegex(ComplianceError,'scope/post registration'):
            workflow.summary(self.root)

    def test_stratified_and_initial_final_metrics_use_only_actual_reviewed_pairs(self):
        self.reviewed();summary=workflow.summary(self.root)
        metrics=summary['additional_review_metrics']
        self.assertEqual(metrics['reviewed_count'],1)
        self.assertEqual(metrics['by_prediction_confidence']['B']['count'],1)
        self.assertEqual(metrics['by_input_completeness']['INCOMPLETE']['honmei_win_rate'],1)
        self.assertEqual(metrics['by_race_period']['MORNING']['count'],1)
        self.assertEqual(metrics['initial_to_final']['paired'],1)
        self.assertEqual(metrics['initial_to_final']['unchanged_outcome'],1)
        self.assertEqual(summary['prediction_performance']['calibration']['win_probability'][2]['count'],1)

    def test_final_can_append_its_fixed_plan_to_the_prior_select_only_history(self):
        self.register();workflow.record_prediction(self.root,DATE,self.entry)
        history=json.loads((self.root/self.entry['operations']['selection_ref']['artifact_path']).read_text())
        history['events']=history['events'][:1]
        selected=self.selected_ref(history,'initial-select')
        workflow.select(self.root,DATE,{'race_id':RACE,'selection_ref':selected})
        self.entry['phase']='FINAL'
        workflow.record_prediction(self.root,DATE,self.entry)
        day,_=workflow.read_day(self.root,DATE)
        self.assertEqual(day['final_scope'],[RACE])
        self.assertEqual(len(day['races'][RACE]['selection_history']),2)

    def market_entry(self):
        market={'status':'ACQUIRED','decision':'POSITIVE_EV','reason':'独立市場評価','odds':3.0,'expected_value':.1,
                'attempted_at_jst':DATE+'T09:58:00+09:00','acquired_at_jst':DATE+'T09:59:00+09:00',
                'source_ref':'https://www.jra.go.jp/test/odds'}
        payload={'schema_version':'market-analysis-v1','race_id':RACE,'race_date_jst':DATE,
                 'data_cutoff':DATE+'T10:01:00+09:00','market':market}
        return {'race_id':RACE,'market_ref':self.fixture.artifact('market','markets/first.json',payload,at='10:02')}

    def test_optional_market_can_use_its_own_cutoff_without_changing_prediction(self):
        self.register();workflow.record_prediction(self.root,DATE,self.entry);self.select()
        self.entry['phase']='FINAL';workflow.record_prediction(self.root,DATE,self.entry)
        before=workflow.read_day(self.root,DATE)[0]['races'][RACE]
        workflow.record_market(self.root,DATE,self.market_entry())
        after=workflow.read_day(self.root,DATE)[0]
        self.assertEqual(after['kpis']['market']['eligible_ids'],[RACE])
        self.assertEqual(after['races'][RACE]['prediction_history'],before['prediction_history'])
        self.assertEqual(after['races'][RACE]['data_cutoff'],before['data_cutoff'])
        self.assertEqual(after['races'][RACE]['recommendation_gate_path'],before['recommendation_gate_path'])

    def test_optional_market_cannot_create_final_scope_or_replace_reviewed_data(self):
        path=self.register();original=path.read_bytes()
        with self.assertRaisesRegex(ComplianceError,'fixed FINAL'):
            workflow.record_market(self.root,DATE,self.market_entry())
        self.assertEqual(path.read_bytes(),original)
