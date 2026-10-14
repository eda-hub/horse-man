"""R06で不足する明示個体2頭の本人・父のみをJBIS原HTMLから唯一Writerへ保存。"""
import argparse
import base64
import gzip
import hashlib
import html
import json
import re
from pathlib import Path

from pedigree_batch import BatchRegistry
from pedigree_registry import SCHEMA, digest, read, stamp

BASE = Path('data/pedigree/reconciliations/2026-10-10-training-priority/legacy-fact-followup/batch-02')
TARGETS = {'0001332370': ('オールナット', 2021, '0001175221'), '0001322201': ('シランケド', 2020, '0001181460')}

def parse_profile(raw, subject_id):
    text = raw.decode('utf-8')
    title = re.search(r'<title>(.*?)</title>', text, re.S)
    birth = re.search(r'<dt>生年月日</dt>\s*<dd>(\d{4})\.\d{2}\.\d{2}', text)
    father = re.search(r'<div class="data-3__male-hdg pc-only">父</div>\s*<div class="data-3__male">\s*<div>\s*<a href="/horse/(\d{10})/"[^>]*>(.*?)</a>', text, re.S)
    if not (title and birth and father and '/horse/' + subject_id + '/' in text):
        raise ValueError('本人・生年月日・父役割の原HTML形式不足')
    return {'name': html.unescape(title[1]).split('｜')[0], 'birth_year': int(birth[1]), 'father_id': father[1], 'father_name': html.unescape(father[2])}

def check(root=Path('.')):
    root = Path(root)
    manifest = read(root / BASE / 'subject-import.json')
    bundle = json.loads(gzip.decompress((root / BASE / 'identity-sources.json.gz').read_bytes()))
    registry = BatchRegistry(root / 'data/pedigree')
    for row in manifest['subjects']:
        sid = row['provider_id']
        source = bundle[sid]
        raw = base64.b64decode(source['body_base64'], validate=True)
        assert source['status'] == 200 and source['url'] == source['final_url'] == 'https://www.jbis.or.jp/horse/' + sid + '/'
        assert hashlib.sha256(raw).hexdigest() == source['sha256']
        profile = parse_profile(raw, sid)
        assert (profile['name'], profile['birth_year'], profile['father_id']) == TARGETS[sid]
        assert profile == row['profile']
        record = read(registry.path(row['horse_key']))
        identity = registry.identity_at(record, manifest['data_cutoff'])
        assert identity and identity['status'] == 'RESOLVED' and identity['name'] == profile['name'] and identity['birth_year'] == profile['birth_year'] and identity['external_ids']['JBIS'] == sid
        parent = read(registry.path(row['father_key']))
        assert parent['identity']['external_ids']['JBIS'] == profile['father_id']
        assert parent['identity']['name'] == profile['father_name']
        fact = registry.edge(row['horse_key'], 'S', manifest['data_cutoff'])
        assert fact['status'] == 'VERIFIED' and fact['value'] == row['father_key']
        revisions = [r for r in record['revisions'] if r['revision_id'] in row['added_revision_ids']]
        assert len(revisions) == 1 and revisions[0]['source']['record_hash'] == source['sha256'] and revisions[0]['source']['record_key'] == sid + ':S'
        assert registry.identity_at(record, manifest['baseline_cutoff']) is None
        assert digest(record) == row['after_record_hash']
    return {'subjects': len(manifest['subjects']), 'parent_revisions': 2, 'mother_and_full_pedigree_promoted': False}

def save(root=Path('.')):
    root = Path(root)
    path = root / BASE / 'subject-import.json'
    if path.exists():
        return check(root)
    bundle = json.loads(gzip.decompress((root / BASE / 'identity-sources.json.gz').read_bytes()))
    registry = BatchRegistry(root / 'data/pedigree')
    rows = []
    baseline = stamp()
    with registry.batch():
        records = list(registry.records())
        for sid, expected in TARGETS.items():
            source = bundle[sid]
            raw = base64.b64decode(source['body_base64'], validate=True)
            assert hashlib.sha256(raw).hexdigest() == source['sha256'] and source['status'] == 200
            profile = parse_profile(raw, sid)
            assert (profile['name'], profile['birth_year'], profile['father_id']) == expected
            parents = [r for r in records if r['identity'].get('external_ids', {}).get('JBIS') == profile['father_id']]
            assert len(parents) == 1 and parents[0]['identity']['name'] == profile['father_name']
            key = 'jbis-' + sid
            assert read(registry.path(key)) is None
            identity = {'name': profile['name'], 'aliases': [], 'birth_year': profile['birth_year'], 'external_ids': {'JBIS': sid}, 'status': 'RESOLVED', 'identity_evidence': {'source': 'JBIS', 'record_key': sid, 'record_hash': source['sha256']}}
            candidate = {'schema_version': SCHEMA, 'horse_key': key, 'identity': identity, 'facts': [{'field': 'parent:S', 'value': parents[0]['horse_key'], 'status': 'VERIFIED', 'first_observed_at': source['captured_at'], 'captured_at': source['captured_at'], 'source': {'source_class': 'BREEDING_DB', 'origin_group': 'JBIS', 'acquisition_method': 'original-profile-explicit-father-id-and-existing-independent-id', 'record_hash': source['sha256'], 'record_hash_kind': 'response-body-sha256', 'url': source['final_url'], 'record_key': sid + ':S'}, 'verification': {'identity_checked': True, 'source_checked': True, 'relationship_checked': True, 'reviewed_by': '本人ID・名前・生年・父欄独立IDと既存父レコードを照合'}}]}
            result = registry.save(candidate)
            after = read(registry.path(key))
            assert registry.save(candidate, expected_hash=digest(after))['added_revisions'] == []
            rows.append({'provider_id': sid, 'horse_key': key, 'father_key': parents[0]['horse_key'], 'profile': profile, 'before_record_hash': None, 'after_record_hash': digest(after), 'added_revision_ids': result['added_revisions'], 'repeat_added_revisions': 0})
    manifest = {'schema_version': 'legacy-explicit-subject-import-v1', 'baseline_cutoff': baseline, 'data_cutoff': stamp(), 'mode': 'REPLAY', 'production_eligible': False, 'subjects': rows, 'scope': '本人と父のみ新規保存。5代父直系は既存独立祖先を再利用。母・5代全体・当時の確認・適性は未昇格。'}
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    return check(root)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--save', action='store_true')
    args = parser.parse_args()
    print(json.dumps(save() if args.save else check(), ensure_ascii=False))
