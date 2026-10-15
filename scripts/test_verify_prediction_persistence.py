import json
import tempfile
import unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).parent))

from check_prediction_compliance import ComplianceError
from verify_prediction_persistence import check_intent, verify, declared_intent_paths, snapshot_section, field


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

    def test_bulleted_snapshot_metadata_is_verified(self):
        # 2026-10-10 uses "- snapshot_id:" and "- working_branch:".
        self.snapshot()
        snapshot_file=self.root/'docs/validation/snapshots'/f'{DATE}.md'
        original=snapshot_file.read_text(encoding='utf-8')
        snapshot_file.write_text(original.replace('snapshot_id:', '- snapshot_id:')
                                 .replace('working_branch:', '- working_branch:'),
                                 encoding='utf-8')
        self.receipt()
        self.assertEqual(check_intent(self.root,self.path),SNAP+'-R02')

    def test_escaped_scope_fences_in_historical_snapshot(self):
        # Preserve the original bytes, including literal backslash-escaped fences.
        self.snapshot()
        path=self.root/'docs/validation/snapshots'/f'{DATE}.md'
        path.write_text(path.read_text(encoding='utf-8').replace('```', '\\`\\`\\`'), encoding='utf-8')
        self.receipt()
        self.assertEqual(check_intent(self.root,self.path), SNAP+'-R02')
    def test_mixed_bulleted_and_plain_fields(self):
        content=(f'## one\n- snapshot_id: {SNAP}\n'
                 f'working_branch: prediction/{DATE}\n')
        self.assertEqual(field(snapshot_section(content,SNAP),'working_branch'),
                         f'prediction/{DATE}')

    def test_duplicate_snapshot_ids_in_two_styles_are_rejected(self):
        content=(f'## first\nsnapshot_id: {SNAP}\n'
                 f'## second\n- snapshot_id: {SNAP}\n')
        with self.assertRaisesRegex(ComplianceError,'found 2'):
            snapshot_section(content,SNAP)

    def test_bulleted_snapshot_without_pre_race_receipt_remains_incomplete(self):
        self.snapshot()
        path=self.root/'docs/validation/snapshots'/f'{DATE}.md'
        path.write_text(path.read_text(encoding='utf-8')
                        .replace('snapshot_id:', '- snapshot_id:')
                        .replace('working_branch:', '- working_branch:'),
                        encoding='utf-8')
        self.receipt()
        receipt_path=self.root/'docs/validation/persistence-receipts'/f'{DATE}.md'
        receipt_path.write_text(
            receipt_path.read_text(encoding='utf-8').replace(
                'receipt_persist_status: RECEIPT_VERIFIED',
                'receipt_persist_status: RECEIPT_READBACK_PENDING'),
            encoding='utf-8')
        with self.assertRaisesRegex(ComplianceError,'verified pre-race receipt missing'):
            check_intent(self.root,self.path)

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

    def registered_races(self, first='10:00', second='10:30'):
        ledger = {
            'cycle_id': 'cycle_04', 'race_date_jst': DATE,
            'initial_scope': RACES,
            'races': {
                RACES[0]: {'scheduled_post_time_jst': f'{DATE}T{first}:00+09:00'},
                RACES[1]: {'scheduled_post_time_jst': f'{DATE}T{second}:00+09:00'}
            }
        }
        write(self.root, f'docs/validation/records/cycle_04/{DATE}.json',
              json.dumps(ledger))

    def test_multiple_races_share_receipt_deadline_not_official_post(self):
        self.snapshot()
        self.receipt()
        self.registered_races()
        self.assertEqual(verify(self.root, DATE, SNAP), SNAP+'-R02')

    def test_multiple_races_reject_readback_after_individual_post(self):
        self.snapshot()
        self.receipt()
        self.registered_races(first='09:40')
        with self.assertRaisesRegex(ComplianceError, 'cannot rehabilitate late/replay'):
            verify(self.root, DATE, SNAP)

    def test_direct_verification_works_without_intent(self):
        self.snapshot(); self.receipt()
        self.assertEqual(verify(self.root,DATE,SNAP),SNAP+'-R02')

    def test_failed_attempts_are_excluded_from_active_audit(self):
        failed=write(self.root,'docs/validation/persistence-intents/failed-attempts/legacy.json','{}')
        self.assertNotIn(failed,declared_intent_paths(self.root/'docs/validation/persistence-intents'))
        self.assertIn(self.path,declared_intent_paths(self.root/'docs/validation/persistence-intents'))


if __name__=='__main__': unittest.main()
