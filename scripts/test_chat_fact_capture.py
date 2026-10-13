import copy
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import chat_fact_capture as facts

DATE = '2026-10-17'


def request():
    return {'schema_version': facts.REQUEST_SCHEMA, 'request_id': 'r1',
            'race_id': '20261017-TOK-01', 'race_date_jst': DATE,
            'scheduled_post_time_jst': DATE+'T10:00:00+09:00',
            'data_cutoff': DATE+'T09:50:00+09:00', 'purpose': 'INPUT',
            'horse_numbers': [1, 2], 'required_items': ['body_weight']}


def capture():
    return {'capture_id': 'c1', 'source_url': 'https://www.jra.go.jp/test',
            'provider': 'OFFICIAL', 'origin_group': 'JRA', 'mode': 'FORWARD',
            'retrieval_kind': 'PAGE_TEXT', 'reason': '公開本文を閲覧',
            'text': '1番 480kg\n2番 500kg\n',
            'read_started_at_jst': DATE+'T09:35:00+09:00',
            'read_finished_at_jst': DATE+'T09:36:00+09:00',
            'source_updated_at_jst': DATE+'T09:30:00+09:00'}


class FactCapture(unittest.TestCase):
    def normalize(self, records=None):
        return facts.normalize(request(), records or [capture()],
                               datetime.fromisoformat(DATE+'T09:40:00+09:00'))

    def test_text_hash_and_shared_origin_not_counted_twice(self):
        second = capture(); second['capture_id'] = 'c2'
        result = self.normalize([capture(), second])
        self.assertEqual(result['independent_origin_groups'], ['JRA'])
        self.assertFalse(result['formal_kpi_certified'])
        self.assertEqual(facts.verify(result), result)
        changed = copy.deepcopy(result); changed['captures'][0]['text'] += '改変'
        with self.assertRaises(ValueError): facts.verify(changed)

    def test_unknown_time_snippet_replay_and_error_never_become_observed_fact(self):
        for kind, mode, time in [('PAGE_TEXT', 'FORWARD', None),
                                 ('SEARCH_SNIPPET', 'FORWARD', capture()['source_updated_at_jst']),
                                 ('PAGE_TEXT', 'REPLAY', capture()['source_updated_at_jst']),
                                 ('ERROR', 'FORWARD', None)]:
            c = capture(); c.update(retrieval_kind=kind, mode=mode, source_updated_at_jst=time)
            if kind == 'ERROR': c['text'] = ''
            self.assertFalse(self.normalize([c])['captures'][0]['usable_as_observed_fact'])

    def test_invalid_source_time_scope_and_http_claims_rejected(self):
        for key, value in [('source_url', 'https://example.org/result'),
                           ('read_finished_at_jst', DATE+'T10:01:00+09:00'),
                           ('raw_http_sha256', 'a'*64), ('http_status', 200)]:
            c = capture(); c[key] = value
            with self.assertRaises(ValueError): self.normalize([c])
        r = request(); r['horse_numbers'] = [1, 1]
        with self.assertRaises(ValueError): facts.request(r)

    def test_immutable_save_and_daily_branch_gate(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); path = 'docs/validation/fact-captures/'+DATE+'/c1.json'
            data = self.normalize()
            with patch('chat_fact_capture.check_working_branch') as branch:
                facts.save(root, path, data); original = (root/path).read_bytes()
                facts.save(root, path, data); branch.assert_called_with(root, DATE)
                newer = copy.deepcopy(data); newer['recorded_at'] = DATE+'T09:41:00+09:00'
                with self.assertRaises(ValueError): facts.save(root, path, newer)
                self.assertEqual((root/path).read_bytes(), original)
            with patch('chat_fact_capture.check_working_branch', side_effect=ValueError('wrong branch')):
                with self.assertRaises(ValueError): facts.save(root, path, data)

    def test_staged_write_failure_preserves_absence_and_removes_lock(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); path = 'docs/validation/fact-captures/'+DATE+'/c1.json'
            with patch('chat_fact_capture.check_working_branch'), \
                    patch('chat_fact_capture.os.link', side_effect=OSError('write failed')):
                with self.assertRaises(OSError): facts.save(root, path, self.normalize())
            self.assertFalse((root/path).exists())
            self.assertFalse(list((root/path).parent.iterdir()))


if __name__ == '__main__': unittest.main()
