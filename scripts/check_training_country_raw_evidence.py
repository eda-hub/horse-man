#!/usr/bin/env python3
"""保存済み5頭の原HTML追加証跡を検査する。ネットワーク取得・Registry更新は行わない。"""
import hashlib
import html
import json
import re
from datetime import datetime
from pathlib import Path


BASE = Path('data/pedigree/reconciliations/2026-10-10-training-priority')
SUBJECTS = {'jbis-0000742976', 'jbis-0000722158', 'jbis-0000729458',
            'jbis-0001089850', 'jbis-0001120570'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def time(value):
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    require(result.tzinfo is not None, 'timezone missing')
    return result


def check(root=Path('.')):
    root = Path(root)
    review = read(root / BASE / 'training-country-source-review.json')
    subjects = [h for h in review['horses'] if h['horse_key'] in SUBJECTS]
    require(len(subjects) == len(SUBJECTS) == len({h['horse_key'] for h in subjects}), 'subject scope')
    for horse in subjects:
        key = horse['horse_key']
        link = horse['raw_html_evidence']
        expected = BASE / 'r01-raw' / key
        require(link['metadata_path'] == str(expected.with_suffix('.capture.json')), 'metadata path')
        meta = read(root / link['metadata_path'])
        require(meta['schema_version'] == 'training-country-raw-evidence-v1', 'schema')
        require(meta['horse_key'] == key and meta['horse_name'] == horse['horse_name'], 'identity')
        require(meta['path'] == link['path'] == str(expected.with_suffix('.html')), 'body path')
        body = (root / meta['path']).read_bytes()
        require(len(body) == meta['byte_length'], 'body length')
        require(hashlib.sha256(body).hexdigest() == meta['sha256'] == link['sha256'], 'body hash')
        require(meta['hash_kind'] == 'http-response-body-bytes-sha256', 'hash kind')
        require(meta['http_status'] == 200 and meta['content_encoding'] in (None, 'identity'), 'HTTP response')
        require('text/html' in meta['content_type'].lower(), 'content type')
        require(meta['mode'] == 'REPLAY' and meta['production_eligible'] is False, 'usage boundary')
        require(meta['historical_capture_reconstructed'] is False and link['supplemental'] is True, 'capture boundary')
        reference = meta['registry_reference']
        original = horse['registry_verification']
        require(reference['path'] == original['record_path'] and reference['blob_sha'] == original['record_blob_sha'], 'record reference')
        record = read(root / reference['path'])
        revisions = [r for r in record['revisions'] if r['revision_id'] == reference['revision_id']]
        require(len(revisions) == 1 and reference['revision_id'] == original['revision_id'], 'revision reference')
        revision = revisions[0]
        require(revision['field'] == 'attribute:training_country_matches' and revision['status'] == 'VERIFIED', 'fact')
        require(revision['content_hash'] == reference['revision_content_hash'], 'revision hash')
        require(revision['source']['record_hash'] == reference['original_source_record_hash'] == original['source_record_hash'], 'original hash')
        require(revision['source']['record_hash_kind'] == 'canonical-extracted-fields-sha256', 'original hash kind')
        require(revision['captured_at'] == reference['original_captured_at'], 'original capture time')
        require(time(revision['captured_at']) < time(meta['request_started_at']) <= time(meta['captured_at']), 'capture ordering')
        require(link['captured_at'] == meta['captured_at'], 'capture link')
        url = 'https://www.jbis.or.jp/horse/' + key.removeprefix('jbis-') + '/'
        require(meta['requested_url'] == meta['final_url'] == revision['source']['url'] == url, 'source URL')
        source = body.decode('utf-8')
        title = re.search(r'<title>(.*?)</title>', source, re.S)
        require(title is not None and horse['horse_name'] in html.unescape(title.group(1)), 'horse title')
        trainer_block = re.search(r'<dt>調教師</dt>\s*<dd>(.*?)</dd>', source, re.S)
        require(trainer_block is not None, 'trainer field')
        trainer = html.unescape(re.search(r'<a[^>]*>(.*?)</a>', trainer_block.group(1), re.S).group(1)).strip()
        location = re.search(r'\(([^)]+)\)', trainer_block.group(1)).group(1).replace(' ', '')
        birth = re.search(r'<dt>生年月日</dt>\s*<dd>(.*?)</dd>', source, re.S).group(1)
        fields = meta['verified_fields']
        require(fields == dict(horse_name=horse['horse_name'], birth_date=birth, trainer=trainer,
                               trainer_location=location, training_country='JP'), 'extracted fields')
        require(int(birth[:4]) == record['identity']['birth_year'], 'birth year')
        require(trainer == revision['source']['extracted_fields']['trainer'], 'trainer mismatch')
        require(location == revision['source']['extracted_fields']['trainer_location'] == '栗東', 'affiliation mismatch')
        require(horse['selected_country'] == 'JP' and {m['country'] for m in revision['value']['matches']} == {'JP'}, 'country mismatch')
    require(review['registry_raw_html_captured_count'] == sum('raw_html_evidence' in h for h in review['horses']), 'capture count')
    return {'integrity': 'PASS', 'scope': 'R01 supplemental raw HTML', 'verified_horses': len(subjects),
            'registry_revisions_modified': False, 'production_eligible': False}


if __name__ == '__main__':
    print(json.dumps(check(), ensure_ascii=False, indent=2))
