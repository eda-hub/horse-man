"""29番：実HTTP通信を含む合成障害再現。実開催の価格・実測とは別。"""
import copy
import hashlib
import json
import tempfile
import threading
import unittest
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import market_acquisition as acquisition
from check_prediction_compliance import ComplianceError
from test_recommendation import DATE, RACE, POST
from cycle04_operations import validate_market_payload
import test_market_sidecar as market_fixtures
import cycle04_workflow as workflow


class Clock:
    def __init__(self):
        self.value = datetime.fromisoformat(DATE+'T09:00:00+09:00')
    def now(self):
        return self.value
    def sleep(self, seconds):
        self.value += timedelta(seconds=seconds)


def request():
    return {'schema_version': 'market-price-request-v1', 'mode': 'SYNTHETIC',
            'race_id': RACE, 'race_date_jst': DATE, 'scheduled_post_time_jst': POST,
            'deadline_at_jst': DATE+'T09:00:05+09:00', 'data_cutoff': DATE+'T09:00:10+09:00',
            'ticket': {'type': 'QUINELLA', 'horses': [2, 5]},
            'routes': [{'source_url': 'http://127.0.0.1:1/primary', 'max_attempts': 2},
                       {'source_url': 'http://127.0.0.1:2/fallback', 'max_attempts': 1}],
            'timeout_seconds': 1, 'retry_delay_seconds': .1}


def response(req=None):
    req = req or request()
    return json.dumps({'schema_version': 'market-price-response-v1', 'race_id': req['race_id'],
                       'ticket': req['ticket'], 'observed_at_jst': DATE+'T08:59:00+09:00',
                       'odds': 12.5}).encode()


class AcquisitionTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock(); self.req = request()
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup); self.root = Path(tmp.name)
        self.calls = []

    def run_collect(self, results, mutate=None):
        def fetch(url, timeout):
            self.calls.append((url, timeout))
            result = results.pop(0)
            self.clock.sleep(.1)
            if mutate: mutate(self.clock)
            return result
        return acquisition.collect(self.req, 'evidence/run', fetch=fetch,
                                   now=self.clock.now, sleep=self.clock.sleep)

    def save(self, p, raws):
        acquisition.save(self.root, 'evidence/run', p, raws)
        acquisition.verify_responses(self.root, p, require_forward=False)

    def test_primary_success_and_raw_price_readback(self):
        p, raw = self.run_collect([(200, response(), True, None)])
        self.save(p, raw)
        self.assertEqual(p['market']['status'], 'ACQUIRED')
        self.assertEqual(p['market']['odds'], 12.5)
        self.assertIsNone(p['market']['expected_value'])
        self.assertEqual(len(self.calls), 1)

    def test_retry_then_fallback_and_raw_hashes(self):
        p, raw = self.run_collect([(503, b'first failure', True, 'HTTP_ERROR'),
                                  (None, None, None, 'TRANSPORT_ERROR'),
                                  (200, response(), True, None)])
        self.save(p, raw)
        self.assertEqual([u for u, _ in self.calls],
                         [self.req['routes'][0]['source_url']]*2+[self.req['routes'][1]['source_url']])
        attempts = p['market']['acquisition']['attempts']
        self.assertEqual(attempts[0]['response_ref']['sha256'], hashlib.sha256(b'first failure').hexdigest())
        self.assertIsNone(attempts[1]['response_ref'])
        self.assertEqual(p['market']['source_ref'], self.req['routes'][1]['source_url'])

    def test_both_routes_failed_does_not_claim_ev_or_price(self):
        p, raw = self.run_collect([(503, b'error', True, 'HTTP_ERROR')]*3)
        self.save(p, raw)
        self.assertEqual(p['market']['status'], 'FAILED')
        self.assertIsNone(p['market']['odds'])
        self.assertEqual(p['market']['decision'], 'NOT_EVALUATED')
        self.assertIn('未完了', p['market']['reason'])

    def test_deadline_before_first_attempt_has_no_fabricated_attempt(self):
        self.clock.sleep(5)
        p, raw = self.run_collect([])
        self.save(p, raw)
        self.assertEqual(p['market']['status'], 'DEADLINE_STOPPED')
        self.assertFalse(self.calls)
        self.assertEqual(p['market']['acquisition']['attempts'], [])
        self.assertIsNone(p['market']['attempted_at_jst'])

    def test_timeout_over_deadline_preserves_actual_finish_and_rejects_late_success(self):
        p, raw = self.run_collect([(200, response(), True, None)], lambda clock: clock.sleep(6))
        self.save(p, raw)
        self.assertEqual(p['market']['status'], 'DEADLINE_STOPPED')
        a = p['market']['acquisition']['attempts'][0]
        self.assertEqual(a['finished_at_jst'], (datetime.fromisoformat(DATE+'T09:00:00+09:00')+
                         timedelta(seconds=6.1)).isoformat())
        self.assertEqual(a['error_code'], 'DEADLINE_EXCEEDED')
        self.assertIsNone(p['market']['odds'])
        self.assertEqual(len(self.calls), 1)

    def test_retry_delay_cannot_cross_deadline_then_fetch(self):
        self.req['retry_delay_seconds'] = 10
        p, raw = self.run_collect([(503, b'error', True, 'HTTP_ERROR')])
        self.save(p, raw)
        self.assertEqual(p['market']['status'], 'DEADLINE_STOPPED')
        self.assertEqual(len(self.calls), 1)

    def test_timeout_is_bounded_by_remaining_deadline(self):
        self.clock.sleep(4.8)
        p, raw = self.run_collect([(200, response(), True, None)])
        self.assertAlmostEqual(self.calls[0][1], .2)
        self.save(p, raw)

    def test_bad_race_ticket_future_price_and_nonfinite_odds_use_fallback(self):
        for field, value in [('race_id', 'other'), ('ticket', {'type': 'QUINELLA', 'horses': [1, 2]}),
                             ('observed_at_jst', DATE+'T09:10:00+09:00'), ('odds', True),
                             ('odds', float('nan'))]:
            with self.subTest(field=field, value=value):
                self.clock = Clock(); self.calls = []
                bad = json.loads(response()); bad[field] = value
                p, raw = self.run_collect([(200, json.dumps(bad).encode(), True, None)]*2+
                                         [(200, response(), True, None)])
                self.assertEqual(len(self.calls), 3)
                self.assertEqual(p['market']['status'], 'ACQUIRED')

    def test_invalid_json_incomplete_response_and_http_error_use_fallback(self):
        for first in [(200, b'not JSON', True, None), (200, response(), False, None),
                      (403, b'denied', True, 'HTTP_ERROR')]:
            self.clock = Clock(); self.calls = []
            p, raw = self.run_collect([first, first, (200, response(), True, None)])
            self.assertEqual(p['market']['status'], 'ACQUIRED')
            self.assertEqual(len(self.calls), 3)

    def test_request_identity_time_policy_and_routes_rejected_before_io(self):
        changes = [('routes', [self.req['routes'][0]]*2), ('timeout_seconds', True),
                   ('retry_delay_seconds', -1), ('deadline_at_jst', POST),
                   ('mode', 'REPLAY'), ('ticket', {'type': 'EXACTA', 'horses': [1, 1]})]
        for key, value in changes:
            req = copy.deepcopy(self.req); req[key] = value
            with self.assertRaises(ComplianceError): acquisition.validate_request(req)
        req = copy.deepcopy(self.req); req['mode'] = 'FORWARD'
        with self.assertRaises(ComplianceError): acquisition.validate_request(req)

    def test_ordered_ticket_identity_and_unordered_identity(self):
        req = copy.deepcopy(self.req); req['ticket'] = {'type': 'EXACTA', 'horses': [2, 5]}
        bad = json.loads(response(req)); bad['ticket']['horses'] = [5, 2]
        with self.assertRaises(ComplianceError):
            acquisition.decode_price(json.dumps(bad).encode(), req, self.clock.now())
        good = json.loads(response()); good['ticket']['horses'] = [5, 2]
        acquisition.decode_price(json.dumps(good).encode(), self.req, self.clock.now())

    def test_corrupt_raw_response_cannot_verify(self):
        p, raw = self.run_collect([(200, response(), True, None)]); self.save(p, raw)
        path = self.root/next(iter(raw)); path.write_bytes(path.read_bytes()+b' ')
        with self.assertRaisesRegex(ComplianceError, 'hash/size mismatch'):
            acquisition.verify_responses(self.root, p, require_forward=False)

    def test_resealed_raw_with_changed_price_is_rejected(self):
        p, raw = self.run_collect([(200, response(), True, None)]); self.save(p, raw)
        a = p['market']['acquisition']['attempts'][0]; ref = a['response_ref']
        data = json.loads((self.root/ref['artifact_path']).read_bytes()); data['odds'] = 99
        changed = json.dumps(data).encode(); (self.root/ref['artifact_path']).write_bytes(changed)
        ref.update(sha256=hashlib.sha256(changed).hexdigest(), bytes=len(changed))
        with self.assertRaisesRegex(ComplianceError, 'acquired price'):
            acquisition.verify_responses(self.root, p, require_forward=False)

    def test_synthetic_transport_never_certifies_live_market(self):
        p, raw = self.run_collect([(200, response(), True, None)]); self.save(p, raw)
        with self.assertRaisesRegex(ComplianceError, 'synthetic acquisition'):
            acquisition.verify_responses(self.root, p)

    def test_missing_transport_tag_and_attempt_policy_tampering_rejected(self):
        p, raw = self.run_collect([(200, response(), True, None)]); self.save(p, raw)
        changed = copy.deepcopy(p); del changed['market']['acquisition']['transport_schema']
        with self.assertRaises(ComplianceError):
            acquisition.verify_responses(self.root, changed, require_forward=False)
        p['market']['acquisition']['attempts'][0]['source_ref'] = 'unconfigured'
        with self.assertRaises(ComplianceError):
            acquisition.verify_responses(self.root, p, require_forward=False)

    def test_false_raw_failure_diagnostic_and_retry_policy_rejected(self):
        p, raw = self.run_collect([(503, b'failed', True, 'HTTP_ERROR'),
                                  (503, b'failed', True, 'HTTP_ERROR'),
                                  (200, response(), True, None)])
        self.save(p, raw)
        changed = copy.deepcopy(p)
        changed['market']['acquisition']['attempts'][0]['error_code'] = 'INCOMPLETE_RESPONSE'
        with self.assertRaisesRegex(ComplianceError, 'false incomplete'):
            acquisition.verify_responses(self.root, changed, require_forward=False)
        p['market']['acquisition']['request']['retry_delay_seconds'] = 1
        with self.assertRaisesRegex(ComplianceError, 'retry delay'):
            acquisition.verify_responses(self.root, p, require_forward=False)

    def test_saved_run_is_append_only_and_does_not_write_predictions(self):
        p, raw = self.run_collect([(200, response(), True, None)])
        before = copy.deepcopy(self.req); self.save(p, raw)
        with self.assertRaises(FileExistsError): acquisition.save(self.root, 'evidence/run', p, raw)
        self.assertEqual(self.req, before)
        self.assertFalse((self.root/'docs/validation/records').exists())

    def test_real_http_primary_failure_and_fallback_success_matches_injected_transport(self):
        body = response()
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                status = 503 if self.path == '/primary' else 200
                raw = b'primary unavailable' if status == 503 else body
                self.send_response(status); self.send_header('Content-Length', str(len(raw)))
                self.end_headers(); self.wfile.write(raw)
            def log_message(self, *args): pass
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            base = 'http://127.0.0.1:'+str(server.server_port)
            self.req['routes'][0]['source_url'] = base+'/primary'
            self.req['routes'][1]['source_url'] = base+'/fallback'
            p, raw = acquisition.collect(self.req, 'evidence/run', now=self.clock.now, sleep=self.clock.sleep)
            self.save(p, raw)
            self.assertEqual(p['market']['status'], 'ACQUIRED')
            self.assertEqual([a['http_status'] for a in p['market']['acquisition']['attempts']], [503, 503, 200])
            q, _ = self.run_collect([(503, b'primary unavailable', True, 'HTTP_ERROR')]*2+
                                    [(200, body, True, None)])
            self.assertEqual(p['market']['odds'], q['market']['odds'])
            self.assertEqual(p['market']['decision'], q['market']['decision'])
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=2)


