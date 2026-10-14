import json
import tempfile
import unittest
from pathlib import Path
from chat_market_live_resume import resume
from cycle04_operations import fingerprint


class LiveResume(unittest.TestCase):
    def test_no_evidence_is_wait_not_zero_meeting_measurement(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);out=resume(root)
            self.assertEqual(out['status'],'WAITING_REAL_EVIDENCE')
            self.assertIsNone(out['measured_meeting_count'])
            self.assertFalse(out['live_validation_accepted'])
            self.assertTrue(out['prediction_recommendation_can_complete_without_market'])
            self.assertEqual(list(root.iterdir()),[])

    def test_future_acquisition_cannot_enter_the_existing_live_checker(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            payload=json.dumps({'market':{'acquired_at_jst':'2026-10-17T09:59:00+09:00'}}).encode()
            (root/'market.json').write_bytes(payload)
            ref={'artifact_path':'market.json','sha256':fingerprint(payload)}
            manifest=json.dumps({'schema_version':'chat-market-live-validation-v1','entries':[{'market_ref':ref}]}).encode()
            (root/'manifest.json').write_bytes(manifest)
            with self.assertRaises(ValueError):
                resume(root,{'artifact_path':'manifest.json','sha256':fingerprint(manifest)},'2026-10-14T12:00:00+09:00')

    def test_empty_manifest_cannot_certify_a_live_measurement(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);raw=json.dumps({'schema_version':'chat-market-live-validation-v1','entries':[]}).encode()
            (root/'manifest.json').write_bytes(raw)
            ref={'artifact_path':'manifest.json','sha256':fingerprint(raw)}
            with self.assertRaises(ValueError):resume(root,ref)
            ref['sha256']='0'*64
            with self.assertRaises(ValueError):resume(root,ref)


if __name__=='__main__':unittest.main()
