"""指定祖先12頭の本人プロフィール原票・追記・過去時点を照合する。"""
import base64
import copy
import gzip
import hashlib
import html
import json
import re
from pathlib import Path
from pedigree_registry import Registry, digest, dt, explicit_user_countries

BASE = Path('data/pedigree/reconciliations/2026-10-10-training-priority')
COUNTRIES = {'米国': 'US', '愛国': 'IE', '仏国': 'FR', '英国': 'GB', '加国': 'CA', '伊国': 'IT'}

def require(ok, message):
    if not ok:
        raise ValueError(message)

def source_text(entry):
    body = base64.b64decode(entry['body_base64'], validate=True)
    meta = entry['capture']
    require(meta['http_status'] == 200 and meta['hash_kind'] == 'response-body-sha256' and hashlib.sha256(body).hexdigest() == meta['sha256'] and len(body) == meta['bytes'], 'original response hash')
    encoding = 'shift_jis' if 'ahonoora.com/' in meta['final_url'] else 'utf-8'
    return re.sub(r'\s+', ' ', html.unescape(re.sub('<[^>]+>', ' ', body.decode(encoding, errors='replace'))))

def profile_countries(entry, name, year):
    text = source_text(entry)
    require(re.search(r'馬名 (?:\*トニービン )?' + re.escape(name) + r'(?: |$)', text) is not None, 'profile individual name')
    require(re.search(r'生年月日 ' + str(year) + r'\.', text) is not None, 'profile birth year')
    profile = re.search(r'馬名 .*? 血統表', text)
    require(profile is not None, 'bounded own profile')
    trainer = re.search(r' 調教師 (.*?) 馬主 ', profile.group())
    require(trainer is not None, 'own trainer field')
    countries = re.findall(r'（([^）]+)）', trainer.group(1))
    require(countries and all(c in COUNTRIES for c in countries), 'explicit trainer affiliation countries')
    return sorted({COUNTRIES[c] for c in countries}), trainer.group(1)

def check_user_resolution(directory, registry, scope, progress):
    resolution = progress.get('user_resolution')
    if not resolution:
        return
    m = json.loads((directory / 'explicit-country-reply.json').read_text())
    require(m['mode'] == 'REPLAY' and m['production_eligible'] is False, 'user reply replay boundary')
    target = next(t for t in scope['subjects'] if t['horse_key'] == m['horse_key'])
    require(m['subject_name'] in target['terms'] and m['birth_year'] == target['birth_year'], 'explicit subject identity')
    require(hashlib.sha256(m['user_reply_text'].encode()).hexdigest() == m['user_reply_sha256'], 'user reply hash')
    require(explicit_user_countries(m['user_reply_text']).get(m['subject_name']) == m['country'], 'user reply country')
    record = json.loads(registry.path(m['horse_key']).read_text())
    n = len(m['before_revision_hashes']); record['revisions'] = record['revisions'][:n+1]
    before = copy.deepcopy(record); before['revisions'] = before['revisions'][:n]
    require(digest(before) == m['before_record_hash'] and digest(record) == m['after_record_hash'], 'user append readback')
    require([r['content_hash'] for r in before['revisions']] == m['before_revision_hashes'], 'user old revisions intact')
    revision = record['revisions'][-1]; registry.validate_fact(revision)
    require(revision['revision_id'] == m['added_revision_id'] and revision['value'] == m['country'] and revision['source']['record_key'] == m['horse_key'], 'user country saved')
    require(revision['source']['user_reply_text'] == m['user_reply_text'] and revision['source']['user_received_at'] == m['received_at'], 'user original receipt')
    require(dt(m['historical_cutoff']) < dt(m['received_at']) <= dt(revision['captured_at']) <= dt(m['data_cutoff']), 'user real receipt cutoff')
    require(registry.fact(m['horse_key'], 'attribute:training_country_user', m['historical_cutoff'])['status'] == 'NOT_FOUND', 'user historical cutoff intact')
    require(m['repeated_save_added'] == 0 and resolution['externally_registered'] == 11 and resolution['user_confirmed'] == 1 and resolution['resolved_total'] == 12 and resolution['remaining'] == 0, 'user resolution counts')

