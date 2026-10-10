#!/usr/bin/env python3
"""手順5の追加入力を、10頭単位の原票本文・CAS・固定時点から検査する。"""
import base64
import copy
import gzip
import hashlib
import json
import re
from pathlib import Path
from functools import lru_cache
from html import unescape

from pedigree_registry import Registry, digest, dt, stamp
from check_training_country_priority import BASE, CHECKPOINT, HTMLRows, read, require

TRAINING_CENTRES_JP = ('栗東', '美浦', '北海道', '岩手', '水沢', '盛岡', '浦和', '船橋', '大井', '川崎', '金沢', '笠松', '名古屋', '園田', '兵庫', '姫路', '高知', '佐賀', '門別', '福山', '荒尾', '益田', '宇都宮', '高崎', '新潟', '上山', '足利', '三条', '中津', '帯広', '旭川')

CONTINUATION = BASE / 's5-remaining/progress.json'
COUNTRIES = {'USA': 'US', 'US': 'US', 'JPN': 'JP', 'JP': 'JP', 'IRE': 'IE', 'IE': 'IE',
             'GB': 'GB', 'FR': 'FR', 'GER': 'DE', 'DE': 'DE', 'UAE': 'AE', 'AE': 'AE',
             'AUS': 'AU', 'AU': 'AU', 'NZ': 'NZ', 'HK': 'HK', 'SAF': 'ZA', 'ZA': 'ZA',
             'ARG': 'AR', 'AR': 'AR', 'CHI': 'CL', 'CL': 'CL', 'CAN': 'CA', 'CA': 'CA',
             'ITY': 'IT', 'IT': 'IT', 'BRZ': 'BR', 'BR': 'BR', 'URU': 'UY', 'UY': 'UY',
             'SIN': 'SG', 'SG': 'SG', 'KSA': 'SA', 'SA': 'SA', 'BHR': 'BH', 'BH': 'BH', 'GNY': 'DE', 'CZ': 'CZ', 'CZE': 'CZ', 'HUN': 'HU', 'PER': 'PE', 'SPA': 'ES', 'TUR': 'TR'}


def text(fragment):
    parser = HTMLRows()
    parser.feed(fragment)
    return re.sub(r'\s+', ' ', ' '.join(parser.text)).strip()


def name(value):
    return re.sub(r'\s+', '', unescape(value).replace('’', "'").replace('＇', "'")).casefold()


def english(value):
    return name(re.sub(r'\([A-Z]{2,3}\)$', '', value.strip()))


def profile_name(value):
    return name(re.sub(r'\s*[（(](?:[A-Z]{2,3}|英|米|仏|愛|独|豪|加|日|伊|亜|新|伯|智|南)[）)]$', '', value))


def decode_html(data):
    header = data[:12000].decode('ascii', errors='ignore')
    encoding = re.search(r'charset\s*=\s*["\']?([A-Za-z0-9_-]+)', header, re.I)
    if encoding:
        label = encoding.group(1).lower().replace('_', '-')
        if label in ('utf-8', 'euc-jp', 'shift-jis', 'sjis', 'windows-1252', 'iso-8859-1'):
            return data.decode('cp932' if label in ('shift-jis', 'sjis') else label, errors='replace')
    try:
        return data.decode('utf-8')
    except UnicodeDecodeError:
        try:
            return data.decode('euc-jp')
        except UnicodeDecodeError:
            return data.decode('cp1252')


