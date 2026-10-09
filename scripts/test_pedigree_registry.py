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
        for _ in range(3):
            f = self.r.failure('req', 'parent:S', 'SOURCE_ERROR', source_key='other')
        self.assertTrue(f['retry_exhausted'])
        with self.assertRaisesRegex(ValueError, 'RETRY_EXHAUSTED'):
            self.r.failure('req', 'parent:S', 'SOURCE_ERROR', source_key='other')
        other_request = self.request(source_key='other')
        self.assertEqual(self.r.plan(other_request)['missing'][0]['retry_state'], 'RETRY_EXHAUSTED')
        self.assertEqual(self.r.plan(other_request, True)['missing'][0]['retry_state'], 'RETRY_EXHAUSTED')
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
        import subprocess
        def git(*args):
            return subprocess.check_output(['git', '-C', str(repo), *args], text=True).strip()
        git('init', '-q'); git('config', 'user.name', 'test')
        git('config', 'user.email', 'test@example.invalid')
        git('add', '.'); git('commit', '-qm', '移行元を固定')
        commit = git('rev-parse', 'HEAD')
        first = migrate(repo, self.root, commit, NOW)
        manifest = read(self.root / 'migration.json')
        second = migrate(repo, self.root, commit, NOW)
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

    def test_direct_ancestor_claim_cannot_hide_shared_parent_conflict(self):
        self.add('horse', [self.fact('parent:S', 'sire'),
                           self.fact('parent:SS', 'ancestor')])
        self.add('sire', [self.fact('parent:S', 'ancestor')])
        self.add('sire', [self.fact('parent:S', 'other', LATE)])
        result = self.r.edge('horse', 'SS', NOW)
        self.assertEqual(result['status'], 'CONFLICT')
        self.assertEqual(self.r.plan(self.request(fields=['parent:SS']))['missing'][0]['status'], 'CONFLICT')
        derived = self.r.derive('horse', ['ancestor'], 2, NOW)
        self.assertEqual(derived['containment']['ancestor']['status'], 'UNKNOWN')
        self.assertEqual(self.r.edge('horse', 'SS', EARLY)['status'], 'VERIFIED')

    def test_direct_long_path_cannot_hide_intermediate_conflict(self):
        self.add('horse', [self.fact('parent:S', 'sire'),
                           self.fact('parent:SSS', 'ancestor')])
        self.add('sire', [self.fact('parent:S', 'dam')])
        self.add('sire', [self.fact('parent:S', 'other', LATE)])
        self.assertEqual(self.r.edge('horse', 'SSS', NOW)['status'], 'CONFLICT')

    def test_identity_resolution_requires_explicit_versioned_update(self):
        unresolved = self.candidate('pending')
        unresolved['identity'] = {'name': '未同定馬', 'status': 'IDENTITY_UNRESOLVED',
                                  'external_ids': {}, 'aliases': []}
        self.r.save(unresolved)
        resolved = copy.deepcopy(unresolved)
        resolved['identity'].update(status='RESOLVED', external_ids={'registry': 'id-123'},
                                    identity_evidence={'source': 'BREEDING_DB', 'record_key': 'id-123'})
        before = read(self.r.path('pending'))
        with self.assertRaisesRegex(ValueError, 'silently changed'):
            self.r.save(resolved, digest(before))
        with self.assertRaisesRegex(ValueError, 'CONCURRENT_UPDATE'):
            self.r.update_identity(resolved, 'stale', 'checked provider', 'reviewer')
        receipt = self.r.update_identity(resolved, digest(before), 'checked provider', 'reviewer')
        self.assertTrue(receipt['identity_updated'])
        updated = read(self.r.path('pending'))
        self.assertEqual(updated['revisions'], before['revisions'])
        self.assertEqual(updated['identity_revisions'][0]['before'], before['identity'])
        self.assertEqual(updated['identity_revisions'][0]['after'], resolved['identity'])
        self.assertEqual(self.r.search('id-123')['status'], 'RESOLVED')
        self.assertEqual(self.r.audit()['status'], 'PASS')
        repeat = self.r.update_identity(resolved, digest(updated), 'checked provider', 'reviewer')
        self.assertFalse(repeat['identity_updated'])
        self.assertEqual(len(read(self.r.path('pending'))['identity_revisions']), 1)
        # The new canonical identity can now be used by regular save.
        self.r.save(dict(resolved, facts=[]), digest(updated))

    def test_identity_enrichment_is_auditable_and_rejects_reassignment(self):
        current = self.candidate('horse')
        current['identity']['external_ids']['another'] = 'second-id'
        old = read(self.r.path('horse'))
        self.r.update_identity(current, digest(old), 'additional original record', 'verifier')
        latest = read(self.r.path('horse'))
        changed = copy.deepcopy(current)
        changed['identity']['external_ids']['test'] = 'new-horse-id'
        with self.assertRaisesRegex(ValueError, 'external ID'):
            self.r.update_identity(changed, digest(latest), 'bad reassignment', 'verifier')
        changed = copy.deepcopy(current)
        changed['identity']['status'] = 'IDENTITY_UNRESOLVED'
        with self.assertRaisesRegex(ValueError, 'downgraded'):
            self.r.update_identity(changed, digest(latest), 'bad downgrade', 'verifier')
        latest['identity_revisions'][0]['reviewed_by'] = 'tampered'
        atomic(self.r.path('horse'), latest)
        self.assertEqual(self.r.audit()['status'], 'FAIL')

    def test_retry_count_is_checked_on_third_failure_and_after_backoff(self):
        self.r.plan(self.request(source_key='provider'))
        for attempt in range(1, 4):
            recorded = self.r.failure('req', 'parent:S', 'SOURCE_ERROR',
                                      source_key='provider', max_retries=2)
            self.assertEqual(recorded['retry_exhausted'], attempt == 3)
            self.assertEqual(recorded['max_retries'], 2)
        with patch('pedigree_registry.stamp', return_value='2026-11-01T00:00:00+00:00'):
            item = self.r.plan(self.request(source_key='provider'), True)['missing'][0]
        self.assertEqual(item['retry_state'], 'RETRY_EXHAUSTED')
        # The next provider is independent of the exhausted one.
        self.assertNotEqual(self.r.plan(self.request(source_key='new-provider'), True)['missing'][0].get('retry_state'),
                            'RETRY_EXHAUSTED')
        with self.assertRaisesRegex(ValueError, 'RETRY_EXHAUSTED'):
            self.r.failure('req', 'parent:S', 'SOURCE_ERROR',
                           source_key='provider', max_retries=100)

    def test_migration_uses_exact_git_commit_not_modified_worktree(self):
        import subprocess
        repo = Path(self.temp.name) / 'repo'
        path = repo / 'docs/yosou/example.md'
        path.parent.mkdir(parents=True)
        path.write_text('母父はA\n')
        def git(*args):
            return subprocess.check_output(['git', '-C', str(repo), *args], text=True).strip()
        git('init', '-q'); git('config', 'user.name', 'test')
        git('config', 'user.email', 'test@example.invalid')
        git('add', '.'); git('commit', '-qm', 'Aを保存')
        commit = git('rev-parse', 'HEAD')
        result = migrate(repo, self.root, commit, NOW)
        manifest = read(self.root / 'migration.json')
        self.assertEqual(result['extracted'], 1)
        self.assertEqual(manifest['claims'][0]['text'], '母父はA')
        path.write_text('母父はB\n')
        (repo / 'docs/yosou/untracked.md').write_text('母父はC\n')
        self.assertEqual(migrate(repo, self.root, commit, LATE), result)
        self.assertEqual(manifest, read(self.root / 'migration.json'))
        self.assertEqual(self.r.audit(repo=repo)['status'], 'PASS')
        with self.assertRaises(Exception):
            migrate(repo, self.root, 'no-such-commit', NOW)
        forged = copy.deepcopy(manifest)
        forged['claims'][0]['text'] = '母父はB'
        forged['claims'][0]['claim_id'] = digest({'commit': commit, 'path': forged['claims'][0]['path'],
                                                   'line': 1, 'text': '母父はB'})
        import hashlib
        forged['claims'][0]['source']['record_hash'] = hashlib.sha256('母父はB'.encode()).hexdigest()
        atomic(self.root / 'migration.json', forged)
        self.assertEqual(self.r.audit(repo=repo)['status'], 'FAIL')
        with self.assertRaisesRegex(ValueError, 'manifest differs'):
            migrate(repo, self.root, commit, NOW)
        self.assertEqual(read(self.root / 'migration.json'), forged)


    def test_identity_as_of_cutoff_does_not_retroactively_verify_attributes(self):
        old_candidate = self.candidate('later_identity', [self.fact('attribute:sex', '牝', EARLY)])
        old_candidate['identity'] = {'name': '調査中', 'aliases': [], 'external_ids': {},
                                      'status': 'IDENTITY_UNRESOLVED'}
        self.r.save(old_candidate)
        request = {'schema_version': SCHEMA, 'request_id': 'identity-asof',
                   'horse_key': 'later_identity', 'fields': ['attribute:sex'],
                   'data_cutoff': EARLY}
        self.assertEqual(self.r.fact('later_identity', 'attribute:sex', EARLY)['status'],
                         'IDENTITY_UNRESOLVED')
        self.assertEqual(self.r.plan(request)['missing'][0]['status'], 'IDENTITY_UNRESOLVED')
        upgrade = copy.deepcopy(old_candidate)
        upgrade['facts'] = []
        upgrade['identity'].update(
            status='RESOLVED', external_ids={'register': 'confirmed-later'},
            identity_evidence={'source': 'official', 'record_key': 'confirmed-later'})
        with patch('pedigree_registry.stamp', return_value=LATE):
            self.r.update_identity(upgrade, digest(read(self.r.path('later_identity'))),
                                   '元資料で照合', '確認者')
        # A later identity must not change a historical plan, source evidence or lookup.
        self.assertEqual(self.r.search('later_identity', EARLY)['status'],
                         'IDENTITY_UNRESOLVED')
        self.assertEqual(self.r.search('confirmed-later', EARLY)['matches'], [])
        self.assertEqual(self.r.search('confirmed-later', NOW)['status'], 'RESOLVED')
        self.assertEqual(self.r.fact('later_identity', 'attribute:sex', EARLY)['status'],
                         'IDENTITY_UNRESOLVED')
        self.assertEqual(self.r.plan(request)['missing'][0]['status'], 'IDENTITY_UNRESOLVED')
        verified = self.r.fact('later_identity', 'attribute:sex', NOW)
        self.assertEqual(verified['status'], 'VERIFIED')
        self.assertEqual(verified['identity_evidence'], upgrade['identity']['identity_evidence'])
        self.assertEqual(self.r.audit()['status'], 'PASS')

    def test_ancestor_identity_as_of_cutoff_blocks_direct_and_inferred_paths(self):
        unresolved = self.candidate('late_sire')
        unresolved['identity'] = {'name': '父候補', 'status': 'IDENTITY_UNRESOLVED',
                                  'external_ids': {}, 'aliases': []}
        self.r.save(unresolved)
        confirmed = copy.deepcopy(unresolved)
        confirmed['identity'].update(
            status='RESOLVED', external_ids={'register': 'late-sire-id'},
            identity_evidence={'source': 'official', 'record_key': 'late-sire-id'})
        with patch('pedigree_registry.stamp', return_value=LATE):
            self.r.update_identity(confirmed, digest(read(self.r.path('late_sire'))),
                                   '父候補の同定', '確認者')
        self.add('late_sire', [self.fact('parent:S', 'ancestor', EARLY)])
        self.add('horse', [self.fact('parent:S', 'late_sire', EARLY),
                           self.fact('parent:SS', 'ancestor', EARLY)])
        self.assertEqual(self.r.edge('horse', 'S', EARLY)['status'], 'IDENTITY_UNRESOLVED')
        self.assertEqual(self.r.edge('horse', 'SS', EARLY)['status'], 'IDENTITY_UNRESOLVED')
        self.assertEqual(self.r.fact('late_sire', 'parent:S', EARLY)['status'],
                         'IDENTITY_UNRESOLVED')
        self.assertEqual(self.r.edge('horse', 'SS', NOW)['status'], 'VERIFIED')
        self.assertEqual(self.r.derive('horse', ['ancestor'], 2, EARLY)['containment']['ancestor']['status'],
                         'UNKNOWN')
        self.assertEqual(self.r.audit()['status'], 'PASS')

    def test_identity_evidence_changes_only_from_revision_time(self):
        before = self.r.search('horse', EARLY)['matches'][0]['identity']
        enriched = self.candidate('horse')
        enriched['identity']['identity_evidence'] = {
            'source': 'new-provider', 'record_key': 'later-proof'}
        with patch('pedigree_registry.stamp', return_value=LATE):
            self.r.update_identity(enriched, digest(read(self.r.path('horse'))),
                                   '根拠更新', '確認者')
        self.assertEqual(self.r.search('horse', EARLY)['matches'][0]['identity'], before)
        self.assertEqual(self.r.search('horse', NOW)['matches'][0]['identity'],
                         enriched['identity'])
        with patch('pedigree_registry.stamp', return_value=EARLY):
            with self.assertRaisesRegex(ValueError, 'cannot precede'):
                changed = copy.deepcopy(enriched)
                changed['identity']['aliases'] = ['別名']
                self.r.update_identity(changed, digest(read(self.r.path('horse'))),
                                       '過去へ変更', '確認者')

    def test_force_cannot_restart_elapsed_budget_and_failure_stays_blocked(self):
        request = self.request(budget_seconds=2, source_key='provider')
        with patch('pedigree_registry.stamp', return_value=EARLY):
            original = self.r.plan(request)
            first = self.r.failure('req', 'parent:S', 'SOURCE_ERROR',
                                   source_key='provider', budget_seconds=2)
        self.assertFalse(first['retry_exhausted'])
        with patch('pedigree_registry.stamp', return_value=LATE):
            forced = self.r.plan(request, True)
            normal = self.r.plan(request)
            self.assertEqual(forced['missing'][0]['retry_state'], 'BUDGET_EXHAUSTED')
            self.assertEqual(normal['missing'][0]['retry_state'], 'BUDGET_EXHAUSTED')
            self.assertEqual(forced['started_at'], original['started_at'])
            self.assertEqual(forced['deadline_at'], original['deadline_at'])
            self.assertEqual(forced['failures'], normal['failures'])
            with self.assertRaisesRegex(ValueError, 'BUDGET_EXHAUSTED'):
                self.r.failure('req', 'parent:S', 'SOURCE_ERROR',
                               source_key='provider', budget_seconds=2)
        self.assertEqual(len(read(self.root / 'research/req.json')['failures']), 1)

    def test_expired_request_without_failures_cannot_be_forced(self):
        request = self.request(budget_seconds=1)
        with patch('pedigree_registry.stamp', return_value=EARLY):
            initial = self.r.plan(request)
        with patch('pedigree_registry.stamp', return_value=LATE):
            again = self.r.plan(request, True)
            self.assertEqual(again['missing'][0]['retry_state'], 'BUDGET_EXHAUSTED')
            self.assertEqual(again['started_at'], initial['started_at'])
            with self.assertRaisesRegex(ValueError, 'BUDGET_EXHAUSTED'):
                self.r.failure('req', 'parent:S', 'SOURCE_ERROR')


if __name__ == '__main__': unittest.main()
