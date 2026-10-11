"""Validate fixed-plan provenance independently of Git receipt quality."""
import hashlib
import json
import re
from pathlib import Path

CONTRACT = 'betting-kpi-split-v1'
SOURCE_TYPES = {'GIT_PRE_RACE_SNAPSHOT', 'CHAT_PRE_RACE_FIXED'}


def tickets_hash(tickets):
    return hashlib.sha256(json.dumps(tickets, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=False).encode()).hexdigest()


def local_path(root, relative):
    if not isinstance(relative, str) or not relative:
        raise ValueError('source path required')
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError('source path escapes repository')
    return path


def snapshot_tickets(root, relative, snapshot_id):
    text = local_path(root, relative).read_text(encoding='utf-8')
    sections = re.split(r'(?=^##\s+)', text, flags=re.M)
    matches = [s for s in sections if re.search(
        r'^snapshot_id:\s*' + re.escape(snapshot_id) + r'\s*$', s, re.M)]
    if len(matches) != 1:
        raise ValueError('expected exactly one fixed snapshot')
    kinds = {'単勝': 'WIN', '複勝': 'PLACE', '馬連': 'QUINELLA',
             'ワイド': 'WIDE', '馬単': 'EXACTA', '三連複': 'TRIO', '三連単': 'TRIFECTA'}
    tickets = []
    for kind, horses, amount in re.findall(
        r'^\|\s*(単勝|複勝|馬連|ワイド|馬単|三連複|三連単)\s*\|\s*([\d-]+)\s*\|\s*([\d,]+)円\s*\|',
        matches[0], re.M):
        tickets.append({'type': kinds[kind], 'horses': [int(x) for x in horses.split('-')],
                        'stake_yen': int(amount.replace(',', ''))})
    if not tickets:
        virtual = re.search(
            r'^###\s+検証用仮想購入（正式帳簿）\s*$\n(.*?)(?=^###\s|\Z)',
            matches[0], re.M | re.S)
        if virtual:
            for kind, horses, amount in re.findall(
                    r'^-\s*(単勝|複勝|馬連|ワイド|馬単|3連複|三連複|3連単|三連単)\s+([\d-]+)\s*[:：]\s*([\d,]+)円\s*$',
                    virtual.group(1), re.M):
                normalized = {'3連複': '三連複', '3連単': '三連単'}.get(kind, kind)
                tickets.append({'type': kinds[normalized],
                                'horses': [int(x) for x in horses.split('-')],
                                'stake_yen': int(amount.replace(',', ''))})
    if not tickets:
        # Modern FIXED snapshots place amount in the final table column and may
        # use circled horse numbers or a leading strategy category. Only read
        # the explicitly titled pre-race virtual-ticket section; a market
        # comparison table must never become a fixed ticket after the event.
        symbols = {ord(char): str(index) for index, char in enumerate(
            '①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳', 1)}
        sections = re.split(r'(?=^###\\s+)', matches[0], flags=re.M)
        for subsection in sections:
            header = subsection.splitlines()[0] if subsection else ''
            if not re.match(r'^###\\s+.*(?:仮想|買い目FIX)', header):
                continue
            for line in subsection.splitlines():
                if not line.startswith('|'):
                    continue
                cells = [cell.strip() for cell in line.split('|')[1:-1]]
                if len(cells) < 4:
                    continue
                offset = 0 if cells[0] in kinds else 1
                if len(cells) <= offset + 2 or cells[offset] not in kinds:
                    continue
                kind, horses = cells[offset:offset + 2]
                amount = cells[-1]
                if not re.fullmatch(r'[0-9,]+円', amount):
                    continue
                horses = horses.translate(symbols).replace('－', '-')
                if not re.fullmatch(r'[0-9]+(?:-[0-9]+)*', horses):
                    continue
                number_list = [int(n) for n in horses.split('-')]
                if len(set(number_list)) != len(number_list):
                    raise ValueError('duplicate horse in fixed ticket')
                tickets.append({'type': kinds[kind], 'horses': number_list,
                                'stake_yen': int(amount[:-1].replace(',', ''))})
    if not tickets:
        raise ValueError('fixed tickets missing')
    return tickets


def validate_source(root, ref, race_id):
    from check_prediction_compliance import iso
    if ref.get('source_type') not in SOURCE_TYPES:
        raise ValueError('unknown performance source type')
    path = local_path(root, ref.get('source_path'))
    source = json.loads(path.read_text(encoding='utf-8'))
    if source.get('schema_version') != 'fixed-plan-source-v1':
        raise ValueError('fixed-plan source schema mismatch')
    for key in ('source_type', 'source_ref', 'working_branch'):
        if source.get(key) != ref.get(key):
            raise ValueError(f'performance source {key} mismatch')
    if source.get('race_id') != race_id or source.get('verification_status') != 'VERIFIED':
        raise ValueError('performance source not verified for race')
    fixed = iso(source.get('source_sent_at_jst'), 'source sent time')
    post = iso(source.get('scheduled_post_time_jst'), 'scheduled post time')
    result = iso(source.get('result_checked_at_jst'), 'result checked time')
    if fixed >= post or fixed >= result:
        raise ValueError('source was not fixed before race and result')
    location = source.get('source_ref', '')
    if source['source_type'] == 'GIT_PRE_RACE_SNAPSHOT':
        if not re.fullmatch(r'https://github\.com/eda-hub/horse-man/blob/[0-9a-f]{40}/[^\s]+', location):
            raise ValueError('immutable Git source reference required')
    elif not re.fullmatch(r'https://chatgpt\.com/[^\s]+', location) or not source.get('message_id'):
        raise ValueError('chat conversation and message reference required')
    raw = local_path(root, source.get('original_path')).read_bytes()
    if hashlib.sha256(raw).hexdigest() != source.get('original_sha256'):
        raise ValueError('original source hash mismatch')
    original = json.loads(raw)
    if original.get('race_id') != race_id or original.get('source_sent_at_jst') != source.get('source_sent_at_jst'):
        raise ValueError('original source race/time mismatch')
    tickets = snapshot_tickets(root, source.get('snapshot_path'), source.get('snapshot_id', ''))
    if original.get('tickets') != tickets or tickets_hash(tickets) != source.get('tickets_sha256'):
        raise ValueError('original and preserved tickets differ')
    if not source.get('verified_by') or not source.get('verification_note'):
        raise ValueError('source verification attribution required')
    return source
