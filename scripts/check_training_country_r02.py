#!/usr/bin/env python3
"""R02の5頭の原文、既存revision、冪等Writer検証と登録棚卸しを監査する。"""
import hashlib
import html
import json
import re
from pathlib import Path
from pedigree_registry import Registry, digest, dt


BASE = Path('data/pedigree/reconciliations/2026-10-10-training-priority')
KEYS = {'jbis-0000725485', 'jbis-0001124297', 'jbis-0001042049',
        'jbis-0001115148', 'jbis-0001215724'}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def capture(root, path, key, role):
    expected = BASE / 'r02-raw' / (key + '-' + role + '.capture.json')
    require(path == str(expected), 'capture metadata path')
    meta = read(root / path)
    expected_body = BASE / 'r02-raw' / (key + '-' + role + '.html')
    require(meta['path'] == str(expected_body), 'body path')
    body = (root / meta['path']).read_bytes()
    require(meta['horse_key'] == key and meta['role'] == role, 'capture subject')
    require(hashlib.sha256(body).hexdigest() == meta['sha256'] and len(body) == meta['byte_length'], 'raw body hash/length')
    require(meta['http_status'] == 200 and meta['content_encoding'] in (None, 'identity'), 'HTTP response')
    require('text/html' in meta['content_type'].lower(), 'HTML content type')
    require(meta['hash_kind'] == 'http-response-body-bytes-sha256', 'hash kind')
    require(dt(meta['request_started_at']) <= dt(meta['captured_at']), 'capture order')
    return meta, body.decode('utf-8')


