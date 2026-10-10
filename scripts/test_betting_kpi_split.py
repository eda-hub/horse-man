import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from check_betting_performance import CONTRACT, snapshot_tickets, tickets_hash, validate_source
from check_cycle03 import validate_day
from check_prediction_compliance import cycle_links, ComplianceError
import test_verify_prediction_persistence as persistence_tests
from test_verify_prediction_persistence import DATE, SNAP
from verify_prediction_persistence import main, snapshot_section


class PerformanceSources(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.race = 'race-a'
        self.write('snap.md', '## final\nsnapshot_id: snap-a\n| 単勝 | 1 | 10,000円 |\n')
        self.tickets = snapshot_tickets(self.root, 'snap.md', 'snap-a')
        raw = json.dumps({'race_id': self.race, 'source_sent_at_jst': '2026-10-03T12:00:00+09:00',
                          'tickets': self.tickets}).encode()
        (self.root / 'original.json').write_bytes(raw)
        self.ref = {'source_type': 'CHAT_PRE_RACE_FIXED', 'source_ref': 'https://chatgpt.com/c/conversation',
                    'source_path': 'source.json', 'working_branch': 'prediction/2026-10-03'}
        self.source = {**self.ref, 'schema_version': 'fixed-plan-source-v1', 'race_id': self.race,
                       'verification_status': 'VERIFIED', 'message_id': 'message-a',
                       'source_sent_at_jst': '2026-10-03T12:00:00+09:00',
                       'scheduled_post_time_jst': '2026-10-03T12:30:00+09:00',
                       'result_checked_at_jst': '2026-10-03T13:00:00+09:00',
                       'original_path': 'original.json', 'original_sha256': hashlib.sha256(raw).hexdigest(),
                       'snapshot_path': 'snap.md', 'snapshot_id': 'snap-a',
                       'tickets_sha256': tickets_hash(self.tickets),
                       'verified_by': 'reviewer', 'verification_note': 'original message inspected'}

    def write(self, path, text):
        (self.root / path).write_text(text, encoding='utf-8')

    def verify(self):
        self.write('source.json', json.dumps(self.source))
        return validate_source(self.root, self.ref, self.race)


    def test_snapshot_tickets_reads_virtual_bullet_plan_only(self):
        self.write('snap.md',
                   '## final\nsnapshot_id: snap-a\n'
                   '### 検証用仮想購入（正式帳簿）\n'
                   '- 馬連 1-2: 6,000円\n'
                   '- 複勝 3: 4,000円\n'
                   '### 実購入提案\n'
                   '- 馬連 1-2: 500円\n')
        tickets = snapshot_tickets(self.root, 'snap.md', 'snap-a')
        self.assertEqual(sum(x['stake_yen'] for x in tickets), 10000)
        self.assertEqual(len(tickets), 2)

    def test_chat_fixed_plan_does_not_require_git_receipt(self):
        self.verify()

    def test_synthetic_reference_and_unknown_type_rejected(self):
        self.ref['source_type'] = 'UNKNOWN'
        with self.assertRaisesRegex(ValueError, 'unknown'): self.verify()
        self.ref['source_type'] = self.source['source_type']
        self.ref['source_ref'] = self.source['source_ref'] = 'chat-fixed:snap-a'
        with self.assertRaisesRegex(ValueError, 'conversation'): self.verify()

    def test_result_after_reconstruction_and_late_fix_rejected(self):
        self.source['source_sent_at_jst'] = self.source['scheduled_post_time_jst']
        with self.assertRaisesRegex(ValueError, 'before race'): self.verify()

    def test_ticket_amount_change_rejected(self):
        self.write('snap.md', '## final\nsnapshot_id: snap-a\n| 単勝 | 1 | 9,000円 |\n')
        with self.assertRaisesRegex(ValueError, 'tickets differ'): self.verify()

    def test_original_tampering_rejected(self):
        self.write('original.json', '{}')
        with self.assertRaisesRegex(ValueError, 'hash mismatch'): self.verify()

    def test_git_source_requires_immutable_commit(self):
        self.ref['source_type'] = self.source['source_type'] = 'GIT_PRE_RACE_SNAPSHOT'
        self.ref['source_ref'] = self.source['source_ref'] = 'https://github.com/eda-hub/horse-man/blob/main/snap.md'
        with self.assertRaisesRegex(ValueError, 'immutable'): self.verify()
        self.ref['source_ref'] = self.source['source_ref'] = 'https://github.com/eda-hub/horse-man/blob/' + 'a'*40 + '/snap.md'
        self.verify()


def split_day():
    empty = dict(target_ids=['race-a'], eligible_ids=[], ineligible_ids=[],
                 pending_ids=['race-a'], evidence_refs={}, stake_yen=None, return_yen=None)
    return {'cycle_id': 'cycle_03', 'race_date_jst': '2026-10-03', 'kpi_contract': CONTRACT,
            'initial_scope': ['race-a'], 'validation_candidates': ['race-a'], 'purchase_candidates': ['race-a'],
            'final_completed_scope': ['race-a'], 'reviewed_scope': ['race-a'], 'unreviewed_scope': [],
            'kpis': {name: copy.deepcopy(empty) for name in ('production', 'shadow', 'betting', 'betting_rules', 'betting_evidence')},
            'fixed_plan_settlement': {'stake_yen': 10000, 'return_yen': 2050, 'races': {
                'race-a': {'snapshot_path': 'snap.md', 'snapshot_id': 'snap-a', 'stake_yen': 10000,
                           'return_yen': 2050, 'source_verification': 'PENDING'}}}}


class SplitLedger(unittest.TestCase):
    def test_pending_performance_retains_full_settlement(self):
        validate_day(split_day(), Path('2026-10-03.md'))

    def test_storage_omission_and_target_shrink_rejected(self):
        d = split_day()
        del d['kpis']['betting_evidence']
        with self.assertRaisesRegex(ValueError, 'requires'): validate_day(d, Path('2026-10-03.md'))
        d = split_day()
        d['kpis']['betting_evidence'].update(target_ids=[], pending_ids=[])
        with self.assertRaisesRegex(ValueError, 'target sets differ'): validate_day(d, Path('2026-10-03.md'))

    def test_settlement_total_change_rejected(self):
        d = split_day(); d['fixed_plan_settlement']['return_yen'] = 0
        with self.assertRaisesRegex(ValueError, 'settlement total'): validate_day(d, Path('2026-10-03.md'))

    def test_storage_eligible_without_gate_rejected(self):
        d = split_day()
        d['kpis']['betting_evidence'].update(eligible_ids=['race-a'], pending_ids=[], evidence_refs={
            'race-a': {'snapshot_id': 'snap-a', 'receipt_id': 'receipt-a', 'working_branch': 'prediction/2026-10-03'}})
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); rd = root/'docs/validation/records'; rd.mkdir(parents=True)
            (root/'snap.md').write_text('## final\nsnapshot_id: snap-a\n| 単勝 | 1 | 10,000円 |\n')
            (rd/'2026-10-03.md').write_text('```cycle03-day-v1\n'+json.dumps(d)+'\n```\n')
            self.assertIn('betting_evidence', cycle_links(root, {})[0])


class TaskCompletion(unittest.TestCase):
    setUp = persistence_tests.PersistenceTest.setUp
    snapshot = persistence_tests.PersistenceTest.snapshot
    receipt = persistence_tests.PersistenceTest.receipt
    def invoke(self, digest):
        argv = ['verify', '--root', str(self.root), '--date', DATE, '--snapshot-id', SNAP,
                '--intent-id', 'morning', '--task-complete', '--fixed-content-sha256', digest]
        with patch('sys.argv', argv): return main()

    def test_completion_requires_intent_receipt_and_fixed_content(self):
        path = self.snapshot(); self.receipt()
        digest = hashlib.sha256(snapshot_section(path.read_text(), SNAP).encode()).hexdigest()
        self.assertEqual(self.invoke(digest), 0)
        self.assertEqual(self.invoke('0'*64), 1)
        self.path.unlink()
        self.assertEqual(self.invoke(digest), 1)

    def test_missing_receipt_cannot_complete(self):
        path = self.snapshot()
        digest = hashlib.sha256(snapshot_section(path.read_text(), SNAP).encode()).hexdigest()
        self.assertEqual(self.invoke(digest), 1)
