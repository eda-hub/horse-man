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