def _profile_fields_html(html, meta, identity):
    accepted = {profile_name(identity['name']), *(profile_name(a) for a in identity.get('aliases', []))}
    headings = [text(h) for h in re.findall(r'<h1[^>]*>(.*?)</h1>', html, re.S)]
    matched_headings = [h for h in headings if profile_name(h) in accepted]
    if not matched_headings:
        return None
    heading = matched_headings[0]
    url = meta.get('final_url', '')
    if 'jbis.or.jp/horse/' in url:
        fields = {text(k): text(v) for k, v in re.findall(r'<dt[^>]*>(.*?)</dt>\s*<dd[^>]*>(.*?)</dd>', html, re.S)}
        birth = fields.get('生年月日', '')
        matched = re.match(r'(\d{4})(?:\.\d{2}\.\d{2}|年)(?:\s|$)', birth)
        if identity['external_ids'].get('JBIS'):
            require('/horse/' + identity['external_ids']['JBIS'] + '/' in url, 'profile independent JBIS ID')
        en = re.search(r'<span class="hdg1-search__sub">(.*?)</span>', html, re.S)
        en = text(en.group(1)) if en else heading
    elif any(host in url for host in ('db.sp.netkeiba.com/horse/', 'db.netkeiba.com/horse/')):
        parser = HTMLRows()
        parser.feed(html)
        fields = {r[0]: r[1] for r in parser.rows if len(r) == 2}
        birth = fields.get('生年月日', '')
        matched = re.match(r'(\d{4})年(?:\d{1,2}月\d{1,2}日)?', birth)
        en = re.search(r'const bameiEng\s*=\s*"([^"]*)"', html)
        if en:
            en = unescape(en.group(1))
        else:
            title = re.search(r'<title>\s*' + re.escape(heading) + r'\s*\(([^)]*)\)\s*\|', html)
            en = unescape(title.group(1)) if title else heading
        require(identity['external_ids'].get('NETKEIBA') in url, 'profile independent netkeiba ID')
    else:
        return None
    if '\ufffd' in heading + birth + fields.get('調教師', ''):
        return None
    if not matched or int(matched.group(1)) != identity.get('birth_year'):
        return None
    if re.fullmatch(r"[A-Za-z0-9 '’.,()\-]+", heading) and not re.fullmatch(r"[A-Za-z0-9 '’.,()\-]+", en or ''):
        en = heading
    return dict(heading=heading, english_name=en, birth=birth, trainer=fields.get('調教師', ''))


def profile_fields(data, meta, identity):
    variants = [('document-declared-or-strict-fallback', decode_html(data))]
    if 'netkeiba.com/horse/' in meta.get('final_url', ''):
        variants.extend((encoding, data.decode(encoding, errors='replace')) for encoding in ('utf-8', 'euc-jp'))
    for encoding, html in variants:
        result = _profile_fields_html(html, meta, identity)
        if result is not None:
            result['decoded_encoding'] = encoding
            return result
    return None


def domestic_country(fields):
    affiliation = re.sub(r'\s+', '', fields['trainer'])
    # 所属センターが本人の調教師欄に明記された場合だけ採用する。
    return 'JP' if any('(' + x + ')' in affiliation or affiliation.startswith(x) for x in TRAINING_CENTRES_JP) else None


@lru_cache(maxsize=32)
def parsed_rows(data):
    parser = HTMLRows()
    parser.feed(decode_html(data))
    return parser.rows


def ranking_rows(data, year, profile, identity):
    rows = parsed_rows(data)
    headers = next((r for r in rows if 'Trained' in r and 'Horse' in r), None)
    if not headers:
        return []
    h, t = headers.index('Horse'), headers.index('Trained')
    y = headers.index('YOF') if 'YOF' in headers else None
    age = headers.index('A') if 'A' in headers else headers.index('a.s') if 'a.s' in headers else None
    found = []
    for row in rows:
        if len(row) != len(headers) or english(row[h]) != english(profile['english_name']):
            continue
        if y is not None:
            if row[y] != str(identity['birth_year']):
                continue
        elif age is not None:
            age_match = re.match(r'^(\d+)', row[age])
            if not age_match or year - int(age_match.group(1)) != identity['birth_year']:
                continue
        else:
            continue
        tokens = re.split(r'\s*/\s*', row[t])
        if not tokens or any(token not in COUNTRIES for token in tokens):
            continue
        for token in tokens:
            found.append(dict(proof_kind='IFHA_EXPLICIT_TRAINED_COLUMN', country=COUNTRIES[token],
                              row=row, reference_year=year, last_trained_on=None))
    return found


