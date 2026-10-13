import copy
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import test_task_completion as fixtures
import test_recommendation as rec
from chat_resume import inspect


class Resume(unittest.TestCase):
    def fixture(self):
        helper=fixtures.TaskCompletionTests();self.addCleanup(helper.doCleanups)
        root,p,digest,rg,rp,rh=helper.fixture()
        request={'schema_version':'chat-resume-request-v1','date':rec.DATE,'snapshot_id':p['snapshot_id'],
                 'phase':'INITIAL','scheduled_post_time_jst':p['scheduled_post_time_jst'],
                 'intent_id':'first','fixed_content_sha256':digest,
                 'prediction_gate_path':f'docs/validation/execution-gates/{rec.DATE}/{rec.RACE}.json'}
        return root,request

    def test_saved_prediction_skips_completed_checks_without_writing(self):
        root,request=self.fixture()
        before={str(p):p.read_bytes() for p in root.rglob('*') if p.is_file()}
        r=inspect(root,request,datetime.fromisoformat(rec.DATE+'T09:59:00+09:00'))
        self.assertTrue(r['prediction']['complete']);self.assertFalse(r['ledger_registered'])
        self.assertEqual(r['next_check'],'日別台帳と固定参照の照合')
        self.assertEqual(before,{str(p):p.read_bytes() for p in root.rglob('*') if p.is_file()})

    def test_unrecorded_fix_hash_stays_unchecked_and_deadline_stops_retry(self):
        root,request=self.fixture();request.pop('fixed_content_sha256')
        r=inspect(root,request,datetime.fromisoformat(rec.DATE+'T12:00:00+09:00'))
        self.assertFalse(r['prediction']['complete']);self.assertTrue(r['deadline_reached'])
        self.assertFalse(r['automatic_retry']);self.assertFalse(r['formal_kpi_certified'])

    def test_final_without_recommendation_is_not_complete_and_wrong_post_rejected(self):
        root,request=self.fixture();request['phase']='FINAL'
        r=inspect(root,request,datetime.fromisoformat(rec.DATE+'T09:59:00+09:00'))
        self.assertIn('推奨',r['next_check'])
        request['scheduled_post_time_jst']=rec.DATE+'T11:00:00+09:00'
        with self.assertRaises(ValueError):inspect(root,request)

    def test_future_receipts_are_not_current_completion(self):
        root,request=self.fixture()
        r=inspect(root,request,datetime.fromisoformat('2026-10-14T09:00:00+09:00'))
        self.assertTrue(r['temporal_evidence_unverified'])
        self.assertFalse(r['prediction_complete_at_current_time'])
        self.assertFalse(r['automatic_retry'])


if __name__=='__main__':unittest.main()
