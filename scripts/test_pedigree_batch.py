import tempfile
import unittest
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from pedigree_batch import BatchRegistry
from pedigree_registry import SCHEMA, read, digest


def candidate(key, external):
    return {'schema_version': SCHEMA, 'horse_key': key, 'identity': {
        'name': key, 'aliases': [], 'birth_year': 2020,
        'external_ids': {'JBIS': external}, 'status': 'RESOLVED',
        'identity_evidence': {'source': 'test', 'record_key': external}}, 'facts': []}


class BatchTests(unittest.TestCase):
    def test_saved_identity_blocks_duplicate_and_index_survives_exception(self):
        with tempfile.TemporaryDirectory() as tmp:
            reg = BatchRegistry(tmp)
            with self.assertRaisesRegex(ValueError, 'external ID'):
                with reg.batch():
                    reg.save(candidate('horse-a', '001'))
                    reg.save(candidate('horse-b', '001'))
            self.assertTrue(reg.path('horse-a').exists())
            self.assertFalse(reg.path('horse-b').exists())
            self.assertEqual(read(Path(tmp) / 'aliases.json')['aliases'],
                             {'horse-a': ['horse-a']})
            self.assertIsNone(reg._batch_records)
            reg.save(candidate('horse-b', '002'))
            self.assertEqual(len(list(reg.records())), 2)

    def test_batch_rejects_stale_cas_and_nested_writer_batch(self):
        with tempfile.TemporaryDirectory() as tmp:
            reg = BatchRegistry(tmp)
            with reg.batch():
                reg.save(candidate('horse-a', '001'))
                with self.assertRaisesRegex(ValueError, 'CONCURRENT_UPDATE'):
                    reg.save(candidate('horse-a', '001'), '0' * 64)
                with self.assertRaisesRegex(ValueError, 'nested batch'):
                    with reg.batch():
                        pass

    def test_other_thread_cannot_bypass_lock_or_change_batch_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            reg = BatchRegistry(tmp)
            with reg.batch():
                reg.save(candidate('horse-a', '001'))
                with ThreadPoolExecutor(max_workers=1) as pool:
                    with self.assertRaisesRegex(ValueError, 'another thread'):
                        pool.submit(reg.save, candidate('horse-b', '002')).result()
                self.assertEqual(reg._saving_key, 'horse-a')
                self.assertFalse(reg.path('horse-b').exists())

    def test_explicit_identity_update_refreshes_cached_identity_and_aliases(self):
        with tempfile.TemporaryDirectory() as tmp:
            reg = BatchRegistry(tmp)
            with reg.batch():
                reg.save(candidate('horse-a', '001'))
                change = candidate('horse-a', '001')
                change['identity']['aliases'] = ['new-alias']
                reg.update_identity(change, digest(read(reg.path('horse-a'))),
                                    'verified alternative name', 'test reviewer')
                self.assertEqual(list(reg.records())[0]['identity']['aliases'], ['new-alias'])
            self.assertEqual(read(Path(tmp) / 'aliases.json')['aliases']['new-alias'], ['horse-a'])

    def test_audit_loads_identity_set_once_and_still_detects_duplicate_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            reg = BatchRegistry(tmp)
            reg.save(candidate('horse-a', '001'))
            reg.save(candidate('horse-b', '002'))
            with patch.object(reg, 'records', wraps=reg.records) as records:
                self.assertEqual(reg.audit()['status'], 'PASS')
                self.assertEqual(records.call_count, 1)
            record = read(reg.path('horse-b'))
            record['identity']['external_ids']['JBIS'] = '001'
            from pedigree_registry import atomic
            atomic(reg.path('horse-b'), record)
            self.assertEqual(reg.audit()['status'], 'FAIL')

    def test_identity_update_indexes_new_provider_and_rejects_invalid_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            reg = BatchRegistry(tmp)
            reg.save(candidate('horse-a', '001'))
            with reg.batch():
                change = candidate('horse-a', '001')
                change['identity']['external_ids']['NETKEIBA'] = 'new-id'
                reg.update_identity(change, digest(read(reg.path('horse-a'))),
                                    'verified native ID', 'test reviewer')
                duplicate = candidate('horse-b', '002')
                duplicate['identity']['external_ids']['NETKEIBA'] = 'new-id'
                with self.assertRaisesRegex(ValueError, 'external ID'):
                    reg.save(duplicate)
                invalid = candidate('horse-b', '002')
                invalid['identity']['external_ids']['NETKEIBA'] = []
                with self.assertRaises(ValueError):
                    reg.save(invalid)
            self.assertFalse(reg.path('horse-b').exists())


if __name__ == '__main__':
    unittest.main()