class TransportPersistence(unittest.TestCase):
    setUp = market_fixtures.MarketPersistence.setUp
    register = market_fixtures.MarketPersistence.register
    select = market_fixtures.MarketPersistence.select
    final = market_fixtures.MarketPersistence.final

    def captured(self, mode='FORWARD', failed=False):
        req = request(); req['mode'] = mode
        req['routes'] = [{'source_url': 'https://primary.example.invalid/price', 'max_attempts': 1},
                         {'source_url': 'https://fallback.example.invalid/price', 'max_attempts': 1}]
        clock = Clock()
        result = (503, b'unavailable', True, 'HTTP_ERROR') if failed else (200, response(req), True, None)
        payload, raws = acquisition.collect(req, 'markets/transport', fetch=lambda url, timeout: result,
                                           now=clock.now, sleep=clock.sleep)
        acquisition.save(self.root, 'markets/transport', payload, raws)
        ref = self.fixture.artifact('http-market', 'markets/http-market.json', payload, at='10:02')
        return payload, raws, {'race_id': RACE, 'market_ref': ref}

    def test_forward_original_response_is_checked_by_existing_writer_and_reader(self):
        self.final(); before, _ = workflow.read_day(self.root, DATE)
        payload, raws, entry = self.captured()
        workflow.record_market(self.root, DATE, entry)
        after, _ = workflow.read_day(self.root, DATE)
        self.assertEqual(after['races'][RACE]['market'], payload['market'])
        self.assertEqual(after['kpis']['production'], before['kpis']['production'])
        self.assertEqual(after['kpis']['recommendation'], before['kpis']['recommendation'])
        (self.root/next(iter(raws))).write_bytes(b'corrupt')
        with self.assertRaisesRegex(ComplianceError, 'hash/size mismatch'):
            workflow.read_day(self.root, DATE)

    def test_failed_pending_transport_original_is_also_checked(self):
        self.final(); payload, raws, entry = self.captured(failed=True)
        workflow.record_market(self.root, DATE, entry)
        after, _ = workflow.read_day(self.root, DATE)
        self.assertEqual(after['kpis']['market']['pending_ids'], [RACE])
        (self.root/next(iter(raws))).write_bytes(b'corrupt')
        with self.assertRaisesRegex(ComplianceError, 'hash/size mismatch'):
            workflow.read_day(self.root, DATE)

    def test_synthetic_http_evidence_cannot_overwrite_live_day(self):
        self.final(); path = self.root/workflow.DIRECTORY/(DATE+'.json'); before = path.read_bytes()
        _, _, entry = self.captured(mode='SYNTHETIC')
        with self.assertRaisesRegex(ComplianceError, 'synthetic acquisition'):
            workflow.record_market(self.root, DATE, entry)
        self.assertEqual(path.read_bytes(), before)

    def test_real_http_redirect_is_not_silent_source_switch(self):
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(302); self.send_header('Location', '/other'); self.end_headers()
            def log_message(self, *args): pass
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            status, raw, complete, error = acquisition.fetch_http('http://127.0.0.1:'+str(server.server_port), 1)
            self.assertEqual(status, 302); self.assertEqual(error, 'HTTP_ERROR')
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=2)