WIKI_TRAINING_COUNTRIES = {'United States': 'US', 'Ireland': 'IE', 'United Kingdom': 'GB',
                         'France': 'FR', 'Germany': 'DE', 'Italy': 'IT', 'Canada': 'CA',
                         'Australia': 'AU', 'New Zealand': 'NZ', 'Japan': 'JP',
                         'Argentina': 'AR', 'Chile': 'CL', 'Hong Kong': 'HK',
                         'United Arab Emirates': 'AE', 'South Africa': 'ZA', 'Brazil': 'BR', 'Uruguay': 'UY', 'Peru': 'PE', 'Spain': 'ES', 'Turkey': 'TR', 'Sweden': 'SE', 'Norway': 'NO', 'Czech Republic': 'CZ', 'Hungary': 'HU', 'Denmark': 'DK'}


@lru_cache(maxsize=4)
def pdf_text(data):
    import subprocess, tempfile
    with tempfile.NamedTemporaryFile(suffix='.pdf') as stream:
        stream.write(data); stream.flush()
        return subprocess.check_output(['pdftotext', '-layout', stream.name, '-']).decode()


def supplementary_countries(data, meta, profile, identity, kind):
    if kind == 'WIKIPEDIA_EXPLICIT_TRAINING_CATEGORY':
        require(meta['final_url'].startswith('https://en.wikipedia.org/wiki/'), 'Wikipedia original page')
        html = decode_html(data)
        headings = [text(h) for h in re.findall(r'<h1[^>]*>(.*?)</h1>', html, re.S)]
        valid_name = any(english(re.sub(r'\s*\(horse\)$', '', h)) == english(profile['english_name']) for h in headings)
        foaled = [r[1] for r in parsed_rows(data) if len(r) == 2 and r[0] == 'Foaled']
        if not valid_name or not any(re.search(r'(?<!\d)' + str(identity['birth_year']) + r'(?!\d)', f) for f in foaled):
            return []
        countries = sorted({WIKI_TRAINING_COUNTRIES[c] for c in (re.sub(r'^the ', '', c) for c in re.findall(r'title="Category:Racehorses trained in ([^"]+)"', html)) if c in WIKI_TRAINING_COUNTRIES})
        return countries
    if kind == 'TJC_2001_EXPLICIT_CLASSIFICATION_TRAINED':
        require(meta['final_url'] == 'https://www.tjcis.com/pdf/icsc02/EndMaterial2002.pdf' and data.startswith(b'%PDF'), 'cataloguing standards original PDF')
        contents = pdf_text(data)
        require('Trained' in contents and re.search(r'INTERNATIONAL CLASSIFICATION\s+[—-]?\s*2001', contents), 'classification year and trained column')
        label = re.sub(r'\([A-Z]{2,3}\)$', '', profile['english_name']).strip()
        matches = []
        for line in contents.splitlines():
            found = re.search(r'^\s*(?:\d+(?:\.\d+)?\s+){0,2}\*?' + re.escape(label) + r"\s+\([A-Z]{2,3}\)\s+(\d+)\s+[CFHGM]\s+.*?\s([A-Z]{2,3})\s*$", line, re.I)
            if found and 2001 - int(found.group(1)) == identity['birth_year'] and found.group(2).upper() in COUNTRIES:
                matches.append(COUNTRIES[found.group(2).upper()])
        return sorted(set(matches))
    if kind == 'IFHA_2003_EXPLICIT_CLASSIFICATION_TRAINED':
        require(meta['final_url'] == 'https://www.ifhaonline.org/resources/Ratings_AlphaList_04.pdf' and data.startswith(b'%PDF'), 'IFHA classification original PDF')
        contents = pdf_text(data)
        require('2003 INTERNATIONAL CLASSIFICATIONS' in contents and 'Trained' in contents, 'classification year and trained column')
        label = re.sub(r'\([A-Z]{2,3}\)$', '', profile['english_name']).strip()
        countries = []
        for line in contents.splitlines():
            found = re.search(r'^\s*\d+\s+(?:[SMILE]\s+)*' + re.escape(label) + r'\s+\([A-Z]{2,3}\)\s+(\d+)\s+[CFHGM]\s+([A-Z]{2,3})\s+', line, re.I)
            if found and 2003 - int(found.group(1)) == identity['birth_year'] and found.group(2).upper() in COUNTRIES:
                countries.append(COUNTRIES[found.group(2).upper()])
        return sorted(set(countries))
    if kind == 'WIKIPEDIA_JA_EXPLICIT_TRAINER_AFFILIATION':
        require(meta['final_url'].startswith('https://ja.wikipedia.org/wiki/'), 'Japanese Wikipedia original profile')
        rows = parsed_rows(data)
        labels = [r[1] for r in rows if len(r) == 2 and r[0] == '欧字表記']
        births = [r[1] for r in rows if len(r) == 2 and r[0] in ('生誕', '生年月日')]
        if not any(english(l) == english(profile['english_name']) for l in labels) or not any(re.search(r'(?<!\d)' + str(identity['birth_year']) + r'年', b) for b in births):
            return []
        countries = {'アメリカ': 'US', 'アメリカ合衆国': 'US', '米国': 'US', 'イギリス': 'GB', '英国': 'GB', 'アイルランド': 'IE', 'フランス': 'FR', 'ドイツ': 'DE', 'イタリア': 'IT', 'オーストラリア': 'AU', 'カナダ': 'CA', 'アルゼンチン': 'AR', 'チリ': 'CL', 'アラブ首長国連邦': 'AE', '香港': 'HK'}
        trainers = [r[1] for r in rows if len(r) == 2 and r[0] == '調教師']
        return sorted({countries[c.strip()] for t in trainers for c in re.findall(r'[（(]([^）)]+)[）)]', t) if c.strip() in countries})
    if kind == 'ACP_ALDEBARAN_EXPLICIT_TRAINING_ENGLAND':
        require(meta['final_url'] == 'https://www.americanclassicpedigrees.com/aldebaran.html', 'reviewed biography original URL')
        contents = text(decode_html(data))
        require(english(profile['english_name']) == 'aldebaran' and identity['birth_year'] == 1998 and 'Aldebaran (USA) February 27, 1998' in contents, 'biography exact horse and birth year')
        require('He was trained by Henry Cecil (later Sir Henry Cecil) in England' in contents, 'own explicit training country; North America is not a country')
        return ['GB']
    raise ValueError('unsupported supplementary proof')


