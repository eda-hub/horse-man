"""第4サイクルの正常一巡/理由付き終了を合成scopeで回帰検査する。"""
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

    def reviewed_with_separate_initial_final_evidence(self):
        """writer経由で初回と最終の宣言/FIX原本を別々に固定する。"""
        workflow.record_prediction(self.root, DATES[0], self.case.entry)
        self.case.select()
        final_entry = json.loads(json.dumps(self.case.entry))
        final_entry['phase'] = 'FINAL'
        first_intent = final_entry['operations']['intent_ref']
        first_fix = final_entry['operations']['fix_ref']
        final_intent = self.case.fixture.artifact(
            'final-intent', f'docs/validation/persistence-intents/{DATES[0]}/final.json',
            json.loads((self.root / first_intent['artifact_path']).read_text()), at='09:39')
        final_manifest = json.loads((self.root / first_fix['artifact_path']).read_text())
        final_manifest['intent_ref'] = final_intent
        final_fix = self.case.fixture.artifact(
            'final-fix', f'docs/validation/fix-manifests/{DATES[0]}/final.json',
            final_manifest, at='09:56')
        final_entry['operations']['intent_ref'] = final_intent
        final_entry['operations']['fix_ref'] = final_fix
        workflow.record_prediction(self.root, DATES[0], final_entry)
        workflow.review(self.root, DATES[0], self.case.result_entry())
        day, _ = workflow.read_day(self.root, DATES[0])
        history = day['races'][self.case.entry['race_id']]['prediction_history']
        self.assertNotEqual(history[0]['intent_ref']['artifact_path'],
                            history[1]['intent_ref']['artifact_path'])
        self.assertNotEqual(history[0]['fix_ref']['artifact_path'],
                            history[1]['fix_ref']['artifact_path'])
        return day, history

    def test_deleted_initial_fix_is_reported_after_final_and_review(self):
        day, history = self.reviewed_with_separate_initial_final_evidence()
        self.assertFalse(any(x['code'] == 'PREDICTION_CHECK_PENDING' for x in
                             evaluate_days(self.root, [day])['issues']))
        (self.root / history[0]['fix_ref']['artifact_path']).unlink()
        result = evaluate_days(self.root, [day])
        self.assertTrue(any(x['code'] == 'PREDICTION_CHECK_PENDING' and
                            'INITIAL' in x['reason'] for x in result['issues']))
        self.assertFalse(result['stage_complete'])
        self.assertFalse(result['normal_cycle_complete'])
        self.assertIn('INITIALの独立保存/個別完了未確認',
                      str(workflow.summary(self.root)['completion']['issues']))

    def test_modified_initial_fix_is_not_replaced_by_latest_final(self):
        day, history = self.reviewed_with_separate_initial_final_evidence()
        target = self.root / history[0]['fix_ref']['artifact_path']
        target.write_text(target.read_text() + '\n', encoding='utf-8')
        result = evaluate_days(self.root, [day])
        self.assertIn('hash mismatch', str(result['issues']))
        self.assertIn('INITIAL', str(result['issues']))
        self.assertFalse(result['normal_cycle_complete'])
        self.assertIn('INITIAL', str(workflow.summary(self.root)['completion']['issues']))

    def test_deleted_initial_intent_is_not_replaced_by_latest_final(self):
        day, history = self.reviewed_with_separate_initial_final_evidence()
        (self.root / history[0]['intent_ref']['artifact_path']).unlink()
        result = evaluate_days(self.root, [day])
        self.assertIn('INITIAL', str(result['issues']))
        self.assertFalse(result['stage_complete'])
        # この合成fixtureでは最終推奨も初回宣言に結合しているため、
        # summaryの正式結果検査が先に拒否する。履歴不足の独立判定は上で確認済み。
        with self.assertRaisesRegex(ValueError, 'predeclaration'):
            workflow.summary(self.root)

    def test_missing_historical_fix_ref_stays_incomplete(self):
        day, history = self.reviewed_with_separate_initial_final_evidence()
        history[0].pop('fix_ref')
        result = evaluate_days(self.root, [day])
        self.assertIn('履歴固有', str(result['issues']))
        self.assertFalse(result['stage_complete'])

    def test_initial_receipt_order_cannot_be_repaired_by_final_receipt(self):
        day, history = self.reviewed_with_separate_initial_final_evidence()
        from check_prediction_compliance import receipt_records
        from test_next_prediction_compliance import write_receipts
        ref = history[0]['fix_ref']
        path = self.root / ref['receipt_path']
        records = receipt_records(path)
        for item in records:
            if item.get('receipt_id') == ref['receipt_id']:
                item['receipt_verified_at_jst'] = DATES[0] + 'T10:09:00+09:00'
        write_receipts(self.root, ref['receipt_path'], records)
        result = evaluate_days(self.root, [day])
        self.assertIn('INITIAL', str(result['issues']))
        self.assertFalse(result['stage_complete'])

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
        self.assertEqual(len(out['missing_dates']),len(DATES)-1)
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

    def test_normal_completion_requires_all_six_days_and_saved_summary(self):
        days=[]
        for date in DATES:
            race=date.replace('-','')+'-TOK-01'
            days.append({'race_date_jst':date,'initial_scope':[race],
                         'selected_scope':[race],'final_scope':[race],'reviewed_scope':[race],
                         'unfinished_reasons':{},
                         'races':{race:{'prediction_history':[{'phase':'INITIAL','prediction_ref':{}},
                                                               {'phase':'FINAL','prediction_ref':{}}],
                                        'recommendation_state':'NO_RECOMMENDATION',
                                        'result_ref':{'artifact_path':'fixed-result.json'},
                                        'review':{'error_classification':'確認','non_degradation':'維持',
                                                  'next_validation':'続行'}}},
                         'kpis':{'market':{'eligible_ids':[],'ineligible_ids':[], 'pending_ids':[], 'reasons':{}},'production':{'eligible_ids':[race],'ineligible_ids':[],
                                                'pending_ids':[],'reasons':{race:'確認'}},
                                 'recommendation':{'eligible_ids':[],'ineligible_ids':[race],
                                                   'pending_ids':[],'reasons':{race:'正常推奨なし'}},
                                 'shadow':{'eligible_ids':[],'ineligible_ids':[],
                                           'pending_ids':[race],'reasons':{race:'Shadow未測定'}}}})
        refs={'day_refs':[], 'summary_ref':None}
        with patch('cycle04_completion._prediction_check',return_value=[]), \
             patch('cycle04_completion._recommendation_check',return_value=[]), \
             patch('cycle04_completion.verify_summary_refs') as verifier:
            incomplete=evaluate_days(self.root,days)
            self.assertFalse(incomplete['normal_cycle_complete'])
            self.assertEqual(incomplete['state'],'終了審査待ち')
            completed=evaluate_days(self.root,days,frozen_refs=refs)
            self.assertTrue(completed['normal_cycle_complete'])
            self.assertEqual(completed['state'],'正常一巡完了')
            self.assertEqual(len(completed['shadow_gaps']),len(DATES))
            verifier.assert_called_once()

    def test_completion_cli_refuses_missing_stages_even_with_six_day_count(self):
        from check_cycle04 import main as checker_main
        from contextlib import redirect_stderr
        import io
        contract=json.loads((self.root/'docs/validation/contracts/cycle_04.json').read_text())
        with patch('check_cycle04.check_preparation',return_value=contract):
            with redirect_stderr(io.StringIO()) as errors:
                code=checker_main(['--root',str(self.root),'--require-complete'])
        self.assertEqual(code,1)
        self.assertIn('正常一巡未完了',errors.getvalue())

    def test_frozen_ref_rejects_stale_hash_before_git_readback(self):
        path=f'{workflow.DIRECTORY}/{DATES[0]}.json'
        ref={'artifact_path':path,'sha256':'0'*64,'git_commit':'a'*40}
        with patch('cycle04_completion.subprocess.run') as git:
            with self.assertRaisesRegex(ValueError,'hash'):
                verify_frozen_cycle(self.root,ref,allowed_prefix=workflow.DIRECTORY+'/')
            git.assert_not_called()

    def test_summary_scope_rejects_missing_or_substituted_day(self):
        from cycle04_completion import verify_summary_refs
        day,_=workflow.read_day(self.root,DATES[0])
        path=f'{workflow.DIRECTORY}/{DATES[0]}.json'
        ref={'artifact_path':path,'sha256':'0'*64,'git_commit':'a'*40}
        with self.assertRaisesRegex(ValueError,'件数'):
            verify_summary_refs(self.root,[day],{'day_refs':[],'summary_ref':ref})
        wrong={**ref,'artifact_path':f'{workflow.DIRECTORY}/{DATES[1]}.json'}
        with self.assertRaisesRegex(ValueError,'scope'):
            verify_summary_refs(self.root,[day],{'day_refs':[wrong],'summary_ref':ref})

    def test_completed_stages_still_require_summary_and_all_dates(self):
        self.assertFalse(self.evaluate()['normal_cycle_complete'])


if __name__=='__main__':
    unittest.main()
