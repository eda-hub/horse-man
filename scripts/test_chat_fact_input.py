import copy
import unittest

import test_chat_fact_capture as fixtures
from chat_fact_input import convert
DATE = fixtures.DATE


def annotations():
    return {'body_weight': [
        {'horse_no': h, 'status': 'ACQUIRED', 'reason': '本文確認済み', 'value': value,
         'quotations': [{'capture_id': 'c1', 'start': start, 'end': end, 'quote': text}]}
        for h, value, start, end, text in [(1, 480, 0, 8, '1番 480kg'), (2, 500, 9, 17, '2番 500kg')]],
        'recent_five_runs': [{'horse_no': h, 'status': 'MISSING', 'value': None,
                             'reason': '近走本文未取得'} for h in [1, 2]]}


class InputConversion(unittest.TestCase):
    def bundle(self): return fixtures.FactCapture().normalize()
    def convert(self, rows=None, bundle=None):
        return convert(bundle or self.bundle(), rows or annotations(), DATE+'T09:45:00+09:00')

    def test_all_horse_rows_and_missing_coverage_preserved(self):
        source = annotations(); before = copy.deepcopy(source)
        result = self.convert(source)
        self.assertEqual(source, before)
        self.assertEqual(result['input']['body_weight'][0]['value'], 480)
        self.assertEqual(result['coverage']['recent_five_runs']['missing_horses'], [1, 2])
        self.assertFalse(result['coverage']['complete'])
        self.assertFalse(result['semantic_extraction_verified'])

    def test_wrong_quote_duplicate_scope_or_missing_zero_rejected(self):
        for mutate in [lambda a: a['body_weight'][0]['quotations'][0].update(quote='changed'),
                       lambda a: a['body_weight'][1].update(horse_no=1),
                       lambda a: a['recent_five_runs'][0].update(value=0)]:
            a = annotations(); mutate(a)
            with self.assertRaises(ValueError): self.convert(a)

    def test_future_readback_unknown_time_and_fallback_without_reason_rejected(self):
        with self.assertRaises(ValueError):
            convert(self.bundle(), annotations(), DATE+'T09:55:00+09:00')
        bundle = self.bundle(); bundle['captures'][0]['source_updated_at_jst'] = None
        with self.assertRaises(ValueError): self.convert(bundle=bundle)
        from test_chat_fact_capture import capture, request
        from chat_fact_capture import normalize
        from datetime import datetime
        c = capture(); c.update(provider='FALLBACK', source_url='https://example.org/test')
        b = normalize(request(), [c], datetime.fromisoformat(DATE+'T09:40:00+09:00'))
        with self.assertRaises(ValueError): self.convert(bundle=b)


if __name__ == '__main__': unittest.main()
