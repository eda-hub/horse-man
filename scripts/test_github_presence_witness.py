import json
import tempfile
import unittest
from pathlib import Path
from check_github_presence_witness import check, MANIFEST


class GithubPresenceWitnessTest(unittest.TestCase):
    root = Path(__file__).resolve().parents[1]

    def run_changed(self, change):
        data = json.loads((self.root / MANIFEST).read_text())
        change(data)
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json') as f:
            json.dump(data, f)
            f.flush()
            return check(self.root, f.name)

    def test_real_witnesses_preserve_missing_readback(self):
        result = check(self.root)
        self.assertEqual(result['witness_count'], 9)
        self.assertEqual(len(result['races']), 3)
        for row in result['races']:
            self.assertFalse(row['formal_kpi_promoted'])
            self.assertEqual(row['server_witness_order_consistent'], 'NIIGATA' not in row['race_id'])

    def test_late_witness_rejected(self):
        with self.assertRaisesRegex(ValueError, 'late or reversed'):
            self.run_changed(lambda d: d['items'][0]['run'].update(created_at='2026-10-17T06:15:00Z', run_started_at='2026-10-17T06:15:00Z'))

    def test_wrong_commit_rejected(self):
        with self.assertRaisesRegex(ValueError, 'binding'):
            self.run_changed(lambda d: d['items'][0]['run'].update(head_sha='0' * 40))

    def test_wrong_hash_rejected(self):
        with self.assertRaisesRegex(ValueError, 'bytes mismatch'):
            self.run_changed(lambda d: d['items'][0].update(sha256='0' * 64))

    def test_readback_promotion_rejected(self):
        with self.assertRaisesRegex(ValueError, 'cannot certify'):
            self.run_changed(lambda d: d.update(readback_proven=True))

    def test_missing_fix_rejected(self):
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            self.run_changed(lambda d: d['items'].pop(1))


if __name__ == '__main__':
    unittest.main()
