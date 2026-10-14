"""2開催の合成受入は実測に数えず、真正な保存参照の要件と拒否境界を検査する。"""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import check_market_live_validation as live
import market_acquisition as acquisition
from test_jvlink_market import record, native_request
from test_market_acquisition import Clock
import test_cycle04_acceptance as fixtures
from check_prediction_compliance import receipt_records


class LiveValidationTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.Cycle04Acceptance(); self.fixture.addCleanup=self.addCleanup; self.fixture.setUp()
        self.root=self.fixture.root
        self.manifest={'schema_version':'market-live-validation-v1','entries':[]}
        self.fixed={}
        self.scopes={}

    def entry(self,date,alternate=False):
        req=native_request(date=date,alternate=alternate); clock=Clock()
        clock.value=clock.value.replace(day=int(date[-2:]))
        folder='live/'+date+('/specific' if alternate else '/whole')
        payload,raws=acquisition.collect(req,folder,fetch=lambda url,timeout:(0,record(date=date),True,None),
                                         now=clock.now,sleep=clock.sleep)
        acquisition.save(self.root,folder,payload,raws)
        ident=date+('-specific' if alternate else '-whole')
        # 合成receiptの日時をfixtureの対象日へ合わせる。実レース証跡は作らない。
        ref=self.fixture.artifact(ident,folder+'/analysis.json',payload,at='09:01')
        original=receipt_records(self.root/ref['receipt_path'])
        receipt=[r for r in original if r.get('receipt_id')==ref['receipt_id']][0]
        for name,value in list(receipt.items()):
            if name.endswith('_jst') and isinstance(value,str):
                receipt[name]=value.replace('2026-10-17',date)
        ref['receipt_path']=folder+'/receipt.md'
        rp=self.root/ref['receipt_path']
        fence=chr(96)*3
        rp.write_text(fence+'persistence-receipt-v1\n'+json.dumps(receipt)+'\n'+fence+'\n')
        commit=('a' if not alternate else 'b')*40
        if date.endswith('18'): commit='c'*40
        paths=[ref['artifact_path'],ref['receipt_path']]+list(raws)
        for path in paths: self.fixed[(commit,path)]=(self.root/path).read_bytes()
        self.fixed[(commit,'time')]=(date+'T09:02:00+09:00\n').encode()
        scope={'initial_scope':[req['race_id']],'races':{req['race_id']:{
            'scheduled_post_time_jst':req['scheduled_post_time_jst']}}}
        self.scopes[date]=scope
        entry={'market_ref':ref,'commit_sha':commit}; self.manifest['entries'].append(entry)
        return entry,payload

    def git(self,root,*args):
        if args[:2]==('show','-s'): return self.fixed[(args[-1],'time')]
        commit,path=args[1].split(':',1); return self.fixed[(commit,path)]

    def check(self):
        with patch('check_market_live_validation.git',side_effect=self.git), patch(
                'cycle04_workflow.read_day',side_effect=lambda root,date:(self.scopes[date],b'')):
            return live.check(self.root,self.manifest)

    def test_empty_and_one_meeting_stay_in_continuation(self):
        self.assertEqual(self.check()['status'],'CONTINUE_VALIDATION')
        self.entry('2026-10-17')
        self.assertEqual(self.check()['status'],'CONTINUE_VALIDATION')

    def test_two_meetings_and_both_live_source_specs_can_pass_contract_only(self):
        self.entry('2026-10-17'); self.entry('2026-10-18',True)
        result=self.check()
        self.assertEqual(result['status'],'PASS')
        self.assertFalse(result['performance_promoted'])

    def test_two_meetings_with_only_primary_does_not_close_fallback(self):
        self.entry('2026-10-17'); self.entry('2026-10-18')
        self.assertEqual(self.check()['status'],'CONTINUE_VALIDATION')

    def test_replayed_or_synthetic_acquisition_is_not_counted(self):
        entry,p=self.entry('2026-10-17')
        path=self.root/entry['market_ref']['artifact_path']
        p['mode']='SYNTHETIC'; path.write_text(json.dumps(p))
        # hash更新で独立原本照合を回避してもmodeの拒否は消えない。
        from unittest.mock import patch
        with patch('check_market_live_validation.verified_artifact',return_value=(p,{})):
            with self.assertRaisesRegex(ValueError,'forward evidence'): self.check()

    def test_late_git_fixation_cannot_count(self):
        entry,p=self.entry('2026-10-17')
        self.fixed[(entry['commit_sha'],'time')]=(p['market']['acquisition']['request']['scheduled_post_time_jst']+'\n').encode()
        with self.assertRaisesRegex(ValueError,'Git fixation'): self.check()

    def test_changed_raw_and_missing_scope_are_rejected(self):
        entry,p=self.entry('2026-10-17')
        self.scopes['2026-10-17']['initial_scope']=[]
        with self.assertRaisesRegex(ValueError,'scope'): self.check()
        self.scopes['2026-10-17']['initial_scope']=[p['race_id']]
        path=p['market']['acquisition']['attempts'][0]['response_ref']['artifact_path']
        (self.root/path).write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'hash/size'): self.check()

    def test_fixed_git_receipt_must_match_original_record(self):
        entry,p=self.entry('2026-10-17')
        key=(entry['commit_sha'],entry['market_ref']['receipt_path'])
        self.fixed[key]=self.fixed[key].replace(b'RECEIPT_VERIFIED',b'RECEIPT_FAILED')
        with self.assertRaisesRegex(ValueError,'receipt mismatch'): self.check()
