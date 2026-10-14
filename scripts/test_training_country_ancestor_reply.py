import copy,json,tempfile,unittest
from pathlib import Path
from pedigree_registry import Registry
from check_training_country_ancestors import BASE,check_user_resolution

class AncestorReplyTests(unittest.TestCase):
    def test_user_reply_and_rejection_of_wrong_identity_hash_time_or_history(self):
        directory=BASE/'s6-designated-ancestors'
        if not (directory/'explicit-country-reply.json').exists():self.skipTest('saved user reply absent')
        manifest=json.loads((directory/'explicit-country-reply.json').read_text())
        scope=json.loads((BASE/'designated-ancestor-target-review.json').read_text())
        progress=json.loads((directory/'progress.json').read_text())
        registry=Registry('data/pedigree')
        check_user_resolution(directory,registry,scope,progress)
        for field,value in [('subject_name','別の馬'),('user_reply_sha256','0'*64),('received_at',manifest['historical_cutoff']),('before_record_hash','0'*64)]:
            with self.subTest(field=field),tempfile.TemporaryDirectory() as temp:
                altered=copy.deepcopy(manifest);altered[field]=value
                Path(temp,'explicit-country-reply.json').write_text(json.dumps(altered))
                with self.assertRaises(ValueError):check_user_resolution(Path(temp),registry,scope,progress)

if __name__=='__main__':unittest.main()
