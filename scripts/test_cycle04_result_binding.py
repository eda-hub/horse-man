"""回顧前固定の上書き、両参照の不一致、正規の結果訂正と旧原票保全を検査。"""
import copy
import json
import unittest
from datetime import datetime
from pathlib import Path

import test_cycle04_workflow as operations
from test_cycle04_workflow import workflow, DATE, RACE
from cycle04_daily_audit import audit_days
from cycle04_operations import fingerprint
from cycle04_result_binding import verify_result_bindings
from cycle04_review_metrics import REVISION_SCHEMA

class ResultBindingTest(unittest.TestCase):
    def setUp(self):
        self.case=operations.OperationalWorkflow();self.case.setUp();self.addCleanup(self.case.doCleanups)
        self.root=self.case.root
        self.case.register();workflow.record_prediction(self.root,DATE,self.case.entry);self.case.select()
        self.case.entry['phase']='FINAL';workflow.record_prediction(self.root,DATE,self.case.entry)
        self.entry=self.case.result_entry()
        self.now=datetime.fromisoformat(DATE+'T12:00:00+09:00')
        workflow.request_review(self.root,DATE,self.entry,now=self.now)
        self.day_path=self.root/workflow.DIRECTORY/(DATE+'.json')
    def day(self):return workflow.read_day(self.root,DATE)[0]
    def freeze(self,path,data):
        raw=(json.dumps(data,ensure_ascii=False,indent=2)+'\n').encode()
        dest=self.root/path;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw)
        return {'artifact_path':path,'sha256':fingerprint(raw)}
    def corrected_entry(self):
        originals={p:p.read_bytes() for p in (self.root/'result-audit').glob('*.json')}
        try:
            entry=self.case.result_entry(scratched=(3,))
            manifest=json.loads((self.root/entry['result_reconciliation_ref']['artifact_path']).read_text())
            for name in ('capture','conversion','result'):
                data=json.loads((self.root/manifest['refs'][name]['artifact_path']).read_text())
                manifest['refs'][name]=self.freeze('result-audit-corrected/'+name+'.json',data)
            entry['result_path']=manifest['refs']['result']['artifact_path']
            entry['result_reconciliation_ref']=self.freeze('result-audit-corrected/manifest.json',manifest)
            return entry
        finally:
            for p,raw in originals.items():p.write_bytes(raw)
    def correction(self,entry,**changes):
        row=self.day()['races'][RACE]
        old={'result_ref':row['result_ready_ref'],'reconciliation_ref':row['result_ready_reconciliation_ref']}
        new={'result_ref':{'artifact_path':entry['result_path'], 'sha256':fingerprint((self.root/entry['result_path']).read_bytes())},
             'reconciliation_ref':entry['result_reconciliation_ref']}
        doc={'schema_version':'cycle04-result-correction-v1','race_id':RACE,'race_date_jst':DATE,
             'revision':1,'previous_sha256':None,'from':old,'to':new,'reason':'公式結果の取消訂正を確認',
             'recorded_at_jst':DATE+'T11:30:00+09:00'}
        doc.update(changes)
        entry['result_correction_ref']=self.freeze(f'docs/validation/result-corrections/{DATE}/{RACE}/R01.json',doc)
        return doc
    def test_request_is_idempotent_but_cannot_rebind_manifest_only(self):
        before=self.day_path.read_bytes()
        workflow.request_review(self.root,DATE,self.entry,now=self.now)
        self.assertEqual(self.day_path.read_bytes(),before)
        entry=copy.deepcopy(self.entry)
        data=json.loads((self.root/entry['result_reconciliation_ref']['artifact_path']).read_text())
        entry['result_reconciliation_ref']=self.freeze('other-manifest.json',data)
        with self.assertRaises(ValueError):workflow.request_review(self.root,DATE,entry,now=self.now)
        self.assertEqual(self.day_path.read_bytes(),before)
    def test_result_or_manifest_overwrite_is_rejected_before_and_after_review(self):
        for reviewed in (False,True):
            if reviewed:workflow.review(self.root,DATE,self.entry)
            for path in (self.entry['result_path'],self.entry['result_reconciliation_ref']['artifact_path']):
                p=self.root/path;raw=p.read_bytes();before=self.day_path.read_bytes()
                try:
                    p.write_bytes(raw+b' ')
                    with self.assertRaises(ValueError):workflow.review(self.root,DATE,self.entry)
                    with self.assertRaises(ValueError):audit_days(self.root,[json.loads(before)],now=self.now)
                    self.assertEqual(self.day_path.read_bytes(),before)
                finally:p.write_bytes(raw)
    def test_choosing_current_reference_does_not_hide_old_fixed_hash(self):
        workflow.review(self.root,DATE,self.entry)
        day=self.day();row=day['races'][RACE]
        p=self.root/self.entry['result_path'];raw=p.read_bytes();p.write_bytes(raw+b' ')
        row['result_ref']['sha256']=fingerprint(p.read_bytes())
        with self.assertRaises(ValueError):audit_days(self.root,[day],now=self.now)
    def test_two_valid_but_different_refs_are_not_silently_prioritized(self):
        workflow.review(self.root,DATE,self.entry)
        day=self.day();entry=self.corrected_entry();row=day['races'][RACE]
        row['result_ref']={'artifact_path':entry['result_path'],
                           'sha256':fingerprint((self.root/entry['result_path']).read_bytes())}
        row['result_reconciliation_ref']=entry['result_reconciliation_ref']
        with self.assertRaisesRegex(ValueError,'不一致'):
            audit_days(self.root,[day],now=self.now)
    def test_correction_cannot_reuse_original_paths(self):
        entry=self.corrected_entry();old=self.day()['races'][RACE]
        self.correction(entry,to={'result_ref':old['result_ready_ref'],
                                 'reconciliation_ref':old['result_ready_reconciliation_ref']})
        before=self.day_path.read_bytes()
        with self.assertRaises(ValueError):workflow.review(self.root,DATE,entry)
        self.assertEqual(self.day_path.read_bytes(),before)
    def test_new_result_requires_explicit_correction_then_keeps_originals(self):
        entry=self.corrected_entry();before=self.day_path.read_bytes()
        with self.assertRaisesRegex(ValueError,'明示的'):workflow.review(self.root,DATE,entry)
        self.assertEqual(self.day_path.read_bytes(),before)
        self.correction(entry);workflow.review(self.root,DATE,entry)
        report=audit_days(self.root,[self.day()],now=self.now)
        self.assertEqual(report['state'],'COMPLETE')
        row=self.day()['races'][RACE]
        self.assertNotEqual(row['result_ref'],row['result_ready_ref'])
        self.assertEqual(len(row['result_correction_history']),1)
        p=self.root/row['result_ready_reconciliation_ref']['artifact_path'];p.write_bytes(p.read_bytes()+b' ')
        with self.assertRaises(ValueError):verify_result_bindings(self.root,row,RACE,DATE,now=self.now)
    def test_postreview_result_correction_also_requires_review_revision(self):
        workflow.review(self.root,DATE,self.entry)
        row=self.day()['races'][RACE];entry=self.corrected_entry();self.correction(entry)
        with self.assertRaises(ValueError):workflow.review(self.root,DATE,entry)
        entry['review']['error_classification']='公式結果訂正を反映した回顧'
        entry['revision_ref']=self.freeze(f'docs/validation/review-revisions/{DATE}/{RACE}/R02.json',{
            'schema_version':REVISION_SCHEMA,'race_date_jst':DATE,'race_id':RACE,'revision':2,
            'supersedes_sha256':row['review_history'][-1]['sha256'],'review':entry['review']})
        workflow.review(self.root,DATE,entry)
        self.assertEqual(audit_days(self.root,[self.day()],now=self.now)['state'],'COMPLETE')
    def test_malformed_correction_never_updates_day(self):
        entry=self.corrected_entry();before=self.day_path.read_bytes()
        for changes in ({'previous_sha256':'0'*64},{'reason':''},{'revision':2},
                        {'recorded_at_jst':'2099-01-01T00:00:00+09:00'}, {'from':{}}):
            with self.subTest(changes=changes):
                self.correction(entry,**changes)
                with self.assertRaises(ValueError):workflow.review(self.root,DATE,entry)
                self.assertEqual(self.day_path.read_bytes(),before)

if __name__=='__main__':unittest.main()
