#!/usr/bin/env python3
"""父・母父613頭の開始時点と、利用頻度順の調査チェックポイントを監査。"""
import argparse
import copy
import hashlib
import json
import subprocess
import re
from html.parser import HTMLParser
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


class HTMLRows(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows, self.text = [], []
        self.cells = self.cell = None

    def handle_starttag(self, tag, attrs):
        if tag == 'tr':
            self.cells = []
        if tag in ('td', 'th') and self.cells is not None:
            self.cell = []

    def handle_data(self, value):
        self.text.append(value)
        if self.cell is not None:
            self.cell.append(value)

    def handle_endtag(self, tag):
        if tag in ('td', 'th') and self.cell is not None:
            self.cells.append(re.sub(r'\s+', ' ', ' '.join(self.cell)).strip())
            self.cell = None
        if tag == 'tr' and self.cells is not None:
            self.rows.append(self.cells)
            self.cells = None


def raw_proof(root, proof, key, cutoff):
    meta = read(root / proof['capture_path'])
    data = (root / proof['raw_path']).read_bytes()
    require(meta['path'] == proof['raw_path'] and key in meta['horse_keys']
            and meta['sha256'] == proof['sha256'] == hashlib.sha256(data).hexdigest()
            and meta['byte_length'] == len(data) and meta['hash_kind'] == proof['hash_kind']
            and meta['final_url'] == proof['url']
            and meta['captured_at'] == proof['captured_at']
            and dt(meta['request_started_at']) <= dt(meta['captured_at']) <= dt(cutoff), 'capture integrity')
    kind = proof['proof_kind']
    if kind == 'TDN_FRENCH_TRAINING_BASE_FIELDS':
        fields = json.loads(data)
        require(meta['http_status'] is None and meta['direct_http_status'] == 403
                and meta['original_pdf_bytes_captured'] is False
                and meta['hash_kind'] == 'reviewed-extracted-fields-file-bytes-sha256-not-original-pdf'
                and fields['original_pdf_bytes_captured'] is False
                and fields['horse_key'] == key == 'jbis-0000362799'
                and fields['english_name'] == 'French Deputy' and fields['birth_year'] == 1992
                and fields['sire'] == 'Deputy Minister' and fields['trainer'] == 'Neil Drysdale'
                and fields['training_base'] == 'Hollywood Park, California, USA'
                and fields['source_url'] == proof['url']
                and fields['source_page'] == 2 and fields['source_lines'] == '103-109'
                and fields['affiliation_reported_on'] == proof['last_trained_on'] == '1995-04-05'
                and fields['country'] == proof['country'] == 'US', 'reviewed fields are not raw PDF bytes')
        return
    require(meta['http_status'] == 200
            and meta['hash_kind'] == 'http-response-body-bytes-sha256', 'successful original body')
    if kind == 'GULFSTREAM_SHANGHAI_TRAINING_BASE':
        require(key == 'jbis-0001162862' and proof['country'] == 'US' and data.startswith(b'%PDF'), 'Shanghai source')
        text = subprocess.check_output(['pdftotext', '-f', '15', '-l', '15', '-layout',
                                       str(root / proof['raw_path']), '-'], stderr=subprocess.DEVNULL).decode()
        require(all(t in text for t in ('Palm Meadows', 'training', 'Palm Beach County',
                'Other noteworthy residents', 'Shanghai', 'Bobby (2012)', 'Boynton Beach')),
                'horse residency at training facility, not a race result')
        require(proof['last_trained_on'] is None, 'year of championship is not a training date')
        return
    parser = HTMLRows()
    parser.feed(data.decode('cp932' if kind == 'JRA_VICTOIRE_RITTO' else 'utf-8', errors='replace'))
    text = re.sub(r'\s+', '', ''.join(parser.text))
    if kind == 'JBIS_IDENTITY_PROFILE':
        require(proof['url'] == 'https://www.jbis.or.jp/horse/' + key[5:] + '/'
                and '生年月日' in text, 'independent horse profile')
        return text
    if kind == 'JRA_VICTOIRE_RITTO':
        require(key == 'jbis-0001046333' and proof['country'] == 'JP'
                and all(t in text for t in ('ヴィクトワールピサ', '2007年3月31日', '角居勝彦', '（栗東）')),
                'JRA horse and Ritto affiliation')
    elif kind == 'JBIS_SPECIAL_WEEK_RITTO':
        require(key == 'jbis-0000293624' and proof['country'] == 'JP'
                and all(t in text for t in ('スペシャルウィーク', '1995.05.02', '白井寿昭', '(栗東)')), 'JBIS Ritto')
    elif kind == 'JBIS_TAIKI_MIHO':
        require(key == 'jbis-0000287925' and proof['country'] == 'JP'
                and all(t in text for t in ('タイキシャトル', '1994.03.23', '藤沢和雄', '(美浦)')), 'JBIS Miho')
    elif kind == 'IFHA_DECLARATION_IRISH_TRAINED':
        require(key == 'jbis-0001181460' and proof['country'] == 'IE'
                and 'IrishtraineddirtdebutantDECLARATIONOFWAR(USA)' in text, 'explicit Irish trained')
    else:
        require('Trained' in text, 'trained column header')
        if kind == 'IFHA_HENNY_TRAINED_COLUMN':
            require(key == 'jbis-0001028940' and proof['country'] == 'US'
                    and proof['last_trained_on'] == '2006-10-07'
                    and any(len(r) == 15 and r[5:9] == ['HENNY HUGHES (USA)', '3', 'C', 'USA']
                            and r[11] == '26th Aug/7th Oct' for r in parser.rows), 'Henny trained country')
        elif kind == 'IFHA_DISCREET_TRAINED_COLUMN_USA':
            require(key == 'jbis-0000985381' and proof['country'] == 'US'
                    and proof['last_trained_on'] == '2006-11-25'
                    and any(len(r) == 15 and r[5:9] == ['DISCREET CAT (USA)', '3', 'C', 'USA']
                            and r[11] == '25th Nov' for r in parser.rows), 'Discreet USA date')
        elif kind == 'IFHA_DISCREET_TRAINED_COLUMN_UAE':
            require(key == 'jbis-0000985381' and proof['country'] == 'AE'
                    and proof['last_trained_on'] == '2006-03-25'
                    and any(len(r) == 22 and r[12:16] == ['Discreet Cat (USA)', '3', 'C', 'UAE']
                            and r[18] == '25th Mar' for r in parser.rows), 'Discreet UAE date')
        elif kind == 'IFHA_MAKFI_TRAINED_COLUMN':
            require(key == 'jbis-0001128881' and proof['country'] == 'FR'
                    and any(r == ['3', 'MAKFI (GB)', '128', 'FR'] for r in parser.rows), 'Makfi trained FR, not birth GB')
        elif kind == 'IFHA_PYRO_TRAINED_COLUMN':
            require(key == 'jbis-0001085636' and proof['country'] == 'US'
                    and proof['last_trained_on'] == '2009-09-05'
                    and any(len(r) == 16 and r[4:10] == ['Pyro (USA)', 'Pulpit (USA)', '2005', 'C', 'S. bin Suroor', 'USA']
                            and r[12] == '5th Sept' for r in parser.rows), 'Pyro trained country and date')
        else:
            raise ValueError('unknown affiliation proof')


def check_batch(root, registry, checkpoint):
    batch = read(root / BASE / 's5-batches/batch-01/verification.json')
    cutoff = batch['data_cutoff']
    require(batch['schema_version'] == 'training-country-priority-batch-v1' and batch['batch'] == 1
            and batch['baseline_cutoff'] == checkpoint['data_cutoff']
            and batch['reviewed_at'] == cutoff and dt(checkpoint['data_cutoff']) < dt(cutoff) <= dt(stamp())
            and batch['mode'] == 'REPLAY' and batch['production_eligible'] is False
            and batch['webui_in_scope'] is False, 'batch boundary')
    require(batch['scope_count'] == dict(reviewed=10, registry_added=10, registered_sire_damsire=102,
            remaining_unsearched=511, searched_zero_match=0, unresolved_latest_date=0), 'batch counts')
    reviews = batch['reviews']
    queue = checkpoint['unsearched_priority_queue']
    require([r['horse_key'] for r in reviews] == [r['horse_key'] for r in queue[:10]], 'first ten in priority order')
    for review, original in zip(reviews, queue):
        key = review['horse_key']
        require(all(review[k] == v for k, v in original.items()), 'batch priority fields')
        profile_text = raw_proof(root, review['profile'], key, cutoff)
        require(re.sub(r'\s+', '', review['horse_name']) in profile_text
                and str(review['birth_year']) + '.' in profile_text, 'profile name and birth year')
        for proof in review['affiliations']:
            raw_proof(root, proof, key, cutoff)
        countries = {p['country'] for p in review['affiliations']}
        if len(countries) == 1:
            require(review['selection_method'] == 'ONE_COUNTRY_STOP', 'single-country stop')
            selected = review['affiliations'][0]
        else:
            require(review['selection_method'] == 'LATEST_CONFIRMED_AFFILIATION_DATE'
                    and all(p['last_trained_on'] for p in review['affiliations']), 'multiple countries need actual dates')
            latest = max(p['last_trained_on'] for p in review['affiliations'])
            require(len({p['country'] for p in review['affiliations'] if p['last_trained_on'] == latest}) == 1, 'latest country tie')
            selected = max(review['affiliations'], key=lambda p: p['last_trained_on'])
        require(review['selected_country'] == selected['country'], 'selected country')
        record = read(registry.path(key))
        n = len(review['before_revision_hashes'])
        require([r['content_hash'] for r in record['revisions'][:n]] == review['before_revision_hashes'], 'batch old revisions')
        for count, field in ((n, 'before_record_hash'), (n + 1, 'after_record_hash')):
            snapshot = copy.deepcopy(record)
            snapshot['revisions'] = snapshot['revisions'][:count]
            require(digest(snapshot) == review[field], 'batch record readback')
        fact = registry.fact(key, 'attribute:training_country_matches', cutoff)
        require(fact['status'] == 'VERIFIED' and fact['revision_id'] == review['added_revision_id']
                and fact['content_hash'] == review['added_revision_content_hash']
                and fact['source']['record_hash'] == selected['sha256']
                and fact['source']['record_hash_kind'] == selected['hash_kind'], 'saved new fact')
        matches = []
        for proof in review['affiliations']:
            match = dict(country=proof['country'], source=dict(url=proof['url'],
                         record_hash=proof['sha256'], captured_at=proof['captured_at']))
            if proof['last_trained_on']:
                match['last_trained_on'] = proof['last_trained_on']
            matches.append(match)
        require(fact['value'] == dict(schema_version='training-country-matches-v1', search_completed=True, matches=matches)
                and dt(fact['first_observed_at']) > dt(checkpoint['data_cutoff'])
                and dt(record['revisions'][n]['captured_at']) >= max(dt(p['captured_at']) for p in review['affiliations']), 'fact matches captured proof')
        require(review['writer_added'] == 1 and review['repeated_save_added'] == 0
                and review['historical_cutoff_status'] == 'NOT_FOUND'
                and registry.fact(key, 'attribute:training_country_matches', checkpoint['data_cutoff'])['status'] == 'NOT_FOUND',
                'CAS/idempotency/historical cutoff')
    require(batch['remaining_priority_queue'] == queue[10:] and batch['next_batch'] == queue[10:20], 'next ten and remaining queue')
    inventory = read(root / checkpoint['source_inventory_path'])
    review_map = {r['horse_key']: r for r in reviews}
    for row in inventory['subjects']:
        fact = registry.fact(row['horse_key'], 'attribute:training_country_matches', cutoff)
        expected = 'VERIFIED_TRAINING_COUNTRY_REGISTRY' if fact['status'] == 'VERIFIED' else 'NOT_YET_SEARCHED_FOR_TRAINING_COUNTRY'
        require(row['status'] == expected, 'current inventory status')
        if row['horse_key'] in review_map:
            require(row['training_country'] == review_map[row['horse_key']]['selected_country'], 'inventory country')
    require(inventory['scope_count']['registered_sire_damsire'] == 102
            and inventory['scope_count']['unsearched'] == 511
            and inventory['scope_count']['previous_source_only_reviews'] == 0, 'current inventory counts')
    return dict(reviewed=10, added_revisions=10, registered=102, remaining=511)


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
            require((old_rows[subject['horse_key']]['sire_uses'], old_rows[subject['horse_key']]['damsire_uses'])
                    == (subject['sire_uses'], subject['damsire_uses']), 'original usage references')
        # 表示整形に依存せず元commitのblob本文と、固定した意味内容hashを照合。
        request = ''.join(s['before_git_blob_sha'] + '\n' for s in subjects).encode()
        output = subprocess.check_output(prefix + ['cat-file', '--batch'], input=request)
        position = 0
        for subject in subjects:
            end = output.index(b'\n', position)
            header = output[position:end].decode().split()
            require(header[:2] == [subject['before_git_blob_sha'], 'blob'], 'original blob object')
            size = int(header[2])
            data = output[end + 1:end + 1 + size]
            position = end + size + 2
            require(git_blob(data) == subject['before_git_blob_sha']
                    and digest(json.loads(data)) == subject['before_record_hash'], 'original record body')
        require(position == len(output), 'original blob readback length')
    result = dict(subjects=613, registered_at_start=92, unsearched_at_start=521,
                  stale_statuses_corrected=5)
    if (root / BASE / 's5-batches/batch-01/verification.json').exists():
        result['batch_01'] = check_batch(root, registry, manifest)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', type=Path)
    args = parser.parse_args()
    print(json.dumps(check(repo=args.repo), ensure_ascii=False, sort_keys=True))