def check(root=Path('.')):
    root = Path(root); directory = root / BASE / 's6-designated-ancestors'
    if not (directory / 'progress.json').exists():
        return {'reviewed': 0}
    progress = json.loads((directory / 'progress.json').read_text())
    scope = json.loads((root / BASE / 'designated-ancestor-target-review.json').read_text())
    queue = scope['country_research_queues']['additional_ancestor_queue']
    archive = (root / progress['bundle_path']).read_bytes()
    require(hashlib.sha256(archive).hexdigest() == progress['bundle_sha256'], 'source bundle hash')
    bundle = json.loads(gzip.decompress(archive)); registry = Registry(root / 'data/pedigree'); seen = []; registered = 0
    for path in progress['batches']:
        batch = json.loads((root / path).read_text())
        require(batch['mode'] == 'REPLAY' and batch['production_eligible'] is False, 'replay boundary')
        for review in batch['reviews']:
            key = review['horse_key']; require(key == queue[len(seen)], 'continuous independent ancestor scope')
            record = json.loads(registry.path(key).read_text()); record['revisions'] = record['revisions'][:len(review['before_revision_hashes'])+1]; before = copy.deepcopy(record); before['revisions'] = before['revisions'][:-1]
            require(digest(before) == review['before_record_hash'] and digest(record) == review['after_record_hash'], 'whole record append/readback')
            require([r['content_hash'] for r in before['revisions']] == review['before_revision_hashes'], 'old revisions intact')
            entry = bundle[review['proof_key']]
            if review['proof_kind'] == 'OWN_PROFILE_TRAINER_COUNTRY':
                countries, trainer = profile_countries(entry, review['source_name'], record['identity']['birth_year'])
                require(trainer == review['trainer_field'], 'trainer extraction receipt')
            else:
                require(key == 'jbis-0000333952' and review['proof_kind'] == 'WIKIPEDIA_EXPLICIT_TRAINING_CATEGORY', 'explicit category scope')
                text = source_text(entry)
                require('Grey Sovereign' in text and '1948' in text and 'George Beeby' in text and 'Racehorses trained in the United Kingdom' in text, 'own training category, identity and trainer')
                countries = ['GB']
            require(countries == sorted({m['country'] for m in review['matches']}), 'training country proofs')
            for proof_key in review['additional_lookup_keys']:
                item = bundle[proof_key]
                if 'body_base64' in item:
                    source_text(item)
            fact = registry.fact(key, 'attribute:training_country_matches', batch['data_cutoff'])
            require(fact['status'] == 'VERIFIED' and fact['value']['matches'] == review['matches'], 'saved matches readback')
            require(fact['source']['record_hash'] == entry['capture']['sha256'], 'source raw binding')
            for match in review['matches']:
                require(match['source']['record_hash'] == entry['capture']['sha256'] and match['source']['url'] == entry['capture']['final_url'], 'individual match source binding')
            revision = record['revisions'][-1]; registry.validate_fact(revision)
            require(revision['revision_id'] == review['added_revision_id'] and review['writer_added'] == 1 and review['repeated_save_added'] == 0, 'single writer/CAS receipt')
            require(dt(entry['capture']['captured_at']) <= dt(revision['first_observed_at']) <= dt(batch['data_cutoff']) and dt(revision['captured_at']) <= dt(batch['data_cutoff']), 'real acquisition and save cutoff')
            require(registry.fact(key, 'attribute:training_country_matches', scope['data_cutoff'])['status'] == 'NOT_FOUND', 'historical cutoff intact')
            selected = countries[0] if len(countries) == 1 else None
            require(review['selected_country'] == selected, 'no undated multi-country inference')
            registered += selected is not None; seen.append(key)
    require(progress['reviewed'] == len(seen) and progress['registered'] == registered and progress['unsearched'] == 12-len(seen) and progress['latest_date_unresolved'] == len(seen)-registered, 'counts')
    check_user_resolution(directory, registry, scope, progress)
    result = {k: progress[k] for k in ['reviewed', 'registered', 'latest_date_unresolved', 'unsearched']}
    if progress.get('user_resolution'):
        result['user_confirmed'] = progress['user_resolution']['user_confirmed']
        result['resolved_total'] = progress['user_resolution']['resolved_total']
        result['remaining'] = progress['user_resolution']['remaining']
    return result

if __name__ == '__main__':
    print(json.dumps(check(), ensure_ascii=False))