def check(root=Path('.')):
    root = Path(root)
    registry = Registry(root / 'data/pedigree')
    batch = read(root / BASE / 'r02-verification.json')
    require(batch['schema_version'] == 'training-country-r02-verification-v1', 'batch schema')
    require(batch['mode'] == 'REPLAY' and batch['production_eligible'] is False, 'usage boundary')
    require(batch['count'] == 5 and {r['horse_key'] for r in batch['subjects']} == KEYS, 'batch scope')
    require(len(batch['subjects']) == 5 and batch['added_registry_revisions'] == 0 and batch['registry_revisions_modified'] is False, 'no duplicate registration')
    review = read(root / BASE / 'training-country-source-review.json')
    reviewed = {h['horse_key']: h for h in review['horses']}
    for subject in batch['subjects']:
        key = subject['horse_key']
        record_path = 'data/pedigree/horses/' + key + '.json'
        require(subject['record_path'] == record_path, 'registry path')
        record = read(root / record_path)
        revisions = [r for r in record['revisions'] if r['revision_id'] == subject['registry_revision_id']]
        require(len(revisions) == 1, 'registry revision')
        fact = revisions[0]
        registry.validate_fact(fact)
        require(fact['field'] == 'attribute:training_country_matches' and fact['status'] == 'VERIFIED', 'verified training fact')
        require(digest({k: v for k, v in fact.items() if k != 'content_hash'}) == fact['content_hash'] == subject['registry_revision_content_hash'], 'revision hash')
        require(fact['captured_at'] == subject['original_captured_at'] and fact['source']['record_hash'] == subject['source_record_hash'], 'original provenance')
        require({m['country'] for m in fact['value']['matches']} == {subject['country']}, 'country')
        proof = subject['raw_capture_metadata_paths']
        require(len(proof) == (2 if subject['country'] == 'GB' else 1), 'proof scope')
        profile, source = capture(root, proof[0], key, 'profile')
        url = 'https://www.jbis.or.jp/horse/' + key[5:] + '/'
        require(profile['requested_url'] == profile['final_url'] == url, 'profile identity URL')
        title = re.search(r'<title>(.*?)</title>', source, re.S).group(1)
        require(subject['horse_name'] in html.unescape(title), 'profile horse name')
        birth = re.search(r'<dt>生年月日</dt>\s*<dd>(.*?)</dd>', source, re.S).group(1)
        require(int(birth[:4]) == record['identity']['birth_year'] and birth == subject['verified_fields']['birth_date'], 'birth identity')
        primary = profile
        if subject['country'] == 'JP':
            require(profile['requested_url'] == fact['source']['url'], 'Japanese training source URL')
            block = re.search(r'<dt>調教師</dt>\s*<dd>(.*?)</dd>', source, re.S).group(1)
            trainer = html.unescape(re.search(r'<a[^>]*>(.*?)</a>', block, re.S).group(1)).strip()
            location = re.search(r'\(([^)]+)\)', block).group(1).replace(' ', '')
            require(location in {'美浦', '栗東'}, 'Japanese trainer affiliation')
            require(trainer == fact['source']['extracted_fields']['trainer'] == subject['verified_fields']['trainer'], 'trainer')
            require(location == fact['source']['extracted_fields']['trainer_location'] == subject['verified_fields']['trainer_location'], 'affiliation')
        else:
            require(subject['country'] == 'GB', 'supported scope country')
            primary, article = capture(root, proof[1], key, 'training')
            require(primary['requested_url'] == primary['final_url'] == fact['source']['url'], 'training source URL')
            text = re.sub(r'\s+', ' ', html.unescape(re.sub('<[^>]*>', ' ', article)))
            for marker in ['Harbinger', 'Michael Stoute', 'who trains both horses',
                           'Warren Hill Newmarket gallops', 'Hardwicke Stakes', 'Royal Ascot']:
                require(marker in text, 'British training source missing ' + marker)
            require('ハードウィックS' in source and '2010' in source and '2010/jul/06' in primary['requested_url'], 'cross-source horse identity')
            require(subject['verified_fields']['trainer'] == fact['source']['extracted_fields']['trainer'] == 'Sir Michael Stoute', 'British trainer')
            require(subject['verified_fields']['trainer_location'] == 'Newmarket', 'British training location')
            require(subject['verified_fields']['original_stable_detail_not_reconfirmed'] == 'Freemason Lodge', 'unconfirmed detail retained')
        for path in proof:
            meta = read(root / path)
            require(dt(fact['captured_at']) < dt(meta['request_started_at']) <= dt(meta['captured_at']) <= dt(batch['verified_at']), 'no backdating')
        link = reviewed[key]['raw_html_evidence']
        require(link['metadata_path'] == proof[-1], 'primary capture metadata reference')
        require(link['all_metadata_paths'] == proof and link['path'] == primary['path'] and link['sha256'] == primary['sha256'], 'review proof reference')
        require(subject['writer_result']['added_revisions'] == [] and subject['registry_revisions_modified'] is False, 'writer idempotence result')
        require(registry.fact(key, 'attribute:training_country_matches', '2026-10-01T00:00:00+00:00')['status'] != 'VERIFIED', 'historical cutoff')
    inventory = read(root / BASE / 'r02-registration-inventory.json')
    require(inventory['base_commit'] == batch['base_commit'], 'inventory base commit')
    require(inventory['count'] == len(inventory['subjects']) == 30, 'inventory count')
    require(len({s['horse_key'] for s in inventory['subjects']}) == 30, 'inventory uniqueness')
    verified = 0
    for entry in inventory['subjects']:
        require(entry['record_path'] == 'data/pedigree/horses/' + entry['horse_key'] + '.json', 'inventory record path')
        record = read(root / entry['record_path'])
        for ref in entry['training_revisions']:
            actual = [r for r in record['revisions'] if r['revision_id'] == ref['revision_id']]
            require(len(actual) == 1 and actual[0]['content_hash'] == ref['content_hash'], 'inventory revision')
            registry.validate_fact(actual[0])
            require(digest({k: v for k, v in actual[0].items() if k != 'content_hash'}) == ref['content_hash'], 'inventory hash')
            require(actual[0]['status'] == ref['status'] and {m['country'] for m in actual[0]['value']['matches']} == set(ref['countries']), 'inventory fact')
        verified += any(r['status'] == 'VERIFIED' for r in entry['training_revisions'])
    require(verified == inventory['registry_verified_subjects'] == 25 and 30 - verified == inventory['no_training_match_fact_subjects'] == 5, 'historical registration count')
    return {'integrity': 'PASS', 'verified_horses': 5, 'writer_added_revisions': 0,
            'registration_inventory_subjects': 30, 'historical_registered_subjects': 25,
            'production_eligible': False}


if __name__ == '__main__':
    print(json.dumps(check(), ensure_ascii=False, indent=2))
