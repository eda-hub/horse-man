import base64
import hashlib
import unittest
from check_training_country_ancestors import profile_countries, source_text

def entry(text):
    body = text.encode('shift_jis')
    return {'body_base64': base64.b64encode(body).decode(), 'capture': {'http_status': 200, 'hash_kind': 'response-body-sha256', 'sha256': hashlib.sha256(body).hexdigest(), 'bytes': len(body), 'final_url': 'https://ahonoora.com/example.html'}}

class AncestorSourceTests(unittest.TestCase):
    def test_own_training_country_excludes_birth_and_ancestor(self):
        e = entry('馬名 Roberto 生年月日 1969. 3.16 生産地 アメリカ 調教師 Vincent O Brien（愛国） 馬主 A 血統表 調教師 Other（米国）')
        self.assertEqual(profile_countries(e, 'Roberto', 1969)[0], ['IE'])

    def test_wrong_identity_and_mutated_body_rejected(self):
        e = entry('馬名 Roberto 生年月日 1969. 3.16 調教師 Trainer（愛国） 馬主 A 血統表')
        for name, year in [('Other', 1969), ('Roberto', 1970)]:
            with self.assertRaises(ValueError):
                profile_countries(e, name, year)
        e['body_base64'] = base64.b64encode(b'altered').decode()
        with self.assertRaises(ValueError):
            source_text(e)

    def test_multiple_affiliations_remain_multiple(self):
        e = entry('馬名 Northern Dancer 生年月日 1961. 5.27 調教師 Fleming（加国） Luro（米国） 馬主 A 血統表')
        self.assertEqual(profile_countries(e, 'Northern Dancer', 1961)[0], ['CA', 'US'])

if __name__ == '__main__':
    unittest.main()
