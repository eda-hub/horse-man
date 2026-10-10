#!/usr/bin/env python3
"""利用者指定の末尾国追記を、元一覧・原文・時点・固定履歴から照合する。"""
import copy
import hashlib
import json
import re
from pathlib import Path
from pedigree_registry import Registry, country_name_suffix, explicit_user_countries, digest, dt

BASE = Path('data/pedigree/reconciliations/2026-10-10-training-priority/s5-remaining')

def require(ok, message):
    if not ok:
        raise ValueError(message)

def check(root=Path('.')):
    root = Path(root)
    directory = root / BASE / 'user-country-confirmations'
    if not (directory / 'progress.json').exists():
        return {'confirmed': 0}
    p = json.loads((directory / 'progress.json').read_text())
    registry = Registry(root / 'data/pedigree')
    require(hashlib.sha256(p['user_reply_text'].encode()).hexdigest() == p['user_reply_sha256'], 'original user reply hash')
    require(hashlib.sha256(p['original_needs_information'].encode()).hexdigest() == p['original_needs_information_sha256'], 'original waiting list hash')
    rows = []
    for line in p['original_needs_information'].splitlines():
        if re.match(r'^\|\d', line):
            cols = line.split('|')[1:-1]
            rows.append((cols[2].strip('`'), cols[1], country_name_suffix(cols[1])))
    eligible = [r for r in rows if r[2]]
    require(len(rows) == 95 and len(eligible) == 84, 'explicit eligible scope')
    seen = []
    for path in p['batches']:
        batch = json.loads((root / path).read_text())
        require(dt(p['received_at']) <= dt(batch['data_cutoff']), 'reply precedes saving')
        for review in batch['reviews']:
            key = review['horse_key']; record = json.loads(registry.path(key).read_text())
            n = len(review['before_revision_hashes']); before = copy.deepcopy(record); before['revisions'] = before['revisions'][:n]
            require(digest(before) == review['before_record_hash'] and len(record['revisions']) == n+1, 'one user-only append, unchanged previous record')
            require([r['content_hash'] for r in before['revisions']] == review['before_revision_hashes'], 'prior revisions preserved')
            require(digest(record) == review['after_record_hash'], 'record readback hash')
            fact = registry.fact(key, 'attribute:training_country_user', batch['data_cutoff'])
            require(fact['status'] == 'VERIFIED' and fact['value'] == review['country'] == country_name_suffix(record['identity']['name']), 'name country answer readback')
            source = fact['source']
            require(source['source_class'] == 'USER_PROVIDED' and source['resolution_policy'] == p['resolution_policy'] == 'USER_CONFIRMED_NAME_SUFFIX_V1', 'user provenance/policy')
            require(source['user_reply_text'] == p['user_reply_text'] and source['record_hash'] == p['user_reply_sha256'] and source['subject_name'] == record['identity']['name'], 'reply and subject bound')
            revision = record['revisions'][-1]
            registry.validate_fact(revision)
            require(revision['revision_id'] == review['added_revision_id'] and review['repeated_save_added'] == 0, 'CAS/idempotency receipt')
            require(revision['first_observed_at'] == p['received_at'] and dt(revision['captured_at']) <= dt(batch['data_cutoff']), 'real reply time/cutoff')
            require(registry.fact(key, 'attribute:training_country_user', p['historical_search_cutoff'])['status'] == 'NOT_FOUND', 'no retroactive answer')
            require(registry.fact(key, 'attribute:training_country_matches', p['historical_search_cutoff'])['status'] == 'VERIFIED', 'search retained')
            seen.append(key)
    require(seen == [r[0] for r in eligible[:len(seen)]], 'continuous answer prefix without duplicates')
    require(p['confirmed'] == len(seen) and p['remaining'] == 95-len(seen) and p['resolved_total'] == 518+len(seen), 'resolution counts')
    direct_seen = []
    direct_path = directory / 'explicit-country-reply.json'
    if direct_path.exists():
        direct = json.loads(direct_path.read_text())
        require(hashlib.sha256(direct['user_reply_text'].encode()).hexdigest() == direct['user_reply_sha256'], 'direct reply original hash')
        replies = direct['user_replies']
        mapping = {}
        for reply in replies:
            require(hashlib.sha256(reply['text'].encode()).hexdigest() == reply['sha256'], 'each direct reply original hash')
            mapping.update(explicit_user_countries(reply['text']))
        require(len(mapping) == len(direct['reviews']) == 11, 'all explicit reply lines saved')
        waiting_names = {name: key for key, name, country in rows if not country}
        for review in direct['reviews']:
            key = review['horse_key']; record = json.loads(registry.path(key).read_text())
            require(waiting_names.get(review['horse_name']) == key and mapping.get(record['identity']['name']) == review['country'], 'explicit reply identity bound to waiting scope')
            before = copy.deepcopy(record); before['revisions'] = before['revisions'][:-1]
            require(digest(before) == review['before_record_hash'] and digest(record) == review['after_record_hash'], 'direct append preserves whole previous record')
            require([r['content_hash'] for r in before['revisions']] == review['before_revision_hashes'], 'direct old revisions retained')
            fact = registry.fact(key, 'attribute:training_country_user', direct['data_cutoff'])
            require(fact['status'] == 'VERIFIED' and fact['value'] == review['country'], 'direct answer readback')
            source = fact['source']
            reply = replies[review['reply_index']]
            require(source['resolution_policy'] == 'USER_EXPLICIT_COUNTRY_V1' and source['source_class'] == 'USER_PROVIDED' and source['record_key'] == key and source['subject_name'] == record['identity']['name'], 'direct provenance/identity')
            require(source['user_reply_text'] == reply['text'] and source['record_hash'] == reply['sha256'], 'direct original reply binding')
            revision = record['revisions'][-1]; registry.validate_fact(revision)
            require(revision['revision_id'] == review['added_revision_id'] and review['repeated_save_added'] == 0, 'direct CAS/idempotency')
            require(revision['first_observed_at'] == reply['received_at'] and dt(revision['captured_at']) <= dt(direct['data_cutoff']), 'direct reply time/cutoff')
            require(registry.fact(key, 'attribute:training_country_user', p['historical_search_cutoff'])['status'] == 'NOT_FOUND', 'no backdated direct answer')
            require(registry.fact(key, 'attribute:training_country_matches', p['historical_search_cutoff'])['status'] == 'VERIFIED', 'direct original search retained')
            direct_seen.append(key)
        require(len(set(direct_seen)) == 11 and not set(direct_seen).intersection(seen), 'direct replies not duplicate suffix scope')
    if len(seen) == 84:
        waiting = (root / BASE / 'needs-information.md').read_text()
        actual = [line.split('|')[3].strip('`') for line in waiting.splitlines() if re.match(r'^\|\d', line)]
        require(actual == [r[0] for r in rows if not r[2] and r[0] not in direct_seen], 'only unanswered horses remain waiting')
    return {'confirmed': len(seen)+len(direct_seen), 'remaining': 95-len(seen)-len(direct_seen), 'resolved_total': 518+len(seen)+len(direct_seen)}

if __name__ == '__main__':
    print(json.dumps(check(), ensure_ascii=False))
