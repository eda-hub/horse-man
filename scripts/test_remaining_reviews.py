import copy,json,shutil,tempfile,unittest
from pathlib import Path
from check_remaining_reviews import BASE,check

class RemainingReviewTest(unittest.TestCase):
    def test_saved_evidence_and_rejection_of_promotion_or_wrong_subject(self):
        check()
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);target=root/BASE;target.mkdir(parents=True)
            for name in ['legacy-535-claim-review.json','persistence-40-audit.json']:
                shutil.copy(BASE/name,target/name)
            for name in ['legacy-remaining-review','persistence-history-review']:
                shutil.copytree(BASE/name,target/name)
            changes=[('legacy-remaining-review/batch-01.json',lambda x:x['claims'][0].update(full_claim_status='VERIFIED')),
                     ('legacy-remaining-review/batch-01.json',lambda x:x['claims'][0]['parts'][0].update(category='FACT')),
                     ('legacy-remaining-review/batch-01.json',lambda x:x['claims'][0].update(original_blob_sha='0'*40)),
                     ('persistence-history-review/batch-01.json',lambda x:x['items'][0].update(eligibility='ELIGIBLE')),
                     ('persistence-history-review/batch-01.json',lambda x:x['items'][0].update(artifact_id='another-subject'))]
            for file,mutate in changes:
                with self.subTest(file=file,mutate=mutate):
                    path=target/file;original=path.read_text();obj=json.loads(original);mutate(obj);path.write_text(json.dumps(obj))
                    with self.assertRaises(ValueError):check(root)
                    path.write_text(original)

if __name__=='__main__':unittest.main()
