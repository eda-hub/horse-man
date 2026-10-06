import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from contextlib import redirect_stdout, redirect_stderr
import io
import sys
sys.path.insert(0,str(Path(__file__).parent))

from check_prediction_compliance import ComplianceError
from verify_prediction_persistence import (
    check_intent, verify, declared_intent_paths, resolve_snapshot, snapshot_digest,
    main as persistence_main,
)


DATE='2026-10-04'
SNAP='20261004-WHOLE-S01'
RACES=['20261004-TOK-01','20261004-TOK-02']
JSON_DATE='2026-10-13'
JSON_RACE='20261013-TOK-01'
JSON_SNAP=JSON_RACE+'-P001-S01'
JSON_ARTIFACT=f'docs/validation/snapshots/{JSON_DATE}/{JSON_SNAP}.json'


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

    def json_intent(self, races=(JSON_RACE,)):
        intent={
            'schema_version':'prediction-persistence-intent-v1',
            'race_date_jst':JSON_DATE,
            'working_branch':f'prediction/{JSON_DATE}',
            'snapshot_id':JSON_SNAP,
            'required_race_ids':list(races),
            'deadline_jst':f'{JSON_DATE}T10:10:00+09:00',
            'artifact_path':JSON_ARTIFACT,
        }
        return write(
            self.root,
            f'docs/validation/persistence-intents/{JSON_DATE}/race1.json',
            json.dumps(intent),
        )

    def json_snapshot(self, race_id=JSON_RACE):
        payload={
            'schema_version':'prediction-snapshot-v2',
            'snapshot_id':JSON_SNAP,
            'race_id':race_id,
            'working_branch':f'prediction/{JSON_DATE}',
            'scheduled_post_time_jst':f'{JSON_DATE}T10:10:00+09:00',
            'manual_release':'v1.7.0',
            'manual_ref_commit':'b'*40,
            'baseline_forecast_id':JSON_RACE+'-P001',
            'data_cutoff':f'{JSON_DATE}T09:50:00+09:00',
            'ranking':[5,2,6],
            'marks':{'honmei':5,'taikou':2,'tanana':6,'renka':[]},
            'probabilities':[
                {'horse_no':5,'win_probability':0.22,'top2_probability':0.39,'top3_probability':0.53},
                {'horse_no':2,'win_probability':0.18,'top2_probability':0.34,'top3_probability':0.49},
                {'horse_no':6,'win_probability':0.14,'top2_probability':0.29,'top3_probability':0.43},
            ],
            'prediction_confidence':'B',
            'evidence_items':[],
            'fixed_at_jst':f'{JSON_DATE}T09:55:00+09:00',
        }
        return write(self.root,JSON_ARTIFACT,json.dumps(payload,ensure_ascii=False,sort_keys=True)+'\n')

    def json_receipt(self, artifact_path=JSON_ARTIFACT):
        return write(
            self.root,
            f'docs/validation/persistence-receipts/{JSON_DATE}.md',
            '## persistence_receipt\n'
            f'receipt_id: {JSON_SNAP}-R01\n'
            f'artifact_id: {JSON_SNAP}\n'
            f'artifact_path: {artifact_path}\n'
            'artifact_persist_status: PERSIST_VERIFIED\n'
            'receipt_persist_status: RECEIPT_VERIFIED\n'
            'timing_eligibility: PRE_RACE_ELIGIBLE\n'
            f'persist_verified_at_jst: {JSON_DATE}T09:56:00+09:00\n'
            f'receipt_verified_at_jst: {JSON_DATE}T09:57:00+09:00\n'
            f'scheduled_post_time_jst: {JSON_DATE}T10:10:00+09:00\n'
        )

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

    def test_json_snapshot_intent_scope_and_receipt_are_verified(self):
        intent=self.json_intent(); self.json_snapshot(); self.json_receipt()
        self.assertEqual(check_intent(self.root,intent),JSON_SNAP+'-R01')

    def test_json_snapshot_scope_mismatch_is_rejected(self):
        intent=self.json_intent(races=(JSON_RACE,'20261013-TOK-02'))
        self.json_snapshot(); self.json_receipt()
        with self.assertRaisesRegex(ComplianceError,'scope differs'):
            check_intent(self.root,intent)

    def test_json_snapshot_receipt_must_reference_same_artifact(self):
        intent=self.json_intent(); self.json_snapshot()
        self.json_receipt('docs/validation/snapshots/2026-10-13/other.json')
        with self.assertRaisesRegex(ComplianceError,'verified pre-race receipt missing'):
            check_intent(self.root,intent)

    def test_json_snapshot_direct_verification_works(self):
        self.json_snapshot(); self.json_receipt()
        self.assertEqual(verify(self.root,JSON_DATE,JSON_SNAP),JSON_SNAP+'-R01')

    def test_json_snapshot_task_complete_checks_exact_file_hash(self):
        self.json_intent(); self.json_snapshot(); self.json_receipt()
        digest=snapshot_digest(resolve_snapshot(self.root,JSON_DATE,JSON_SNAP,JSON_ARTIFACT))
        argv=[
            'verify_prediction_persistence.py','--root',str(self.root),
            '--date',JSON_DATE,'--snapshot-id',JSON_SNAP,
            '--task-complete','--intent-id','race1',
            '--fixed-content-sha256',digest,
        ]
        with patch.object(sys,'argv',argv), redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(persistence_main(),0)

        payload=json.loads((self.root/JSON_ARTIFACT).read_text(encoding='utf-8'))
        payload['ranking']=[2,5,6]
        write(self.root,JSON_ARTIFACT,json.dumps(payload,ensure_ascii=False,sort_keys=True)+'\n')
        with patch.object(sys,'argv',argv), redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(persistence_main(),1)

    def test_json_snapshot_without_intent_is_reported_by_audit(self):
        self.json_snapshot(); self.json_receipt()
        out=io.StringIO()
        argv=['verify_prediction_persistence.py','--root',str(self.root),'--audit','--date',JSON_DATE]
        with patch.object(sys,'argv',argv), redirect_stdout(out), redirect_stderr(io.StringIO()):
            self.assertEqual(persistence_main(),0)
        self.assertIn('NO_INTENT',out.getvalue())
        self.assertIn(JSON_SNAP,out.getvalue())


if __name__=='__main__': unittest.main()
