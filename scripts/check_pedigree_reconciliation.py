#!/usr/bin/env python3
"""Read-only check of the source-backed PR69 reconciliation, without network."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

from pedigree_registry import Registry, digest, read, dt


def check(repo, date='2026-10-09'):
    repo = Path(repo)
    directory = repo / 'data/pedigree/reconciliations' / date
    evidence = read(directory / 'matches.json')
    assert evidence['mode'] == 'REPLAY' and evidence['production_eligible'] is False
    legacy_path = repo / 'data/pedigree/migration.json'
    assert hashlib.sha256(legacy_path.read_bytes()).hexdigest() == evidence['legacy_manifest_sha256']
    legacy = read(legacy_path)
    claims = {c['claim_id']: c for c in legacy['claims']}
    candidates = {(c['claim_id'], a['field']): a for c in legacy['claims']
                  for a in c['components'] if a['kind'] == 'OBJECTIVE_FACT_CANDIDATE'}
    profiles = read(directory / 'jra_profiles.json')['records']
    by_id = {p['external_id']: p for p in profiles}
    assert len(by_id) == len(profiles) == 53
    aliases = {('アルデバランⅡ', 'アルデバラン2'),
               ('Highland Reel', 'ハイランドリール'), ('ミッキーアイル', 'Mikki Isle')}
    seen = set()
    for row in evidence['matches']:
        pair = row['claim_id'], row['component_field']
        assert pair not in seen
        seen.add(pair)
        candidate, claim = candidates[pair], claims[row['claim_id']]
        assert candidate['horse_name'] == row['horse_name']
        assert candidate['ancestor_name'] == row['expected']
        assert (row['legacy_path'], row['legacy_line']) == (claim['path'], claim['line'])
        profile = by_id[row['horse_external_id']]
        assert profile['horse_name'] == row['horse_name']
        assert row['actual'] == profile['fields']['父' if row['component_field'] == 'parent:S' else '母の父']
        assert row['source_url'] == profile['source']['url']
        assert row['source_record_hash'] == digest(profile['fields']) == profile['source']['record_hash']
        assert re.fullmatch(r'20\d{8}', row['horse_external_id'])
        status = 'EXACT_MATCH' if row['expected'] == row['actual'] else 'ALIAS_MATCH'
        assert status == row['status']
        if status == 'ALIAS_MATCH':
            assert (row['expected'], row['actual']) in aliases
    assert seen == set(candidates)
    assert dict(Counter(r['status'] for r in evidence['matches'])) == evidence['counts']
    registry = Registry(repo / 'data/pedigree')
    # Freeze the read-only audit under the sole Writer's lock. Avoid rereading
    # every identity file for each identity's duplicate-ID check.
    with registry.writer():
        records = registry.records()
        class ReadSnapshot(Registry):
            def records(self):
                return records
        audit = ReadSnapshot(registry.root).audit()
        assert audit['status'] == 'PASS', audit
        indexed = {r['horse_key']: r for r in records}
        summary = read(directory / 'import_summary.json')
        cutoff = summary['verification_cutoff']
        dt(cutoff)
        sheets = read(directory / 'jbis_pedigrees.json')['records']
        scoped_ids = {r['horse']['id'] for r in sheets}
        scoped_ids.update(a['id'] for r in sheets for a in r['ancestors'].values())
        assert len(sheets) == 52
        expected_paths = {format(i, '0%db' % depth).translate(str.maketrans('01', 'SD'))
                          for depth in range(1, 6) for i in range(2 ** depth)}
        edges = {}
        for sheet in sheets:
            assert set(sheet['ancestors']) == expected_paths
            assert sheet['source']['source_class'] == 'BREEDING_DB'
            assert re.fullmatch(r'[0-9a-f]{64}', sheet['source']['record_hash'])
            root_key = 'jbis-' + sheet['horse']['id']
            assert registry.identity_at(indexed[root_key], cutoff)['external_ids']['JBIS'] == sheet['horse']['id']
            for path, ancestor in sheet['ancestors'].items():
                parent_key = root_key if len(path) == 1 else 'jbis-' + sheet['ancestors'][path[:-1]]['id']
                ancestor_key = 'jbis-' + ancestor['id']
                assert registry.identity_at(indexed[ancestor_key], cutoff)['name'] == ancestor['name']
                fact = registry.fact(parent_key, 'parent:' + path[-1], cutoff)
                assert fact['status'] == 'VERIFIED' and fact['value'] == ancestor_key
                pair = parent_key, path[-1]
                assert pair not in edges or edges[pair] == ancestor_key
                edges[pair] = ancestor_key
            # A source acquired today cannot be reused at a previous prediction cutoff.
            assert registry.fact(root_key, 'parent:S', '2026-10-04T23:59:59+09:00')['status'] != 'VERIFIED'
        assert summary['independent_parent_edge_count'] == len(edges) == 1774
        assert summary['ancestor_positions'] == 3224
        assert summary['identity_count'] == len(scoped_ids) == 1430
    return {'status': 'PASS', 'official_horses': len(profiles), 'objective_components': len(seen),
            'matches': evidence['counts'], 'jbis_sheets': len(sheets),
            'ancestor_positions': 3224, 'independent_parent_edges': len(edges),
            'registry_audit': audit, 'production_eligible': False,
            'legacy_candidates_automatically_promoted': 0}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', default='.')
    parser.add_argument('--date', default='2026-10-09')
    args = parser.parse_args()
    print(json.dumps(check(args.repo, args.date), ensure_ascii=False, indent=2))
