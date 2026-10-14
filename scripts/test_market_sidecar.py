"""28番の価格状態・時点・全試行・独立保存の合成回帰。"""
import copy
import json
import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from check_prediction_compliance import ComplianceError
from cycle04_operations import validate_market_payload
from market_sidecar import describe
import cycle04_workflow as workflow
import test_cycle04_workflow as fixtures
from test_recommendation import DATE, RACE

CUTOFF = DATE + 'T10:01:00+09:00'


def payload(state='NOT_ATTEMPTED', decision='NOT_EVALUATED'):
    m = {'status': state, 'decision': decision, 'reason': '合成試行の検査',
         'odds': None, 'expected_value': None, 'attempted_at_jst': None,
         'acquired_at_jst': None, 'source_ref': None,
         'acquisition': {'schema_version': 'market-acquisition-v1', 'attempts': [],
                         'deadline_at_jst': DATE + 'T10:00:00+09:00',
                         'stopped_at_jst': None}}
    if state != 'NOT_ATTEMPTED':
        attempt = {'attempt_no': 1, 'source_ref': 'https://example.invalid/price',
                   'started_at_jst': DATE + 'T09:58:00+09:00',
                   'finished_at_jst': DATE + 'T09:59:00+09:00',
                   'result': 'FAILED', 'reason': '取得応答を得られない',
                   'observed_at_jst': None}
        m['attempted_at_jst'] = attempt['started_at_jst']
        m['acquisition']['attempts'].append(attempt)
        if state == 'ACQUIRED':
            attempt.update(result='ACQUIRED', reason='価格照合済み',
                           observed_at_jst=DATE + 'T09:57:00+09:00')
            m.update(odds=3.0, acquired_at_jst=attempt['finished_at_jst'],
                     source_ref=attempt['source_ref'],
                     expected_value=None if decision == 'NOT_EVALUATED' else
                     (.1 if decision == 'POSITIVE_EV' else -.1))
        elif state == 'DEADLINE_STOPPED':
            m['acquisition']['stopped_at_jst'] = DATE + 'T10:00:00+09:00'
    return {'schema_version': 'market-analysis-v2', 'race_id': RACE,
            'race_date_jst': DATE, 'data_cutoff': CUTOFF, 'market': m}


class MarketStates(unittest.TestCase):
    def check(self, p):
        return validate_market_payload(p, p['data_cutoff'])

    def test_all_acquisition_states_and_three_decisions(self):
        for state in ('NOT_ATTEMPTED', 'FAILED', 'DEADLINE_STOPPED', 'ACQUIRED'):
            p = payload(state)
            self.assertEqual(self.check(p), state)
            self.assertEqual(describe(p)['判断'], '期待値は未評価')
        for decision in ('POSITIVE_EV', 'INSUFFICIENT_EV'):
            self.assertEqual(self.check(payload('ACQUIRED', decision)), 'ACQUIRED')

    def test_failed_then_acquired_keeps_both_sources(self):
        p = payload('ACQUIRED')
        success = p['market']['acquisition']['attempts'][0]
        failure = copy.deepcopy(success)
        failure.update(result='FAILED', observed_at_jst=None,
                       started_at_jst=DATE+'T09:56:00+09:00',
                       finished_at_jst=DATE+'T09:57:00+09:00',
                       source_ref='https://example.invalid/first')
        success['attempt_no'] = 2
        p['market']['acquisition']['attempts'].insert(0, failure)
        p['market']['attempted_at_jst'] = failure['started_at_jst']
        before = copy.deepcopy(p)
        self.check(p)
        self.assertEqual(p, before)
        self.assertEqual(len(describe(p)['試行履歴']), 2)

    def test_missing_prices_never_become_insufficient_ev(self):
        for state in ('NOT_ATTEMPTED', 'FAILED', 'DEADLINE_STOPPED'):
            p = payload(state); p['market']['decision'] = 'INSUFFICIENT_EV'
            with self.assertRaises(ComplianceError): self.check(p)

    def test_no_attempt_cannot_claim_history(self):
        p = payload(); p['market']['acquisition']['attempts'] = payload('FAILED')['market']['acquisition']['attempts']
        with self.assertRaises(ComplianceError): self.check(p)

    def test_failed_history_cannot_claim_acquisition(self):
        p = payload('FAILED'); p['market']['acquired_at_jst'] = DATE+'T09:59:00+09:00'
        with self.assertRaises(ComplianceError): self.check(p)

    def test_v2_missing_history_and_unknown_schema_rejected(self):
        p = payload(); del p['market']['acquisition']
        with self.assertRaises(ComplianceError): self.check(p)
        p = payload(); p['schema_version'] = 'unknown'
        with self.assertRaises(ComplianceError): self.check(p)

    def test_attempt_source_and_reason_required(self):
        for field in ('source_ref', 'reason'):
            p = payload('FAILED'); p['market']['acquisition']['attempts'][0][field] = ''
            with self.assertRaises(ComplianceError): self.check(p)

    def test_future_reversed_and_observed_time_rejected(self):
        for field, value in [('started_at_jst', '10:02'), ('finished_at_jst', '09:55'),
                             ('observed_at_jst', '10:02')]:
            p = payload('ACQUIRED')
            p['market']['acquisition']['attempts'][0][field] = DATE+'T'+value+':00+09:00'
            with self.assertRaises(ComplianceError): self.check(p)

    def test_attempt_number_duplicate_overlap_and_retry_after_success_rejected(self):
        for kind in ('number', 'overlap', 'after_success'):
            p = payload('ACQUIRED'); a = p['market']['acquisition']['attempts'][0]
            if kind == 'number': a['attempt_no'] = True
            else:
                b = copy.deepcopy(a); b['attempt_no'] = 2
                if kind == 'after_success':
                    b.update(started_at_jst=DATE+'T09:59:00+09:00', finished_at_jst=DATE+'T10:00:00+09:00')
                p['market']['acquisition']['attempts'].append(b)
            with self.assertRaises(ComplianceError): self.check(p)

    def test_top_level_source_and_times_must_match_history(self):
        for field in ('source_ref', 'attempted_at_jst', 'acquired_at_jst'):
            p = payload('ACQUIRED'); p['market'][field] = None
            with self.assertRaises(ComplianceError): self.check(p)

    def test_deadline_stop_and_attempt_after_deadline_rejected(self):
        for field, value in [('deadline_at_jst', None), ('stopped_at_jst', DATE+'T09:59:00+09:00'),
                             ('stopped_at_jst', DATE+'T10:02:00+09:00')]:
            p = payload('DEADLINE_STOPPED'); p['market']['acquisition'][field] = value
            with self.assertRaises(ComplianceError): self.check(p)
        p = payload('ACQUIRED'); p['market']['acquisition']['deadline_at_jst'] = DATE+'T09:58:00+09:00'
        with self.assertRaises(ComplianceError): self.check(p)

    def test_nonfinite_bool_and_contradictory_expected_value_rejected(self):
        for odds, ev in [(True, .1), (float('inf'), .1), (3, float('nan')), (3, -.1)]:
            p = payload('ACQUIRED', 'POSITIVE_EV'); p['market'].update(odds=odds, expected_value=ev)
            with self.assertRaises(ComplianceError): self.check(p)

    def test_legacy_history_is_unverified_not_fabricated(self):
        p = payload(); p['schema_version'] = 'market-analysis-v1'; del p['market']['acquisition']
        self.check(p)
        self.assertIsNone(describe(p)['試行履歴'])
        self.assertIn('未確認', describe(p)['履歴状態'])

    def test_cli_reads_without_writing_and_displays_failed_source(self):
        from market_sidecar import main
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'market.json'
            path.write_text(json.dumps(payload('FAILED'), ensure_ascii=False))
            before = path.read_bytes()
            out = io.StringIO()
            with redirect_stdout(out):
                self.assertEqual(main([str(path)]), 0)
            self.assertIn('価格取得に失敗', out.getvalue())
            self.assertIn('https://example.invalid/price', out.getvalue())
            self.assertIn('期待値は未評価', out.getvalue())
            self.assertEqual(path.read_bytes(), before)


