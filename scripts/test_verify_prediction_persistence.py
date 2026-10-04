import json
import tempfile
import unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).parent))

from check_prediction_compliance import ComplianceError
from verify_prediction_persistence import check_intent, verify, declared_intent_paths


DATE='2026-10-04'
SNAP='20261004-WHOLE-S01'
RACES=['20261004-TOK-01','20261004-TOK-02']


def write(root,relative,text):
    path=root/relative
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(text,encoding='utf-8')
    return path


class PersistenceTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.intent={
            'schema_version':'prediction-persistence-intent-v1',
            'race_date_jst':DATE,'working_branch':f'prediction/{DATE}',
            'snapshot_id':SNAP,'required_race_ids':RACES,
            'deadline_jst':f'{DATE}T09:50:00+09:00'
        }
        self.path=write(self.root,f'docs/validation/persistence-intents/{DATE}/morning.json',json.dumps(self.intent))

    def snapshot(self,races=RACES):
        return write(self.root,f'docs/validation/snapshots/{DATE}.md',
            f'## all races\nsnapshot_id: {SNAP}\nworking_branch: prediction/{DATE}\n'
            f'```prediction-scope-v1\n{json.dumps({"race_ids":races})}\n```\n')

    def receipt(self,receipt_verified=f'{DATE}T09:42:00+09:00'):
        return write(self.root,f'docs/validation/persistence-receipts/{DATE}.md',
            '## persistence_receipt\n'
            f'receipt_id: {SNAP}-R02\nartifact_id: {SNAP}\n'
            f'artifact_path: docs/validation/snapshots/{DATE}.md\n'
            'artifact_persist_status: PERSIST_VERIFIED\nreceipt_persist_status: RECEIPT_VERIFIED\n'
            'timing_eligibility: PRE_RACE_ELIGIBLE\n'
            f'persist_verified_at_jst: {DATE}T09:41:00+09:00\n'
            f'receipt_verified_at_jst: {receipt_verified}\n'
            f'scheduled_post_time_jst: {DATE}T09:50:00+09:00\n')

    def test_intent_catches_snapshot_never_created(self):
        with self.assertRaisesRegex(ComplianceError,'snapshot file missing'): check_intent(self.root,self.path)

    def test_intent_catches_receipt_never_created(self):
        self.snapshot()
        with self.assertRaisesRegex(ComplianceError,'receipt file missing'): check_intent(self.root,self.path)

    def test_intent_catches_incomplete_race_scope(self):
        self.snapshot(RACES[:1]); self.receipt()
        with self.assertRaisesRegex(ComplianceError,'scope differs'): check_intent(self.root,self.path)

    def test_intent_checks_pre_race_readback(self):
        self.snapshot(); self.receipt()
        self.assertEqual(check_intent(self.root,self.path),SNAP+'-R02')

    def test_late_receipt_is_not_pre_race_verified(self):
        self.snapshot(); self.receipt(f'{DATE}T09:51:00+09:00')
        with self.assertRaisesRegex(ComplianceError,'after deadline'): check_intent(self.root,self.path)

    def test_direct_verification_works_without_intent(self):
        self.snapshot(); self.receipt()
        self.assertEqual(verify(self.root,DATE,SNAP),SNAP+'-R02')

    def test_failed_attempts_are_excluded_from_active_audit(self):
        failed=write(self.root,'docs/validation/persistence-intents/failed-attempts/legacy.json','{}')
        self.assertNotIn(failed,declared_intent_paths(self.root/'docs/validation/persistence-intents'))
        self.assertIn(self.path,declared_intent_paths(self.root/'docs/validation/persistence-intents'))


if __name__=='__main__': unittest.main()
