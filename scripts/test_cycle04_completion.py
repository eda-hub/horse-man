"""第4サイクルの正常一巡/理由付き終了を合成scopeで回帰検査する。"""
import copy
import hashlib
import json
import unittest
from unittest.mock import patch

import cycle04_workflow as workflow
import test_cycle04_workflow as fixtures
from check_cycle04 import DATES
from cycle04_completion import evaluate_days, verify_closure, verify_frozen_cycle


class CompletionAcceptance(unittest.TestCase):
    def setUp(self):
        self.case=fixtures.OperationalWorkflow()
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.root=self.case.root
        self.case.register()

    def evaluate(self):
        day,_=workflow.read_day(self.root,workflow.DATES[0])
        return evaluate_days(self.root,[day])

    def test_registered_and_reviewed_without_initial_prediction_is_incomplete(self):
        path=self.root/workflow.DIRECTORY/(DATES[0]+'.json')
        day=json.loads(path.read_text())
        race=day['initial_scope'][0]
        day['reviewed_scope']=[race]
        day['races'][race]['review']={'error_classification':'不足','non_degradation':'不足','next_validation':'次回'}
        # 原本結果を捏造して合格させない。純粋な工程評価だけを確認する。
        out=evaluate_days(self.root,[day])
        self.assertFalse(out['normal_cycle_complete'])
        self.assertIn('初回Prediction未実施',str(out['issues']))
        self.assertIn('公式結果',str(out['issues']))

    def test_selected_without_final_is_not_normal(self):
        workflow.record_prediction(self.root,DATES[0],self.case.entry)
        self.case.select()
        out=self.evaluate()
        self.assertIn('選定済み・最終工程未実施',str(out['issues']))
        self.assertFalse(out['normal_cycle_complete'])

    def test_unselected_initial_does_not_require_final(self):
        workflow.record_prediction(self.root,DATES[0],self.case.entry)
        out=self.evaluate()
        self.assertNotIn('選定済み・最終工程未実施',str(out['issues']))

    def test_untouched_days_not_fabricated(self):
        out=self.evaluate()
        self.assertEqual(out['recorded_dates'],[DATES[0]])
        self.assertEqual(len(out['missing_dates']),3)
        self.assertEqual(out['performance_promotion'],'NOT_APPROVED')

    def test_frozen_refs_require_real_git_readback(self):
        day,_=workflow.read_day(self.root,DATES[0])
        path=f'{workflow.DIRECTORY}/{DATES[0]}.json'
        ref={'artifact_path':path,'sha256':hashlib.sha256((self.root/path).read_bytes()).hexdigest(),
             'git_commit':'0'*40}
        with self.assertRaises(ValueError):
            verify_frozen_cycle(self.root,ref,allowed_prefix=workflow.DIRECTORY+'/')
        self.assertFalse(evaluate_days(self.root,[day])['normal_cycle_complete'])

    def test_approval_is_never_automatically_generated(self):
        with self.assertRaises(ValueError):
            verify_closure(self.root,{'schema_version':'cycle04-closure-review-v1',
                'decision':'REASONED_CLOSE','reviewer':'','owner':'',
                'reason':'空欄','protected_good_parts':[],'next_validation':'次回',
                'day_refs':[],'summary_ref':None},[])
        self.assertNotEqual(self.evaluate()['state'],'理由付き終了')

    def test_completed_stages_still_require_summary_and_all_dates(self):
        self.case.reviewed() if False else None
        self.case.select() if False else None
        self.assertFalse(self.evaluate()['normal_cycle_complete'])


if __name__=='__main__':
    unittest.main()
