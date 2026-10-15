import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from selection_history import SCHEMA, audit_oct11, digest, validate_history


class SelectionHistoryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.history = {'schema_version': SCHEMA,
                        'scheduled_posts': {'race-a': '2026-10-11T14:00:00+09:00'}, 'events': []}

    def add(self, action, **changes):
        events = self.history['events']
        core = {'revision': len(events) + 1,
                'previous_sha256': digest({k: v for k, v in events[-1].items() if k != 'evidence'}) if events else None,
                'race_id': 'race-a', 'purpose': 'OFFICIAL_VIRTUAL', 'action': action,
                'at': f'2026-10-11T13:{len(events):02}:00+09:00', 'reason': '試験用変更',
                **changes}
        self.write(core)

    def write(self, core):
        path = f'event-{len(self.history["events"])}.json'
        raw = json.dumps(core, ensure_ascii=False).encode()
        (self.root / path).write_bytes(raw)
        self.history['events'].append({**core, 'evidence': {
            'path': path, 'sha256': hashlib.sha256(raw).hexdigest()}})

    def buy(self, **changes):
        self.add('BUY', **{'selection_revision': 1, 'plan_id': 'p1',
                          'tickets': [{'type': 'WIN', 'horses': [1]}], **changes})

    def check(self):
        return validate_history(self.history, self.root)

    def test_valid_history_is_not_certificate(self):
        self.add('SELECT')
        self.buy()
        report = self.check()
        self.assertTrue(report['history_valid'])
        self.assertFalse(report['kpi_certified'])

    def test_new_event_keeps_old_deadline_in_previous_revision(self):
        self.history['scheduled_posts']['race-a'] = '2026-10-11T13:01:00+09:00'
        self.add('SELECT')
        self.buy(scheduled_post_time_jst='2026-10-11T13:10:00+09:00')
        self.assertEqual(self.check()['event_count'], 2)
        self.assertNotIn('scheduled_post_time_jst', self.history['events'][0])
        self.history['events'][1]['scheduled_post_time_jst'] = '2026-10-11T13:01:00+09:00'
        with self.assertRaisesRegex(ValueError, 'late'):
            self.check()

    def test_buy_without_selection(self):
        self.buy()
        with self.assertRaisesRegex(ValueError, 'additional selection'):
            self.check()

    def test_revision_gap(self):
        self.add('SELECT', revision=2)
        with self.assertRaisesRegex(ValueError, 'revision gap'):
            self.check()

    def test_previous_hash_changed(self):
        self.add('SELECT')
        self.buy(previous_sha256='0' * 64)
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            self.check()

    def test_purpose_switch_requires_new_selection(self):
        self.add('SELECT', purpose='VALIDATION_ONLY')
        self.buy()
        with self.assertRaisesRegex(ValueError, 'additional selection'):
            self.check()

    def test_mixed_ticket_purposes(self):
        self.add('SELECT')
        self.buy(tickets=[{'purpose': 'ACTUAL_PURCHASE'}])
        with self.assertRaisesRegex(ValueError, 'mixed ticket'):
            self.check()

    def test_change_cancel_history_retained(self):
        self.add('SELECT')
        self.buy()
        self.add('CHANGE', selection_revision=1, plan_id='p1', plan_revision=2,
                 tickets=[{'type': 'WIN', 'horses': [2]}])
        self.add('CANCEL', selection_revision=1, plan_id='p1', plan_revision=3)
        self.add('DESELECT', selection_revision=1)
        report = self.check()
        self.assertFalse(report['plans']['p1']['active'])
        self.assertEqual(report['event_count'], 5)
        self.assertEqual(self.history['events'][1]['tickets'][0]['horses'], [1])

    def test_stale_change(self):
        self.add('SELECT')
        self.buy()
        self.add('CHANGE', selection_revision=1, plan_id='p1', plan_revision=1,
                 tickets=[{'type': 'WIN'}])
        with self.assertRaisesRegex(ValueError, 'revision, race or purpose'):
            self.check()

    def test_cancel_unknown(self):
        self.add('SELECT')
        self.add('CANCEL', selection_revision=1, plan_id='missing', plan_revision=1)
        with self.assertRaisesRegex(ValueError, 'revision, race or purpose'):
            self.check()

    def test_cancelled_plan_not_reused(self):
        self.add('SELECT')
        self.buy()
        self.add('CANCEL', selection_revision=1, plan_id='p1', plan_revision=2)
        self.buy()
        with self.assertRaisesRegex(ValueError, 'reused'):
            self.check()

    def test_deselect_with_active_plan(self):
        self.add('SELECT')
        self.buy()
        self.add('DESELECT', selection_revision=1)
        with self.assertRaisesRegex(ValueError, 'cancel active'):
            self.check()

    def test_actual_and_virtual_separate_plan_ids(self):
        self.add('SELECT')
        self.buy()
        self.add('SELECT', purpose='ACTUAL_PURCHASE')
        self.buy(purpose='ACTUAL_PURCHASE', selection_revision=3, plan_id='p2')
        report = self.check()
        self.assertEqual({p['purpose'] for p in report['plans'].values()},
                         {'OFFICIAL_VIRTUAL', 'ACTUAL_PURCHASE'})

    def test_duplicate_selection(self):
        self.add('SELECT')
        self.add('SELECT')
        with self.assertRaisesRegex(ValueError, 'duplicate active'):
            self.check()

    def test_stale_selection_after_reselect(self):
        self.add('SELECT')
        self.add('DESELECT', selection_revision=1)
        self.add('SELECT')
        self.buy()
        with self.assertRaisesRegex(ValueError, 'additional selection'):
            self.check()

    def test_late_or_naive_or_reverse_time(self):
        for at in ('2026-10-11T14:00:00+09:00', '2026-10-11T13:00:00',
                   '2026-10-11T12:59:00+09:00'):
            with self.subTest(at=at):
                self.history['events'] = []
                self.add('SELECT')
                self.buy(at=at)
                with self.assertRaises(ValueError):
                    self.check()

    def test_tampered_evidence(self):
        self.add('SELECT')
        (self.root / 'event-0.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'evidence hash'):
            self.check()

    def test_matching_hash_different_event(self):
        self.add('SELECT')
        self.history['events'][0]['reason'] = '変更'
        with self.assertRaisesRegex(ValueError, 'differs from original'):
            self.check()

    def test_path_escape(self):
        self.add('SELECT')
        self.history['events'][0]['evidence']['path'] = '../missing'
        with self.assertRaisesRegex(ValueError, 'escapes'):
            self.check()

    def test_missing_history_or_old_schema(self):
        for history in ({}, self.history, {'schema_version': 'cycle03-day-v1'}):
            with self.subTest(history=history), self.assertRaises(ValueError):
                validate_history(history, self.root)

    def test_boolean_revision_reference_rejected(self):
        self.add('SELECT')
        self.buy(selection_revision=True)
        with self.assertRaisesRegex(ValueError, 'integer selection'):
            self.check()

    def test_invalid_evidence_shape(self):
        self.add('SELECT')
        self.history['events'][0]['evidence'] = []
        with self.assertRaisesRegex(ValueError, 'evidence object'):
            self.check()

    def test_initial_previous_hash_must_be_explicit(self):
        self.add('SELECT')
        del self.history['events'][0]['previous_sha256']
        with self.assertRaisesRegex(ValueError, 'explicit previous'):
            self.check()

    def test_read_only(self):
        self.add('SELECT')
        self.buy()
        before = copy.deepcopy(self.history)
        files = {p.name: p.read_bytes() for p in self.root.iterdir()}
        self.check()
        self.assertEqual(self.history, before)
        self.assertEqual(files, {p.name: p.read_bytes() for p in self.root.iterdir()})

    def test_real_oct11_remains_pending(self):
        root = Path(__file__).resolve().parents[1]
        report = audit_oct11(root)
        self.assertEqual(report['reference_settlement'], {'stake_yen': 50000, 'return_yen': 0})
        self.assertEqual(report['legacy_formal_betting']['pending'], 5)
        self.assertEqual(sum(r['ticket_count'] for r in report['races']), 7)
        self.assertTrue(all(not r['formal_count_allowed'] for r in report['races']))
        self.assertEqual(report['historical_events_created'], 0)

    def test_saved_audit_sources_and_totals_reproduce(self):
        root = Path(__file__).resolve().parents[1]
        saved = json.loads((root / 'docs/validation/implementation/2026-10-11-task27.json').read_text())
        actual = audit_oct11(root)
        for key in ('sources', 'reference_settlement', 'legacy_formal_betting'):
            self.assertEqual(saved['legacy_audit'][key], actual[key])
