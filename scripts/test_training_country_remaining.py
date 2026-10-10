import base64
import hashlib
import unittest
from pedigree_registry import stamp
from check_training_country_remaining import captured, domestic_country, profile_fields, ranking_rows, supplementary_countries


class TrainingCountryRemainingTests(unittest.TestCase):
    def identity(self):
        return dict(name='ウインブライト', aliases=[], birth_year=2014, external_ids={'NETKEIBA': '2014100222'})

    def profile(self, encoding='utf-8'):
        html = '<h1>netkeiba</h1><h1>ウインブライト</h1><table><tr><th>生年月日</th><td>2014年05月12日</td></tr><tr><th>調教師</th><td>美浦 畠山吉宏</td></tr></table>'
        return html.encode(encoding), dict(final_url='https://db.sp.netkeiba.com/horse/2014100222/')

    def test_logo_is_not_the_horse_heading(self):
        self.assertEqual(domestic_country(profile_fields(*self.profile(), self.identity())), 'JP')

    def test_legacy_encoding_and_desktop_redirect(self):
        body, meta = self.profile('euc-jp')
        meta['final_url'] = 'https://db.netkeiba.com/horse/2014100222/'
        self.assertEqual(profile_fields(body, meta, self.identity())['trainer'], '美浦 畠山吉宏')

    def test_wrong_external_id_is_rejected(self):
        body, meta = self.profile()
        meta['final_url'] = 'https://db.sp.netkeiba.com/horse/2014100223/'
        with self.assertRaises(ValueError):
            profile_fields(body, meta, self.identity())

    def test_wrong_birth_year_is_not_merged_by_name(self):
        identity = self.identity(); identity['birth_year'] = 2015
        self.assertIsNone(profile_fields(*self.profile(), identity))

    def test_country_annotation_is_not_training_evidence(self):
        self.assertIsNone(domestic_country(dict(trainer='海外 -', heading='Horse (米)')))
        self.assertEqual(domestic_country(dict(trainer='川島 正行 (船 橋)')), 'JP')

    def ranking(self, trained='IRE', born='2017'):
        return ('<table><tr><th>Horse</th><th>YOF</th><th>Trained</th><th>Run</th></tr>'
                '<tr><td>Siskin (USA)</td><td>' + born + '</td><td>' + trained + '</td><td>GB</td></tr></table>').encode()

    def test_trained_column_not_birth_or_race_country(self):
        rows = ranking_rows(self.ranking(), 2020, dict(english_name='Siskin(USA)'), dict(birth_year=2017))
        self.assertEqual([r['country'] for r in rows], ['IE'])
        self.assertIsNone(rows[0]['last_trained_on'])

    def test_all_explicit_countries_are_retained(self):
        rows = ranking_rows(self.ranking('UAE/GB'), 2020, dict(english_name='Siskin'), dict(birth_year=2017))
        self.assertEqual([r['country'] for r in rows], ['AE', 'GB'])
        self.assertEqual(ranking_rows(self.ranking(), 2020, dict(english_name='Siskin'), dict(birth_year=2018)), [])

    def test_wikipedia_birth_country_and_namesake_are_rejected(self):
        source = dict(final_url='https://en.wikipedia.org/wiki/Horse')
        raw = '<h1>Horse</h1><table><tr><th>Foaled</th><td>2001</td></tr><tr><th>Country</th><td>United States</td></tr></table>'.encode()
        self.assertEqual(supplementary_countries(raw, source, dict(english_name='Horse'), dict(birth_year=2001), 'WIKIPEDIA_EXPLICIT_TRAINING_CATEGORY'), [])
        raw += b'<a title="Category:Racehorses trained in Ireland">Ireland</a>'
        self.assertEqual(supplementary_countries(raw, source, dict(english_name='Horse'), dict(birth_year=2000), 'WIKIPEDIA_EXPLICIT_TRAINING_CATEGORY'), [])

    def test_successful_http_status_does_not_allow_corrupt_bytes(self):
        body=b'original'; now=stamp()
        entry=dict(capture=dict(http_status=200,hash_kind='http-response-body-bytes-sha256',byte_length=len(body),sha256=hashlib.sha256(body).hexdigest(),request_started_at=now,captured_at=now),body_base64=base64.b64encode(b'changed!').decode())
        with self.assertRaises(ValueError):
            captured(entry, stamp())


if __name__ == '__main__':
    unittest.main()