class MarketPersistence(unittest.TestCase):
    setUp = fixtures.OperationalWorkflow.setUp
    register = fixtures.OperationalWorkflow.register
    select = fixtures.OperationalWorkflow.select

    def final(self):
        self.register(); workflow.record_prediction(self.root, DATE, self.entry); self.select()
        self.entry['phase'] = 'FINAL'; workflow.record_prediction(self.root, DATE, self.entry)

    def save_market(self, p, ident):
        ref = self.fixture.artifact(ident, 'markets/'+ident+'.json', p, at='10:02')
        return workflow.record_market(self.root, DATE, {'race_id': RACE, 'market_ref': ref})

    def test_no_market_needed_for_prediction_and_recommendation(self):
        self.final()
        day, _ = workflow.read_day(self.root, DATE)
        self.assertEqual(day['kpis']['production']['eligible_ids'], [RACE])
        self.assertEqual(day['kpis']['recommendation']['eligible_ids'], [RACE])
        self.assertFalse(day['races'][RACE].get('market_ref'))

    def test_every_market_state_keeps_prediction_recommendation_bytes_and_kpis(self):
        self.final(); day, _ = workflow.read_day(self.root, DATE)
        rec_gate = day['races'][RACE]['recommendation_gate_path']
        rec = json.loads((self.root/rec_gate).read_text())
        paths = [day['races'][RACE]['operations']['prediction_ref']['artifact_path'],
                 rec_gate, rec['evidence_ref']['artifact_path']]
        before = {p: (self.root/p).read_bytes() for p in paths}
        kpis = copy.deepcopy({k: day['kpis'][k] for k in ('production', 'recommendation')})
        cases = [('FAILED', 'NOT_EVALUATED'), ('DEADLINE_STOPPED', 'NOT_EVALUATED'),
                 ('ACQUIRED', 'NOT_EVALUATED'), ('ACQUIRED', 'INSUFFICIENT_EV'),
                 ('ACQUIRED', 'POSITIVE_EV'), ('NOT_ATTEMPTED', 'NOT_EVALUATED')]
        for i, (state, decision) in enumerate(cases):
            self.save_market(payload(state, decision), str(i))
            after, _ = workflow.read_day(self.root, DATE)
            self.assertEqual(after['races'][RACE]['market'], payload(state, decision)['market'])
            self.assertEqual({k: after['kpis'][k] for k in kpis}, kpis)
        self.assertEqual({p: (self.root/p).read_bytes() for p in paths}, before)

    def test_invalid_history_cannot_overwrite_saved_day(self):
        self.final(); p = payload('FAILED'); del p['market']['acquisition']
        path = self.root/workflow.DIRECTORY/(DATE+'.json'); before = path.read_bytes()
        with self.assertRaises(ComplianceError): self.save_market(p, 'invalid')
        self.assertEqual(path.read_bytes(), before)

    def test_pending_market_original_hash_is_checked_without_eligible_kpi(self):
        self.final(); self.save_market(payload('FAILED'), 'failed')
        path = self.root/'markets/failed.json'; path.write_text(path.read_text()+'\n')
        with self.assertRaisesRegex(ComplianceError, 'artifact hash mismatch'):
            workflow.read_day(self.root, DATE)
