#!/usr/bin/env python3
"""チャットで実際に閲覧した非価格本文を独立sidecarへ保存する。"""
import argparse
import copy
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from check_prediction_compliance import iso
from cycle04_operations import fingerprint, positive_set, require, safe_path
from cycle04_workflow import check_working_branch

REQUEST_SCHEMA = 'chat-fact-request-v1'
CAPTURE_SCHEMA = 'chat-fact-capture-v1'


def request(data):
    require(isinstance(data, dict) and data.get('schema_version') == REQUEST_SCHEMA,
            'explicit fact request required')
    for key in ('request_id', 'race_id', 'race_date_jst'):
        require(isinstance(data.get(key), str) and data[key].strip(), key + ' required')
    post = iso(data.get('scheduled_post_time_jst'), 'post')
    cutoff = iso(data.get('data_cutoff'), 'cutoff')
    require(post.astimezone(timezone.utc).tzinfo is not None, 'post timezone required')
    require(post.date().isoformat() == data['race_date_jst'] and
            post.utcoffset().total_seconds() == 32400, 'post must match JST race date')
    require(re.fullmatch(data['race_date_jst'].replace('-', '') + r'-[A-Z]{3}-\d{2}',
                         data['race_id']), 'request race/date mismatch')
    require(data.get('purpose') in {'INPUT', 'RESULT'}, 'input/result purpose required')
    require(cutoff < post if data['purpose'] == 'INPUT' else cutoff >= post,
            'purpose cutoff mismatch')
    positive_set(data.get('horse_numbers'), 'all-horse request scope')
    items = data.get('required_items')
    require(isinstance(items, list) and items and all(isinstance(x, str) and x.strip() for x in items)
            and len(set(items)) == len(items), 'unique required items needed')
    return copy.deepcopy(data)


def normalize(req, captures, now=None):
    req = request(req)
    require(isinstance(captures, list), 'capture list required')
    current = now or datetime.now(timezone.utc)
    require(current.tzinfo is not None, 'recording timezone required')
    records, seen = [], set()
    cutoff = iso(req['data_cutoff'], 'cutoff')
    post = iso(req['scheduled_post_time_jst'], 'post')
    for original in captures:
        require(isinstance(original, dict), 'capture object required')
        c = copy.deepcopy(original)
        ident = c.get('capture_id')
        require(isinstance(ident, str) and ident.strip() and ident not in seen,
                'unique capture ID required')
        seen.add(ident)
        url = urlsplit(c.get('source_url', ''))
        require(url.scheme == 'https' and url.hostname and not url.username and not url.password,
                'public HTTPS source URL required')
        require(c.get('provider') in {'OFFICIAL', 'FALLBACK'} and
                isinstance(c.get('origin_group'), str) and c['origin_group'].strip(),
                'provider and upstream origin group required')
        if c['provider'] == 'OFFICIAL':
            require(url.hostname in {'jra.go.jp', 'jra.jp'} or
                    url.hostname.endswith('.jra.go.jp') or url.hostname.endswith('.jra.jp'),
                    'official fact source must be JRA')
        require(c.get('mode') in {'FORWARD', 'REPLAY', 'SYNTHETIC'}, 'capture mode required')
        require(c.get('retrieval_kind') in {'PAGE_TEXT', 'SEARCH_SNIPPET', 'ERROR', 'NOT_ATTEMPTED',
                                             'SYNTHETIC_PAGE_TEXT'}, 'retrieval kind required')
        require(isinstance(c.get('reason'), str) and c['reason'].strip(), 'capture reason required')
        require(c.get('raw_http_sha256') is None and c.get('http_status') is None,
                'this recorder stores tool text, not HTTP original bytes/status')
        text = c.get('text')
        require(isinstance(text, str) and len(text.encode('utf-8')) <= 131072,
                'bounded UTF-8 capture text required')
        kind = c['retrieval_kind']
        require(bool(text.strip()) if kind in {'PAGE_TEXT', 'SEARCH_SNIPPET', 'SYNTHETIC_PAGE_TEXT'}
                else not text, 'capture text contradicts retrieval kind')
        if kind == 'NOT_ATTEMPTED':
            require(c.get('read_started_at_jst') is None and c.get('read_finished_at_jst') is None,
                    'not attempted cannot have retrieval times')
            started = finished = observed = None
        else:
            started = iso(c.get('read_started_at_jst'), 'read start')
            finished = iso(c.get('read_finished_at_jst'), 'read finish')
            observed = iso(c['source_updated_at_jst'], 'source time') if c.get('source_updated_at_jst') else None
            require(started <= finished <= current and (observed is None or observed <= finished),
                    'future or reversed retrieval times')
        require(kind != 'SYNTHETIC_PAGE_TEXT' or c['mode'] == 'SYNTHETIC',
                'synthetic text cannot be a live observation')
        usable = (c['mode'] == 'FORWARD' and kind == 'PAGE_TEXT' and observed is not None
                  and finished <= cutoff and (finished < post if req['purpose'] == 'INPUT' else started >= post))
        c.update(text_sha256=fingerprint(text.encode('utf-8')), raw_http_sha256=None,
                 http_status=None, usable_as_observed_fact=bool(usable))
        records.append(c)
    groups = sorted({c['origin_group'] for c in records if c['usable_as_observed_fact']})
    return {'schema_version': CAPTURE_SCHEMA, 'request': req, 'captures': records,
            'recorded_at': current.isoformat(), 'independent_origin_groups': groups,
            'formal_kpi_certified': False, 'git_persistence_verified': False}


def verify(data):
    require(isinstance(data, dict) and data.get('schema_version') == CAPTURE_SCHEMA,
            'capture sidecar schema required')
    expected = normalize(data['request'], data['captures'], iso(data['recorded_at'], 'recorded at'))
    require(data == expected, 'capture text/hash/state mismatch')
    return data


def save(root, relative, data):
    data = verify(data)
    date = data['request']['race_date_jst']
    check_working_branch(root, date)
    require(relative.startswith('docs/validation/fact-captures/' + date + '/') and
            relative.endswith('.json'), 'independent daily capture path required')
    path = safe_path(root, relative)
    raw = (json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = path.with_suffix('.lock')
    handle = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    staged = None
    try:
        os.close(handle)
        if path.exists():
            require(path.read_bytes() == raw, 'immutable capture differs; use new revision')
        else:
            with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.capture-', delete=False) as stream:
                staged = Path(stream.name)
                stream.write(raw); stream.flush(); os.fsync(stream.fileno())
            require(staged.read_bytes() == raw, 'staged capture readback mismatch')
            # link is atomic and cannot overwrite another writer's artifact.
            os.link(staged, path)
        require(path.read_bytes() == raw, 'capture readback mismatch')
    finally:
        if staged is not None: staged.unlink(missing_ok=True)
        lock.unlink(missing_ok=True)
    return {'artifact_path': relative, 'sha256': fingerprint(raw),
            'local_readback_matches': True, 'git_persistence_verified': False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request', type=Path, required=True)
    parser.add_argument('--captures', type=Path, required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    try:
        result = save(args.root, args.output, normalize(json.loads(args.request.read_text()),
                                                       json.loads(args.captures.read_text())))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print('取得本文の保存未完了：' + str(exc))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
