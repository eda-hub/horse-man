#!/usr/bin/env python3
"""推奨個別完了のR01/R02独立保存履歴とゲート参照を回帰検査。"""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from task_completion import recommendation_completion


class RecommendationReceiptHistoryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.rpath = 'docs/validation/recommendations/2026-10-17/test.json'
        self.gpath = 'docs/validation/recommendation-gates/2026-10-17/test.json'
        self.receipt_path = self.root / 'docs/validation/persistence-receipts/2026-10-17.md'
        self.rec = {
            'race_date_jst': '2026-10-17', 'race_id': '2026-10-17-TOKYO-11',
            'recommendation_id': 'TEST-TOKYO-11-REC',
            'fixed_at_jst': '2026-10-17T15:35:00+09:00',
            'scheduled_post_time_jst': '2026-10-17T15:45:00+09:00',
        }
        self.raw = (json.dumps(self.rec, ensure_ascii=False) + '\n').encode()
        self.digest = hashlib.sha256(self.raw).hexdigest()
        self.write(self.rpath, self.raw.decode())
        self.write(self.gpath, json.dumps({
            'evidence_ref': {
                'artifact_id': self.rec['recommendation_id'],
                'artifact_path': self.rpath,
                'receipt_id': 'TEST-TOKYO-11-REC-R02',
                'persist_verified_at_jst': '2026-10-17T15:36:00+09:00',
            },
        }))

    def write(self, path, text):
        f = self.root / path
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding='utf-8')

    def receipt(self, ident, *, status='RECEIPT_VERIFIED', digest=None,
                previous=None):
        rec = {
            'receipt_id': ident,
            'artifact_id': self.rec['recommendation_id'],
            'artifact_path': self.rpath,
            'content_sha256': self.digest if digest is None else digest,
            'scheduled_post_time_jst': self.rec['scheduled_post_time_jst'],
            'persist_verified_at_jst': '2026-10-17T15:36:00+09:00',
            'artifact_persist_status': 'PERSIST_VERIFIED',
            'receipt_persist_status': status,
            'timing_eligibility': 'PRE_RACE_ELIGIBLE',
        }
        if status == 'RECEIPT_VERIFIED':
            rec['receipt_verified_at_jst'] = '2026-10-17T15:37:00+09:00'
        if previous:
            rec['previous_receipt_ref'] = previous
        return rec

    def run_case(self, receipts):
        blocks = ''.join('\u0060\u0060\u0060persistence-receipt-v1\n' +
                         json.dumps(r, ensure_ascii=False) + '\n\u0060\u0060\u0060\n'
                         for r in receipts)
        self.receipt_path.parent.mkdir(parents=True, exist_ok=True)
        self.receipt_path.write_text(blocks, encoding='utf-8')
        with patch('recommendation.validate_snapshot', return_value=self.rec), \
             patch('recommendation.verify', return_value=self.rec):
            return recommendation_completion(self.root, self.rpath, self.gpath,
                                             fixed_content_sha256=self.digest)

    def test_initial_and_verified_receipts_coexist(self):
        prior = self.receipt('TEST-TOKYO-11-REC-R01', status='RECEIPT_READBACK_PENDING')
        final = self.receipt('TEST-TOKYO-11-REC-R02',
                             previous='TEST-TOKYO-11-REC-R01')
        result = self.run_case([prior, final])
        self.assertTrue(result['checks']['receipt']['result'])
        self.assertTrue(result['checks']['execution_gate']['result'])
        self.assertTrue(result['complete'])

    def test_duplicated_pinned_receipt_is_rejected(self):
        final = self.receipt('TEST-TOKYO-11-REC-R02')
        result = self.run_case([final, final])
        self.assertFalse(result['checks']['receipt']['result'])

    def test_conflicting_predecessor_is_rejected(self):
        prior = self.receipt('TEST-TOKYO-11-REC-R01', status='RECEIPT_READBACK_PENDING',
                             digest='f' * 64)
        final = self.receipt('TEST-TOKYO-11-REC-R02',
                             previous='TEST-TOKYO-11-REC-R01')
        result = self.run_case([prior, final])
        self.assertFalse(result['checks']['receipt']['result'])

    def test_pending_receipt_without_verified_readback_is_rejected(self):
        result = self.run_case([self.receipt('TEST-TOKYO-11-REC-R01',
                                            status='RECEIPT_READBACK_PENDING')])
        self.assertFalse(result['checks']['receipt']['result'])


    def test_actual_kyoto_and_tokyo_11_verified_receipts(self):
        """実ファイルの読戻し証跡はR01が残っていても個別に合格させる。"""
        root = Path(__file__).resolve().parent.parent
        for track in ('KYOTO', 'TOKYO'):
            ident = f'20261017-{track}-11-REC-S01'
            artifact = f'docs/validation/recommendations/2026-10-17/{ident}.json'
            gate = f'docs/validation/recommendation-gates/2026-10-17/2026-10-17-{track}-11.json'
            content = (root / artifact).read_bytes()
            result = recommendation_completion(root, artifact, gate,
                                               fixed_content_sha256=hashlib.sha256(content).hexdigest())
            self.assertTrue(result['checks']['artifact']['result'],
                            (track, result['checks']['artifact']))
            self.assertTrue(result['checks']['receipt']['result'],
                            (track, result['checks']['receipt']))
            self.assertTrue(result['checks']['content_match']['result'],
                            (track, result['checks']['content_match']))
            self.assertFalse(result['eligibility_promoted'])


if __name__ == '__main__':
    unittest.main()
