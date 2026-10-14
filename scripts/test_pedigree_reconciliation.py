"""Keep the fixed source reconciliation valid after later legitimate writes."""
import copy
from datetime import datetime, timezone
from pathlib import Path
import shutil
import tempfile
import unittest

from check_pedigree_reconciliation import check
from pedigree_registry import Registry, SCHEMA, digest, read


class ReconciliationHistoryTest(unittest.TestCase):
    def test_later_identity_and_parent_conflict_preserve_fixed_reconciliation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = Path(__file__).resolve().parents[1] / 'data/pedigree'
            shutil.copytree(source, root / 'data/pedigree')
            registry = Registry(root / 'data/pedigree')
            original_count = len(registry.records())
            registry.save({
                'schema_version': SCHEMA, 'horse_key': 'future-test-only',
                'identity': {'name': 'test fixture only', 'status': 'RESOLVED',
                             'external_ids': {'fixture': 'future-only'},
                             'identity_evidence': {'source': 'fixture', 'record_key': 'future-only'}},
                'facts': [],
            })
            key = 'jbis-0001338391'
            original = read(registry.path(key))
            fact = copy.deepcopy(original['revisions'][0])
            for field in ('revision_id', 'previous_revision', 'input_hash', 'saved_at', 'content_hash'):
                fact.pop(field, None)
            fact.update(first_observed_at=datetime.now(timezone.utc).isoformat(),
                        value='jbis-0000337102')
            fact['captured_at'] = fact['first_observed_at']
            fact['source'] = {'source_class': 'BREEDING_DB', 'origin_group': 'test-fixture-only',
                              'acquisition_method': 'fixture', 'record_key': 'future-conflict-test-only',
                              'record_hash': digest('future-conflict-test-only')}
            fact['verification']['reviewed_by'] = 'test fixture'
            registry.save({'schema_version': SCHEMA, 'horse_key': key,
                           'identity': original['identity'], 'facts': [fact]}, digest(original))
            self.assertEqual(registry.fact(key, fact['field'], fact['captured_at'])['status'], 'CONFLICT')
            result = check(root)
            self.assertEqual(result['status'], 'PASS')
            self.assertEqual(result['registry_audit']['horses'], original_count + 1)
            self.assertEqual(result['objective_components'], 106)
