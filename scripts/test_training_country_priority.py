"""優先調査の順番・所属証拠・時点・旧履歴の誤認を拒否する。"""
import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from check_training_country_priority import BASE, CHECKPOINT, check, read


class TrainingCountryPriorityTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = Path(__file__).resolve().parent.parent
        manifest = read(self.source / CHECKPOINT)
        batch = read(self.source / BASE / 's5-batches/batch-01/verification.json')
        self.batch_path = BASE / 's5-batches/batch-01/verification.json'
        paths = {CHECKPOINT, Path(manifest['source_inventory_path']), self.batch_path}
        paths.update(Path('data/pedigree/horses/' + s['horse_key'] + '.json') for s in manifest['subjects'])
        for review in batch['reviews']:
            for proof in [review['profile']] + review['affiliations']:
                paths.update((Path(proof['raw_path']), Path(proof['capture_path'])))
        for path in paths:
            target = self.root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(self.source / path, target)

    def mutate(self, path, mutate):
        value = read(self.root / path)
        mutate(value)
        (self.root / path).write_text(json.dumps(value, ensure_ascii=False))

    def test_accept_saved_checkpoint_and_first_ten(self):
        result = check(self.root)
        self.assertEqual(result['batch_01']['registered'], 102)

    def test_reject_skip_high_priority_horse(self):
        self.mutate(self.batch_path, lambda b: b['reviews'].reverse())
        with self.assertRaisesRegex(ValueError, 'first ten'):
            check(self.root)

    def test_reject_birth_country_as_makfi_training_country(self):
        self.mutate(self.batch_path, lambda b: b['reviews'][5]['affiliations'][0].update(country='GB'))
        with self.assertRaisesRegex(ValueError, 'Makfi trained FR'):
            check(self.root)

    def test_reject_old_uae_as_latest_discreet_country(self):
        self.mutate(self.batch_path, lambda b: b['reviews'][8].update(selected_country='AE'))
        with self.assertRaisesRegex(ValueError, 'selected country'):
            check(self.root)

    def test_reject_original_body_tampering(self):
        batch = read(self.root / self.batch_path)
        path = self.root / batch['reviews'][0]['affiliations'][0]['raw_path']
        path.write_bytes(path.read_bytes() + b'changed')
        with self.assertRaisesRegex(ValueError, 'capture integrity'):
            check(self.root)

    def test_reject_false_original_pdf_capture_claim(self):
        batch = read(self.root / self.batch_path)
        path = batch['reviews'][2]['affiliations'][0]['capture_path']
        self.mutate(path, lambda m: m.update(original_pdf_bytes_captured=True))
        with self.assertRaisesRegex(ValueError, 'not raw PDF'):
            check(self.root)

    def test_reject_changed_old_fact_even_with_same_stored_hash(self):
        batch = read(self.root / self.batch_path)
        path = Path('data/pedigree/horses/' + batch['reviews'][0]['horse_key'] + '.json')
        self.mutate(path, lambda r: r['revisions'][0].update(status='UNVERIFIED'))
        with self.assertRaisesRegex(ValueError, 'revision content hash'):
            check(self.root)

    def test_reject_future_capture(self):
        batch = read(self.root / self.batch_path)
        path = batch['reviews'][0]['affiliations'][0]['capture_path']
        self.mutate(path, lambda m: m.update(captured_at='2099-01-01T00:00:00+00:00'))
        with self.assertRaisesRegex(ValueError, 'capture integrity'):
            check(self.root)


if __name__ == '__main__':
    unittest.main()