def captured(entry, cutoff):
    meta = entry['capture']
    data = base64.b64decode(entry['body_base64'], validate=True)
    require(meta['http_status'] == 200 and meta['hash_kind'] == 'http-response-body-bytes-sha256'
            and len(data) == meta['byte_length'] and hashlib.sha256(data).hexdigest() == meta['sha256']
            and dt(meta['request_started_at']) <= dt(meta['captured_at']) <= dt(cutoff), 'original source bytes')
    return data, meta


def check(root=Path('.')):
    root = Path(root)
    progress = read(root / CONTINUATION)
    baseline = read(root / CHECKPOINT)
    queue = baseline['unsearched_priority_queue'][10:]
    require(progress['schema_version'] == 'training-country-remaining-progress-v1'
            and progress['mode'] == 'REPLAY' and progress['production_eligible'] is False
            and progress['webui_in_scope'] is False, 'continuation boundary')
    reference_bytes = (root / progress['reference_bundle_path']).read_bytes()
    require(hashlib.sha256(reference_bytes).hexdigest() == progress['reference_bundle_sha256'], 'shared reference archive')
    references = json.loads(gzip.decompress(reference_bytes))
    additional_references = []
    for archive in progress.get('additional_reference_bundles', []):
        raw = (root / archive['path']).read_bytes()
        require(hashlib.sha256(raw).hexdigest() == archive['sha256'] and archive['active_from_batch'] >= 3, 'additional reference archive')
        additional_references.append((archive['active_from_batch'], json.loads(gzip.decompress(raw))))
    registry = Registry(root / 'data/pedigree')
    reviews = []
    counts = {'registered': 0, 'searched_without_country': 0, 'latest_date_unresolved': 0,
              'acquisition_blocked': 0}
    for expected_batch, batch_path in enumerate(progress['batches'], 2):
        batch = read(root / batch_path)
        references_for_batch = dict(references)
        for active_from, extra in additional_references:
            if expected_batch >= active_from:
                require(not set(extra).intersection(references_for_batch), 'distinct reference keys')
                references_for_batch.update(extra)
        cutoff = batch['data_cutoff']
        require(batch['batch'] == expected_batch and dt(baseline['data_cutoff']) < dt(cutoff) <= dt(stamp()), 'batch sequence/cutoff')
        zipped = (root / batch['bundle_path']).read_bytes()
        require(hashlib.sha256(zipped).hexdigest() == batch['bundle_sha256'], 'archive SHA256')
        bundle = json.loads(gzip.decompress(zipped))
        require(set(bundle) == {r['horse_key'] for r in batch['reviews']}, 'bundle subject scope')
        require(1 <= len(batch['reviews']) <= 10 and (len(batch['reviews']) == 10 or len(reviews) + len(batch['reviews']) == 511), 'ten-subject checkpoints')
        for review in batch['reviews']:
            key = review['horse_key']
            original = queue[len(reviews)]
            require(all(review[k] == v for k, v in original.items()), 'global priority order')
            record = read(registry.path(key))
            require(digest(record['identity']) == review['identity_hash'], 'independent identity preserved')
            n = len(review['before_revision_hashes'])
            before = copy.deepcopy(record)
            before['revisions'] = before['revisions'][:n]
            require(digest(before) == review['before_record_hash'] and [r['content_hash'] for r in before['revisions']] == review['before_revision_hashes'], 'old fact prefix unchanged')
            entry = bundle[key]
            if review['status'] == 'ACQUISITION_BLOCKED':
                require('body_base64' not in entry['profile'] or profile_fields(*captured(entry['profile'], cutoff), record['identity']) is None, 'blocked is not a valid profile')
                require(review['writer_added'] == 0 and len(record['revisions']) == n, 'failed retrieval creates no empty match fact')
                counts['acquisition_blocked'] += 1
                reviews.append(review)
                continue
            data, meta = captured(entry['profile'], cutoff)
            fields = profile_fields(data, meta, record['identity'])
            require(fields == review['profile_fields'] and fields is not None, 'profile heading and birth year')
            proved = []
            country = domestic_country(fields)
            if country:
                proved.append(dict(country=country, source=dict(url=meta['final_url'], record_hash=meta['sha256'], captured_at=meta['captured_at'])))
                require(not entry['rankings'] and not entry.get('supplementary'), 'domestic single country stop')
            else:
                for source in entry['rankings']:
                    if 'body_base64' not in source:
                        canonical = references_for_batch[source['source_key']]
                        require(source['capture'] == canonical['capture'] and source['year'] == canonical['year'], 'reference provenance exactly matches shared archive')
                        source = dict(source, body_base64=canonical['body_base64'])
                    raw, capture = captured(source, cutoff)
                    require(capture['final_url'].startswith('https://www.ifhaonline.org/'), 'IFHA original URL')
                    rows = ranking_rows(raw, source['year'], fields, record['identity'])
                    require(rows == source['matched_rows'] and rows, 'same-name birth-year trained column')
                    for row in rows:
                        match = dict(country=row['country'], source=dict(url=capture['final_url'], record_hash=capture['sha256'], captured_at=capture['captured_at']))
                        if match not in proved:
                            proved.append(match)
            if not country:
                expected_sources = []
                for source_key, source in references_for_batch.items():
                    raw, _ = captured(source, cutoff)
                    matched = ranking_rows(raw, source['year'], fields, record['identity'])
                    if matched:
                        expected_sources.append((source_key, matched))
                require([(source['source_key'], source['matched_rows']) for source in entry['rankings']] == expected_sources, 'all known trained rows, including multiple countries')
            for source in entry.get('supplementary', []):
                raw, capture = captured(source, cutoff)
                cs = supplementary_countries(raw, capture, fields, record['identity'], source['proof_kind'])
                require(cs == source['countries'] and cs, 'supplementary identity and explicit training category')
                for c in cs:
                    m = dict(country=c, source=dict(url=capture['final_url'], record_hash=capture['sha256'], captured_at=capture['captured_at']))
                    if m not in proved:
                        proved.append(m)
            for lookup in entry.get('additional_lookups', []):
                if 'body_base64' in lookup:
                    raw, capture = captured(lookup, cutoff)
                    cs = supplementary_countries(raw, capture, fields, record['identity'], lookup['proof_kind'])
                    require(set(cs).issubset({m['country'] for m in proved}), 'all known additional affiliations included')
            lookup = entry.get('supplementary_lookup')
            if lookup and 'body_base64' in lookup:
                raw, capture = captured(lookup, cutoff)
                cs = supplementary_countries(raw, capture, fields, record['identity'], 'WIKIPEDIA_EXPLICIT_TRAINING_CATEGORY')
                require(set(cs).issubset({m['country'] for m in proved}), 'do not omit a known supplementary training country')
            require(review['matches'] == proved, 'matches are exactly the reviewed explicit affiliations')
            countries = {m['country'] for m in proved}
            selected = next(iter(countries)) if len(countries) == 1 else None
            expected = 'REGISTERED' if selected else 'LATEST_DATE_UNRESOLVED' if countries else 'SEARCHED_WITHOUT_VERIFIED_COUNTRY'
            require(review['status'] == expected and review['selected_country'] == selected, 'known multi-country dates stay unknown')
            after = copy.deepcopy(record)
            after['revisions'] = after['revisions'][:n + 1]
            require(digest(after) == review['after_record_hash'] and len(record['revisions']) == n + 1, 'one appended revision')
            fact = registry.fact(key, 'attribute:training_country_matches', cutoff)
            require(fact['status'] == 'VERIFIED' and fact['value'] == dict(schema_version='training-country-matches-v1', search_completed=True, matches=proved)
                    and fact['revision_id'] == review['added_revision_id'] and fact['content_hash'] == review['added_revision_content_hash'], 'writer readback')
            primary = proved[0]['source'] if proved else dict(url=meta['final_url'], record_hash=meta['sha256'])
            require(fact['source']['url'] == primary['url'] and fact['source']['record_hash'] == primary['record_hash'] and fact['source']['record_hash_kind'] == 'http-response-body-bytes-sha256', 'fact primary provenance bound to raw proof')
            revision = record['revisions'][n]
            require(all(revision['verification'].get(k) is True for k in ('identity_checked', 'source_checked', 'relationship_checked')) and revision['verification'].get('reviewed_by')
                    and dt(revision['first_observed_at']) <= dt(revision['captured_at']) <= dt(cutoff)
                    and dt(revision['captured_at']) >= max([dt(meta['captured_at'])] + [dt(m['source']['captured_at']) for m in proved]), 'explicit verification and capture ordering')
            require(dt(fact['first_observed_at']) > dt(baseline['data_cutoff']) and registry.fact(key, 'attribute:training_country_matches', baseline['data_cutoff'])['status'] == 'NOT_FOUND'
                    and review['writer_added'] == 1 and review['repeated_save_added'] == 0, 'old cutoff and idempotency')
            counts['registered' if selected else 'latest_date_unresolved' if countries else 'searched_without_country'] += 1
            reviews.append(review)
    require([r['horse_key'] for r in reviews] == [r['horse_key'] for r in queue[:len(reviews)]], 'continuous reviewed prefix')
    require(progress['remaining_priority_queue'] == queue[len(reviews):] and progress['counts'] == dict(reviewed=len(reviews), unsearched=511-len(reviews), **counts), 'resume/counts exact')
    inventory = read(root / baseline['source_inventory_path'])
    by_key = {r['horse_key']: r for r in reviews}
    for row in inventory['subjects']:
        if row['horse_key'] in by_key:
            r = by_key[row['horse_key']]
            require(row['status'] == r['status'] and row['training_country'] == r['selected_country'], 'latest inventory matches reviews')
    require(inventory['scope_count']['registered_sire_damsire'] == 102 + counts['registered']
            and inventory['scope_count']['unsearched'] == 511-len(reviews), 'latest inventory totals')
    return progress['counts']


if __name__ == '__main__':
    print(json.dumps(check(), ensure_ascii=False, sort_keys=True))
