#!/usr/bin/env python3
"""指定祖先28表記の調査対象と、既存Registryを固定時点で照合する。"""
import hashlib
import json
from pathlib import Path

from pedigree_registry import Registry, digest, dt, stamp


BASE = Path('data/pedigree/reconciliations/2026-10-10-training-priority')
TARGET = BASE / 'designated-ancestor-target-review.json'
# 対象化のレビュー結果。別名はRegistryへ登録せずこの調査範囲だけで扱う。
TARGETS = {
    'Caro': ('0000334731', 1967), 'Storm Cat': ('0000337102', 1983),
    'Bellamy Road': ('0001127392', 2002), 'Danzig': ('0000336082', 1977),
    'Roberto': ('0000335167', 1969), 'Nureyev': ('0000336085', 1977),
    'Lyphard': ('0000334968', 1969), 'Northern Dancer': ('0000334002', 1961),
    'Mr. Prospector': ('0000335975', 1970), 'Nasrullah': ('0000334374', 1940),
    'Nijinsky': ('0000333996', 1967), "Sadler's Wells": ('0000336572', 1981),
    'Galileo': ('0000714343', 1998), 'Kingmambo': ('0000347989', 1990),
    'サンデーサイレンス': ('0000333862', 1986), 'Bold Ruler': ('0000334140', 1954),
    'Never Bend': ('0000334001', 1960), 'Danehill': ('0000337424', 1986),
    'Generous': ('0000340528', 1988), 'Tony Bin': ('0000161740', 1983),
    'トニービン': ('0000161740', 1983), 'グレイソヴリン': ('0000333952', 1948),
    'Grey Sovereign': ('0000333952', 1948), 'リファール': ('0000334968', 1969),
    'ダンジグ': ('0000336082', 1977), 'ロベルト': ('0000335167', 1969),
    'ヌレイエフ': ('0000336085', 1977), 'ノーザンダンサー': ('0000334002', 1961),
}
ALLOWED_ROLES = {
    'ANCESTOR_INCLUSION', 'SIRE_LINEAGE_REFERENCE', 'DAM_SIRE_LINEAGE_REFERENCE',
    'DAM_SIRE_ID', 'DAM_SIRE_LINEAGE_SENSITIVITY_REFERENCE',
    'SIRE_OR_DAM_SIRE_LINEAGE_REFERENCE', 'LINEAGE_DESCENDANT_REFERENCE',
    'BROAD_LINEAGE_DEFINITION_PENDING',
}


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check(root=Path('.')):
    root = Path(root)
    registry = Registry(root / 'data/pedigree')
    manifest = read(root / TARGET)
    require(manifest['schema_version'] == 'designated-ancestor-target-review-v1', 'schema')
    cutoff = manifest['data_cutoff']
    require(cutoff == manifest['reviewed_at'] and dt(cutoff) <= dt(stamp()), 'review cutoff')
    require(manifest['mode'] == 'REPLAY' and manifest['usage'] == 'RESEARCH_SHADOW_ONLY'
            and manifest['production_eligible'] is False and manifest['webui_in_scope'] is False,
            'usage boundary')
    for field in ['registry_revisions_added', 'aliases_registered', 'new_external_country_searches',
                  'historic_claims_promoted']:
        require(manifest[field] == 0, 'scope-only boundary: ' + field)
    for name, filename in [('source_candidates', 'designated-ancestor-mentions-review.json'),
                           ('legacy_claims', 'legacy-535-claim-review.json')]:
        require(manifest[name + '_path'] == str(BASE / filename), 'fixed source path')
        require(sha(root / manifest[name + '_path']) == manifest[name + '_sha256'], 'source preserved')
    candidates = read(root / manifest['source_candidates_path'])['candidate_terms']
    legacy = read(root / manifest['legacy_claims_path'])['claims']
    claims = {c['claim_id']: c for c in legacy}
    require([c['term'] for c in candidates] == list(TARGETS), 'fixed 28-term scope')
    require(manifest['batches'] == [str(BASE / f'designated-ancestor-batches/batch-{i:02}.json')
                                  for i in range(1, 7)], 'six checkpoint paths')
    reviews = []
    for i, path in enumerate(manifest['batches']):
        batch = read(root / path)
        require(batch['schema_version'] == 'designated-ancestor-term-batch-v1'
                and batch['batch'] == i + 1 and batch['data_cutoff'] == cutoff
                and batch['source_head'] == manifest['source_head'] and batch['mode'] == 'REPLAY'
                and batch['production_eligible'] is False, 'batch boundary')
        require([r['term'] for r in batch['reviews']] == list(TARGETS)[i*5:i*5+5], 'batch coverage')
        reviews.extend(batch['reviews'])
    for i, (review, candidate) in enumerate(zip(reviews, candidates)):
        term = candidate['term']
        ident, year = TARGETS[term]
        key = 'jbis-' + ident
        require(review['term_index'] == i + 1 and review['horse_key'] == key
                and review['birth_year'] == year and review['external_ids']['JBIS'] == ident,
                'term identity mapping')
        identity = registry.identity_at(read(registry.path(key)), cutoff)
        require(identity and identity['status'] == 'RESOLVED'
                and identity['birth_year'] == year and identity['external_ids'] == review['external_ids']
                and identity['name'] == review['canonical_name']
                and identity['identity_evidence'] == review['identity_evidence'], 'resolved identity')
        require(review['mapping_method'] == 'EXPLICIT_ID_AND_VERIFIED_PARENT_PATH_REVIEW_NOT_NAME_ONLY_MERGE'
                and review['scope_status'] == 'TARGET_ID_AND_ROLE_REVIEWED'
                and review['historic_claims_promoted'] is False
                and review['definition_status'] == 'SCOPE_ONLY_COMPARATIVE_ADVANTAGE_AND_UNSPECIFIED_LINEAGE_DEFINITIONS_NOT_APPROVED',
                'scope is not claim promotion')
        require(review['roles'] and len(review['roles']) == len(set(review['roles']))
                and set(review['roles']) <= ALLOWED_ROLES, 'roles')
        require([r['claim_id'] for r in review['source_references']] == candidate['claim_ids'], 'claim coverage')
        for ref in review['source_references']:
            claim = claims[ref['claim_id']]
            require((ref['path'], ref['line']) == (claim['path'], claim['line'])
                    and ref['original_text_sha256'] == hashlib.sha256(claim['original_text'].encode()).hexdigest()
                    and ref['disposition'] == 'REFERENCE_PRESERVED_NOT_FACT_PROMOTED'
                    and claim['original_status'] == 'UNVERIFIED', 'original claim preserved')
        anchor = claims[review['source_anchor_claim_id']]
        require(anchor['claim_id'] in candidate['claim_ids']
                and anchor['original_text'] in (root / anchor['path']).read_text(encoding='utf-8'), 'source context anchor')
        expected_exclusions = [{'claim_id': c, 'reason': 'DIFFERENT_INDIVIDUAL_DANEHILL_DANCER_NOT_AN_EXACT_DANEHILL_MENTION'}
                               for c in candidate['claim_ids'] if term == 'Danehill' and 'Danehill Dancer' in claims[c]['original_text']]
        require(review['excluded_name_mentions'] == expected_exclusions, 'different-name exclusion')
        if term == 'Nasrullah':
            require(set(review['roles']) == {'LINEAGE_DESCENDANT_REFERENCE', 'BROAD_LINEAGE_DEFINITION_PENDING'},
                    'Nasrullah descendant scope')
        if term in ['リファール', 'ダンジグ', 'グレイソヴリン']:
            require(review['roles'] == ['DAM_SIRE_LINEAGE_REFERENCE'], 'dam sire lineage separate')
        if term == 'ヌレイエフ':
            require(review['roles'] == ['DAM_SIRE_LINEAGE_SENSITIVITY_REFERENCE'], 'sensitivity scope separate')

    dependency_path = BASE / 'designated-ancestor-batches/registry-dependencies.json'
    require(manifest['registry_dependencies_path'] == str(dependency_path), 'dependency path')
    dependencies = read(root / dependency_path)
    require(dependencies['schema_version'] == 'designated-ancestor-dependencies-v1'
            and dependencies['data_cutoff'] == cutoff
            and dependencies['source_head'] == manifest['source_head'], 'dependency snapshot')
    dep_keys = set()
    for dependency in dependencies['dependencies']:
        key = dependency['horse_key']
        require(key not in dep_keys, 'duplicate dependency')
        dep_keys.add(key)
        record = read(registry.path(key))
        require(digest(registry.identity_at(record, cutoff)) == dependency['identity_hash_at_cutoff'], 'identity cutoff')
        n = len(dependency['revision_prefix_hashes'])
        prefix = record['revisions'][:n]
        require([r['content_hash'] for r in prefix] == dependency['revision_prefix_hashes'], 'old revisions preserved')
        for revision in prefix:
            require(digest({k: v for k, v in revision.items() if k != 'content_hash'}) == revision['content_hash'],
                    'revision content hash')

    inventory = read(root / BASE / 'all-jra-sire-damsire-inventory.json')
    parents = {s['horse_key'] for s in inventory['subjects']}
    require(len(parents) == len(inventory['subjects']) == 613, 'parent inventory identity scope')
    subjects = manifest['subjects']
    keys = [s['horse_key'] for s in subjects]
    require(len(keys) == len(set(keys)) == 21 and set(keys) == {r['horse_key'] for r in reviews}, 'deduplicated targets')
    pending, existing, needed_deps = [], [], set(keys)
    for subject in subjects:
        key = subject['horse_key']
        identity = registry.identity_at(read(registry.path(key)), cutoff)
        require(digest(identity) == subject['identity_hash_at_cutoff']
                and (identity['name'], identity['birth_year']) == (subject['canonical_name'], subject['birth_year']), 'subject identity')
        require(subject['terms'] == [r['term'] for r in reviews if r['horse_key'] == key]
                and subject['in_sire_damsire_inventory'] == (key in parents), 'subject terms and parent reuse')
        proof = subject['representative_registry_path']
        start, path = proof['root_horse_key'], proof['path']
        require(path and set(path) <= {'S', 'D'} and len(path) == proof['generation'] <= 5
                and proof['example_scope'] == 'INDEPENDENT_VERIFIED_PATH_NOT_CONFIRMATION_OF_EVERY_LEGACY_CLAIM', 'path scope')
        require(registry.identity_at(read(registry.path(start)), cutoff)['name'] == proof['root_horse_name'], 'root identity')
        current = start
        needed_deps.add(start)
        require(len(proof['edges']) == len(path), 'path dependencies')
        for side, edge in zip(path, proof['edges']):
            fact = registry.edge(current, side, cutoff)
            require((edge['child'], edge['side']) == (current, side) and fact['status'] == 'VERIFIED'
                    and (fact['value'], fact['revision_id'], fact['content_hash']) == (edge['parent'], edge['revision_id'], edge['content_hash']), 'parent path fact')
            current = fact['value']
            needed_deps.add(current)
        resolved = registry.edge(start, path, cutoff)
        require(current == key and resolved['status'] == 'VERIFIED' and resolved['value'] == key, 'end-to-end path conflict check')
        kind = ('LINEAGE_FROM_REFERENCED_ANCESTOR' if key == 'jbis-0000334374' else
                'DAM_SIRE' if path == 'DS' else 'SIRE_LINEAGE' if key == 'jbis-0000335167' else 'ANCESTOR_INCLUSION')
        require(proof['relationship_kind'] == kind, 'path relationship kind')
        if key == 'jbis-0000334374':
            require(start == 'jbis-0000334731' and path == 'SSS', 'Nasrullah is from Caro, not a runner five-generation claim')
        country = subject['training_country']
        require(subject['country_applies_only_to_this_horse'] is True and subject['production_eligible'] is False
                and country['horse_key'] == key and country['new_search_performed'] is False, 'individual country boundary')
        fact = registry.fact(key, 'attribute:training_country_matches', cutoff)
        if fact['status'] == 'VERIFIED':
            require(fact['value']['search_completed'] and len({m['country'] for m in fact['value']['matches']}) == 1, 'reusable single country')
            require(country == {'state': 'EXISTING_SINGLE_COUNTRY_REUSED', 'country': fact['value']['matches'][0]['country'],
                    'horse_key': key, 'revision_id': fact['revision_id'], 'content_hash': fact['content_hash'],
                    'first_observed_at': fact['first_observed_at'], 'new_search_performed': False}, 'existing country provenance')
            existing.append(key)
        else:
            require(country == {'state': 'COUNTRY_RESEARCH_REQUIRED', 'country': None, 'horse_key': key,
                    'registry_matches_status': fact['status'], 'new_search_performed': False, 'user_input_required': False},
                    'unsearched is not zero matches or user request')
            pending.append(key)
    require(dep_keys == needed_deps, 'exact dependency scope')
    queues = {'reuse_existing_single_country': existing, 'reuse_sire_damsire_queue': [k for k in pending if k in parents],
              'additional_ancestor_queue': [k for k in pending if k not in parents]}
    require(manifest['country_research_queues'] == queues, 'deduplicated queues')
    overlap = len(set(keys) & parents)
    counts = {'reviewed_terms': len(reviews), 'canonical_individuals': len(keys), 'sire_damsire_overlap': overlap,
              'additional_individuals': len(keys) - overlap, 'combined_scope_individuals': len(set(keys) | parents),
              'existing_single_country_reused': len(existing), 'country_research_required': len(pending),
              'pending_in_sire_damsire_queue': len(queues['reuse_sire_damsire_queue']),
              'pending_additional_ancestor_queue': len(queues['additional_ancestor_queue'])}
    require(manifest['scope_counts'] == counts, 'computed scope counts')
    return dict(integrity='PASS', **counts, registry_revisions_added=0, historic_claims_promoted=0, production_eligible=False)


if __name__ == '__main__':
    print(json.dumps(check(), ensure_ascii=False, indent=2))
