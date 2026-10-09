import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from pedigree_registry import Registry, SCHEMA, digest, read, atomic, migrate

EARLY = '2026-09-01T00:00:00+00:00'
LATE = '2026-10-01T00:00:00+00:00'
NOW = '2026-10-09T01:00:00+00:00'


class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'data'
        self.r = Registry(self.root)
        for key in ('horse', 'sire', 'dam', 'ancestor', 'other'):
            self.add(key)

    def candidate(self, key, facts=None, name=None):
        return {'schema_version': SCHEMA, 'horse_key': key,
                'identity': {'name': name or key, 'aliases': [], 'status': 'RESOLVED',
                             'birth_year': 2020, 'external_ids': {'test': key},
                             'identity_evidence': {'source': 'test-provider', 'record_key': key}},
                'facts': facts or []}

    def add(self, key, facts=None, **kwargs):
        old = read(self.r.path(key))
        return self.r.save(self.candidate(key, facts, **kwargs), digest(old) if old else None)

    def fact(self, field, value, at=EARLY, source='BREEDING_DB'):
        return {'field': field, 'value': value, 'status': 'VERIFIED',
                'first_observed_at': at, 'captured_at': at,
                'source': {'source_class': source, 'origin_group': 'test',
                           'acquisition_method': 'manual-source-check', 'record_key': value,
                           'record_hash': digest(value)},
                'verification': {'identity_checked': True, 'source_checked': True,
                                 'relationship_checked': True, 'reviewed_by': 'test-reviewer'}}

    def request(self, **kwargs):
        return dict({'schema_version': SCHEMA, 'request_id': 'req', 'horse_key': 'horse',
                     'data_cutoff': NOW, 'fields': ['parent:S']}, **kwargs)

    def test_registered_request_requires_zero_external_queries(self):
        self.add('horse', [self.fact('parent:S', 'sire')])
        a = self.r.plan(self.request()); b = self.r.plan(self.request())
        self.assertEqual(a, b)
        self.assertEqual(b['status'], 'VERIFIED')
        self.assertEqual(b['metrics']['external_queries'], 0)

    def test_only_missing_dam_sire_requested(self):
        self.add('horse', [self.fact('parent:S', 'sire')])
        plan = self.r.plan(self.request(fields=['parent:S', 'parent:DS']))
        self.assertEqual([m['item'] for m in plan['missing']], ['parent:DS'])

    def test_common_ancestor_reuses_independent_record(self):
        self.add('horse', [self.fact('parent:S', 'sire')])
        self.add('other', [self.fact('parent:S', 'sire')])
        self.add('sire', [self.fact('parent:S', 'ancestor')])
        a = self.r.edge('horse', 'SS', NOW); b = self.r.edge('other', 'SS', NOW)
        self.assertEqual(a['revision_id'], b['revision_id'])
        self.assertEqual(a['value'], 'ancestor')

    def test_same_name_not_merged(self):
        self.add('twin1', name='同名馬'); self.add('twin2', name='同名馬')
        self.assertEqual(len(self.r.search('同名馬')['matches']), 2)
        self.assertEqual(self.r.search('同名馬')['status'], 'IDENTITY_UNRESOLVED')
        plan = self.r.plan(dict(self.request(), horse_key=None, query='同名馬'))
        self.assertEqual(plan['missing'][0]['status'], 'IDENTITY_UNRESOLVED')

    def test_absent_only_with_complete_scope(self):
        a = self.r.derive('horse', ['ancestor'], 1, NOW)
        self.assertEqual(a['containment']['ancestor']['status'], 'UNKNOWN')
        self.add('horse', [self.fact('parent:S', 'sire'), self.fact('parent:D', 'dam')])
        b = self.r.derive('horse', ['ancestor', 'sire'], 1, NOW)
        self.assertEqual(b['containment']['ancestor']['status'], 'ABSENT_WITHIN_SCOPE')
        self.assertEqual(b['containment']['sire']['status'], 'PRESENT')
        self.assertEqual(b['containment']['sire']['positions'], ['S'])

    def test_taxonomy_change_no_new_raw_revision(self):
        self.add('horse', [self.fact('parent:S', 'sire')])
        for v, line in [('v1', 'line A'), ('v2', 'line B')]:
            atomic(self.root / 'taxonomies' / (v + '.json'),
                   {'schema_version': SCHEMA, 'version': v, 'source': 'test classification',
                    'first_observed_at': EARLY, 'ancestor_lines': {'sire': line}})
        before = digest(read(self.r.path('horse')))
        a = self.r.derive('horse', [], 2, NOW, 'v1'); b = self.r.derive('horse', [], 2, NOW, 'v2')
        self.assertNotEqual(a['lines'], b['lines'])
        self.assertEqual(before, digest(read(self.r.path('horse'))))

    def test_conflict_preserved_and_authoritative_correction(self):
        self.add('horse', [self.fact('parent:S', 'sire')])
        self.add('horse', [self.fact('parent:S', 'other', LATE)])
        self.assertEqual(self.r.fact('horse', 'parent:S', NOW)['status'], 'CONFLICT')
        self.assertEqual(self.r.fact('horse', 'parent:S', EARLY)['value'], 'sire')
        old = read(self.r.path('horse'))
        correction = self.fact('parent:S', 'sire', NOW, 'OFFICIAL_JRA')
        correction['supersedes'] = [r['revision_id'] for r in old['revisions']]
        correction['correction_reason'] = 'official correction after identity recheck'
        self.add('horse', [correction])
        self.assertEqual(self.r.fact('horse', 'parent:S', NOW)['status'], 'VERIFIED')
        self.assertEqual(len(read(self.r.path('horse'))['revisions']), 3)
        self.assertEqual(self.r.fact('horse', 'parent:S', LATE)['status'], 'CONFLICT')

    def test_cutoff_excludes_late_fact(self):
        self.add('horse', [self.fact('parent:S', 'sire', LATE)])
        self.assertEqual(self.r.fact('horse', 'parent:S', EARLY)['status'], 'NOT_FOUND')
        self.assertEqual(self.r.fact('horse', 'parent:S', NOW)['status'], 'VERIFIED')

    def test_retry_save_is_idempotent_and_stale_hash_rejected(self):
        old = read(self.r.path('horse'))
        self.add('horse', [self.fact('parent:S', 'sire')])
        with self.assertRaisesRegex(ValueError, 'CONCURRENT_UPDATE'):
            self.r.save(self.candidate('horse', [self.fact('parent:D', 'dam')]), digest(old))
        self.assertEqual(self.add('horse', [self.fact('parent:S', 'sire')])['added_revisions'], [])
        self.assertEqual(len(read(self.r.path('horse'))['revisions']), 1)

    def test_full_manual_candidate_roundtrip(self):
        first = self.r.plan(self.request())
        self.assertEqual(first['status'], 'PARTIAL')
        receipt = self.add('horse', [self.fact('parent:S', 'sire')])
        self.assertEqual(receipt['content_hash'], digest(read(self.r.path('horse'))))
        self.assertEqual(self.r.plan(self.request())['status'], 'VERIFIED')
        self.assertEqual(receipt['snapshot_persistence'], 'NOT_EVALUATED')
        self.assertEqual(receipt['git_persistence'], 'UNCONFIRMED')

    def test_failure_types_retry_limit_and_force(self):
        self.r.plan(self.request())
        not_found = self.r.failure('req', 'parent:S', 'NOT_FOUND')
        self.assertEqual(not_found['status'], 'NOT_FOUND')
        self.assertEqual(self.r.plan(self.request())['missing'][0]['retry_state'], 'DEFERRED')
        self.assertNotIn('retry_state', self.r.plan(self.request(), True)['missing'][0])
        for _ in range(4):
            f = self.r.failure('req', 'parent:S', 'SOURCE_ERROR', source_key='other')
        self.assertTrue(f['retry_exhausted'])
        self.assertEqual(self.r.failure('req', 'parent:S', 'SAVE_ERROR')['status'], 'SAVE_ERROR')

    def test_legacy_claim_never_verified(self):
        fact = self.fact('parent:S', 'sire', source='LEGACY_REPOSITORY')
        with self.assertRaises(ValueError): self.add('horse', [fact])
        fact['status'] = 'UNVERIFIED'
        self.add('horse', [fact])
        self.assertEqual(self.r.plan(self.request())['missing'][0]['status'], 'UNVERIFIED')

    def test_production_accepts_no_trends_or_scores_as_facts(self):
        for field in ('trend:Danzig', 'score:pedigree', 'race_statistics'):
            with self.assertRaises(ValueError): self.add('horse', [self.fact(field, 'sire')])

    def test_save_error_not_claimed_success(self):
        with patch('pedigree_registry.os.replace', side_effect=OSError('disk full')):
            with self.assertRaises(OSError): self.add('horse', [self.fact('parent:S', 'sire')])
        self.assertEqual(self.r.fact('horse', 'parent:S', NOW)['status'], 'NOT_FOUND')

    def test_future_db_writer_disables_json_updates(self):
        atomic(self.root / 'writer.json', {'writer': 'DB'})
        with self.assertRaisesRegex(ValueError, 'disabled'):
            self.add('horse', [self.fact('parent:S', 'sire')])

    def test_audit_detects_tampered_revision(self):
        self.add('horse', [self.fact('parent:S', 'sire')])
        self.assertEqual(self.r.audit()['status'], 'PASS')
        horse = read(self.r.path('horse')); horse['revisions'][0]['value'] = 'dam'
        atomic(self.r.path('horse'), horse)
        self.assertEqual(self.r.audit()['status'], 'FAIL')

    def test_migration_is_searchable_unverified_and_repeatable(self):
        repo = Path(self.temp.name) / 'repo'
        p = repo / 'docs/yosou/example.md'; p.parent.mkdir(parents=True)
        p.write_text('父系Danzig内包の仮説\n本文\n母父の調教国は未確認\n')
        first = migrate(repo, self.root, 'abc', NOW)
        manifest = read(self.root / 'migration.json')
        second = migrate(repo, self.root, 'abc', NOW)
        self.assertEqual(first, second)
        self.assertEqual(manifest, read(self.root / 'migration.json'))
        self.assertEqual(first['verified'], 0)
        self.assertTrue(all(c['status'] == 'UNVERIFIED' for c in manifest['claims']))
        self.assertIn('past chats', manifest['unaccessed'])

    def test_unknown_ancestor_and_bad_timestamp_rejected(self):
        with self.assertRaises(ValueError): self.add('horse', [self.fact('parent:S', 'unknown')])
        with self.assertRaises(ValueError): self.add('horse', [self.fact('parent:S', 'sire', '2026-09-01')])
        with self.assertRaises(ValueError): self.r.derive('horse', [], 99, NOW)

    def test_external_ids_cannot_duplicate(self):
        c = self.candidate('new'); c['identity']['external_ids'] = {'test': 'horse'}
        with self.assertRaises(ValueError): self.r.save(c)

    def test_request_id_cannot_replace_previous_request(self):
        self.r.plan(self.request())
        with self.assertRaises(ValueError): self.r.plan(self.request(fields=['parent:D']))

    def test_cycle_rejected(self):
        self.add('horse', [self.fact('parent:S', 'sire')])
        with self.assertRaisesRegex(ValueError, 'cycle'):
            self.add('sire', [self.fact('parent:D', 'horse')])

    def test_direct_path_and_shared_ancestor_disagreement_is_conflict(self):
        self.add('horse', [self.fact('parent:S', 'sire'), self.fact('parent:SS', 'dam')])
        self.add('sire', [self.fact('parent:S', 'ancestor')])
        self.assertEqual(self.r.edge('horse', 'SS', NOW)['status'], 'CONFLICT')

    def test_source_error_budget_exhaustion(self):
        self.r.plan(self.request())
        with patch('pedigree_registry.stamp', return_value=EARLY):
            self.r.failure('req', 'parent:S', 'SOURCE_ERROR', budget_seconds=1)
        with patch('pedigree_registry.stamp', return_value=LATE):
            failure = self.r.failure('req', 'parent:S', 'SOURCE_ERROR', budget_seconds=1)
        self.assertTrue(failure['retry_exhausted'])

    def test_production_request_cannot_ask_for_score_or_trend(self):
        with self.assertRaises(ValueError):
            self.r.plan(self.request(fields=['attribute:score']))

    def test_late_taxonomy_excluded(self):
        atomic(self.root / 'taxonomies/v1.json', {'schema_version': SCHEMA, 'version': 'v1',
               'source': 'test', 'first_observed_at': LATE, 'ancestor_lines': {}})
        with self.assertRaises(ValueError): self.r.derive('horse', [], 2, EARLY, 'v1')

    def test_git_commit_readback_and_branch_cas(self):
        import subprocess
        from pedigree_registry import git_save
        repo = Path(self.temp.name)
        def git(*args):
            return subprocess.check_output(['git', '-C', str(repo), *args], text=True).strip()
        git('init', '-q'); git('config', 'user.name', 'test'); git('config', 'user.email', 'test@example.invalid')
        (repo / '.gitignore').write_text('**/.writer.lock\n')
        git('add', '.'); git('commit', '-qm', '初期状態')
        git('switch', '-qc', 'research/pedigree/test')
        old_head = git('rev-parse', 'HEAD')
        self.add('horse', [self.fact('parent:S', 'sire')])
        result = git_save(repo, self.root, old_head)
        self.assertEqual(result['persistence'], 'LOCAL_GIT_READBACK_VERIFIED')
        self.assertEqual(result['snapshot_persistence'], 'NOT_EVALUATED')
        self.assertNotEqual(old_head, result['commit_sha'])
        with self.assertRaisesRegex(ValueError, 'HEAD changed'):
            git_save(repo, self.root, old_head)


if __name__ == '__main__': unittest.main()
