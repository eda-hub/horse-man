import unittest
import base64
import hashlib
from check_r08_acceptance import country_evidence

class CountryEvidenceTest(unittest.TestCase):
    def profile(self,text):
        body=text.encode('shift_jis');return {'body_base64':base64.b64encode(body).decode(),'capture':{'http_status':200,'hash_kind':'response-body-sha256','sha256':hashlib.sha256(body).hexdigest(),'bytes':len(body),'final_url':'https://ahonoora.com/test.html'}}
    def test_own_trainer_country_wins_over_birthplace(self):
        e=self.profile('馬名 Test 生年月日 2000.1.1 生産国 米国 調教師 Trainer（英国） 馬主 Owner 血統表')
        self.assertEqual(country_evidence(e,{'name':'Test','birth_year':2000},'OWN_PROFILE_TRAINER_COUNTRY')[0],['GB'])
    def test_multiple_trainer_countries_preserved_without_last_date(self):
        e=self.profile('馬名 Test 生年月日 2000.1.1 調教師 Trainer（UAE／英国） 馬主 Owner 血統表')
        self.assertEqual(country_evidence(e,{'name':'Test','birth_year':2000},'OWN_PROFILE_TRAINER_COUNTRY')[0],['AE','GB'])
    def test_wrong_individual_year_rejected(self):
        e=self.profile('馬名 Test 生年月日 2001.1.1 調教師 Trainer（英国） 馬主 Owner 血統表')
        with self.assertRaisesRegex(ValueError,'name/year'):country_evidence(e,{'name':'Test','birth_year':2000},'OWN_PROFILE_TRAINER_COUNTRY')

if __name__=='__main__':unittest.main()
