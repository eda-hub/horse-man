#!/usr/bin/env python3
"""父・母父613頭の開始時点と、利用頻度順の調査チェックポイントを監査。"""
import argparse
import copy
import hashlib
import json
import subprocess
from pathlib import Path

from pedigree_registry import Registry, digest, dt, stamp

BASE = Path('data/pedigree/reconciliations/2026-10-10-training-priority')
CHECKPOINT = BASE / 's5-inventory-checkpoint.json'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def git_blob(data):
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()


def check(root=Path('.'), repo=None):
    root = Path(root)
    manifest = read(root / CHECKPOINT)
    require(manifest['schema_version'] == 'training-country-inventory-checkpoint-v1', 'schema')
    cutoff = manifest['data_cutoff']
    require(cutoff == manifest['reviewed_at'] and dt(cutoff) <= dt(stamp()), 'cutoff')
    require(manifest['mode'] == 'REPLAY' and manifest['production_eligible'] is False
            and manifest['external_country_queries'] == manifest['registry_revisions_added'] == 0,
            'baseline is a registry-only checkpoint')
    inventory = read(root / manifest['source_inventory_path'])
    rows = {r['horse_key']: r for r in inventory['subjects']}
    subjects = manifest['subjects']
    require(len(rows) == len(inventory['subjects']) == len(subjects) == 613
            and {s['horse_key'] for s in subjects} == set(rows), '613 unique subjects')
    require(manifest['sort_order'] == 'USE_REFERENCES_DESC_HORSE_KEY_ASC', 'priority order')
    registry = Registry(root / 'data/pedigree')
    registered, pending, corrections = [], [], []
    for subject in subjects:
        key = subject['horse_key']
        record = read(registry.path(key))
        identity = registry.identity_at(record, cutoff)
        require(identity and identity['status'] == 'RESOLVED'
                and digest(identity) == subject['identity_hash_at_cutoff']
                and identity['name'] == subject['horse_name']
                and identity['birth_year'] == subject['birth_year'], 'identity at cutoff')
        n = len(subject['before_revision_hashes'])
        prefix = record['revisions'][:n]
        require([r['content_hash'] for r in prefix] == subject['before_revision_hashes'], 'old revisions')
        for revision in record['revisions']:
            require(digest({k: v for k, v in revision.items() if k != 'content_hash'})
                    == revision['content_hash'], 'revision content hash')
        before = copy.deepcopy(record)
        before['revisions'] = prefix
        require(digest(before) == subject['before_record_hash'], 'old record preserved')
        row = rows[key]
        require((row['sire_uses'], row['damsire_uses'])
                == (subject['sire_uses'], subject['damsire_uses'])
                and subject['use_references'] == subject['sire_uses'] + subject['damsire_uses'], 'usage scope')
        fact = registry.fact(key, 'attribute:training_country_matches', cutoff)
        require(fact['status'] == subject['registry_matches_status']
                and subject['country_search_performed_in_checkpoint'] is False, 'baseline fact status')
        if fact['status'] == 'VERIFIED':
            countries = {m['country'] for m in fact['value']['matches']}
            require(fact['value']['search_completed'] is True and len(countries) == 1
                    and subject['country'] in countries
                    and subject['revision_id'] == fact['revision_id']
                    and subject['revision_content_hash'] == fact['content_hash']
                    and subject['source'] == fact['source'], 'existing single country')
            expected = 'VERIFIED_TRAINING_COUNTRY_REGISTRY'
            registered.append(key)
        else:
            require(fact['status'] == 'NOT_FOUND' and subject['country'] is None
                    and subject['revision_id'] is None and subject['source'] is None, 'unsearched is not zero matches')
            expected = 'NOT_YET_SEARCHED_FOR_TRAINING_COUNTRY'
            pending.append(subject)
        require(subject['reconciled_status'] == expected, 'reconciled status')
        if subject['before_inventory_status'] != expected:
            corrections.append(key)
    require(len(registered) == 92 and len(pending) == 521 and len(corrections) == 5, 'baseline counts')
    require(manifest['scope_counts'] == dict(sire_damsire_subjects=613,
            registered_single_country=92, unsearched=521, source_only_stale_statuses_corrected=5,
            unresolved_identity=0, conflicts=0, multiple_countries=0, zero_match_searches=0), 'scope counts')
    require(manifest['status_corrections'] == corrections, 'five stale statuses')
    queue = sorted(pending, key=lambda s: (-s['use_references'], s['horse_key']))
    expected_queue = [dict(priority=i + 1, **{k: s[k] for k in
                      ('horse_key', 'horse_name', 'sire_uses', 'damsire_uses', 'use_references')})
                      for i, s in enumerate(queue)]
    require(manifest['unsearched_priority_queue'] == expected_queue, 'complete priority queue')
    if repo is not None:
        prefix = ['git', '-C', str(repo)]
        original = subprocess.check_output(prefix + ['show', manifest['source_commit'] + ':'
                                                      + manifest['source_inventory_path']])
        require(hashlib.sha256(original).hexdigest() == manifest['source_inventory_sha256'], 'original inventory bytes')
        old = json.loads(original)
        require(old['scope_count'] == manifest['source_scope_count'], 'original counts preserved')
        old_rows = {r['horse_key']: r for r in old['subjects']}
        require(set(old_rows) == set(rows), 'original scope')
        tree = subprocess.check_output(prefix + ['ls-tree', '-r', manifest['source_commit'],
                                                'data/pedigree/horses']).decode()
        blobs = {line.split('\t')[1]: line.split()[2] for line in tree.splitlines()}
        for subject in subjects:
            require(blobs['data/pedigree/horses/' + subject['horse_key'] + '.json']
                    == subject['before_git_blob_sha'], 'original record blob')
            require(old_rows[subject['horse_key']]['status'] == subject['before_inventory_status'], 'original status')
    return dict(subjects=613, registered_at_start=92, unsearched_at_start=521,
                stale_statuses_corrected=5)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', type=Path)
    args = parser.parse_args()
    print(json.dumps(check(repo=args.repo), ensure_ascii=False, sort_keys=True))
