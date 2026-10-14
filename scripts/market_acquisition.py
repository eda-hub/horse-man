#!/usr/bin/env python3
"""任意市場の2経路HTTP取得。原応答・全試行を保存し、価格判断は行わない。"""
import argparse
import copy
import hashlib
import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from check_prediction_compliance import iso
from cycle04_operations import BET_TYPES, require, safe_path, validate_market_payload

TRANSPORT = 'market-http-acquisition-v1'
PROVIDER_TRANSPORT = 'market-provider-acquisition-v1'
MAX_BYTES = 131072


def ticket_key(ticket):
    require(isinstance(ticket, dict) and ticket.get('type') in BET_TYPES, 'market ticket required')
    kind = ticket['type']; field = 'frames' if kind == 'BRACKET_QUINELLA' else 'horses'
    values = ticket.get(field)
    require(isinstance(values, list) and len(values) == BET_TYPES[kind] and
            all(type(v) is int and v > 0 for v in values), 'invalid market ticket values')
    require((kind == 'BRACKET_QUINELLA' and all(v <= 8 for v in values)) or
            (kind != 'BRACKET_QUINELLA' and len(set(values)) == len(values)),
            'duplicate horse or invalid frame')
    return kind, tuple(values if kind in {'EXACTA', 'TRIFECTA'} else sorted(values))


def validate_request(request):
    require(isinstance(request, dict) and request.get('schema_version') == 'market-price-request-v1',
            'market price request schema required')
    require(request.get('mode') in {'FORWARD', 'SYNTHETIC'}, 'explicit acquisition mode required')
    date = request.get('race_date_jst')
    require(isinstance(date, str) and isinstance(request.get('race_id'), str)
            and request['race_id'].startswith(date.replace('-', '') + '-'), 'market race/date mismatch')
    day = iso(date+'T00:00:00+09:00', 'market race date')
    ticket_key(request.get('ticket'))
    deadline = iso(request.get('deadline_at_jst'), 'acquisition deadline')
    cutoff = iso(request.get('data_cutoff'), 'acquisition cutoff')
    post = iso(request.get('scheduled_post_time_jst'), 'acquisition post')
    require(post.astimezone(day.tzinfo).date() == day.date(), 'market post date mismatch')
    require(deadline <= cutoff < post, 'market deadline/cutoff/post mismatch')
    routes = request.get('routes')
    require(isinstance(routes, list) and len(routes) == 2, 'primary and fallback routes required')
    urls = []
    for route in routes:
        require(isinstance(route, dict), 'route object required')
        require(route.get('provider') in {None,'HTTP_JSON','JV_LINK'}, 'unknown market provider')
        url = route.get('source_url')
        require(isinstance(url, str), 'route source URL required')
        parsed = urlparse(url)
        native = route.get('provider') == 'JV_LINK'
        if native:
            from jvlink_market import address
            address(url, request)
        require(native or parsed.scheme == 'https' or (request['mode'] == 'SYNTHETIC' and
                parsed.scheme == 'http' and parsed.hostname in {'127.0.0.1', 'localhost', '::1'}),
                'HTTPS required; synthetic HTTP is loopback only')
        require(parsed.hostname and parsed.username is None and parsed.password is None and
                not parsed.fragment, 'invalid market source URL')
        require(type(route.get('max_attempts')) is int and 1 <= route['max_attempts'] <= 3,
                'bounded route attempt count required')
        urls.append(url)
    require(len(set(urls)) == 2, 'fallback must be a distinct configured endpoint')
    for name, low, high in [('timeout_seconds', .01, 30), ('retry_delay_seconds', 0, 30)]:
        value = request.get(name)
        require(type(value) in (int, float) and math.isfinite(value) and low <= value <= high,
                'invalid acquisition timing policy')
    return deadline, cutoff, post


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch_http(url, timeout):
    """GETだけ実行。redirectで出所を黙って変更しない。"""
    opener = build_opener(NoRedirect())
    try:
        with opener.open(Request(url, headers={'Accept': 'application/json',
                        'User-Agent': 'horse-man-market/1'}), timeout=timeout) as response:
            raw = response.read(MAX_BYTES + 1)
            return response.status, raw, len(raw) <= MAX_BYTES, None
    except HTTPError as exc:
        with exc:
            raw = exc.read(MAX_BYTES + 1)
            return exc.code, raw, len(raw) <= MAX_BYTES, 'HTTP_ERROR'
    except (URLError, TimeoutError, OSError):
        return None, None, None, 'TRANSPORT_ERROR'


def decode_price(raw, request, acquired_at, provider=None):
    if provider == 'JV_LINK':
        from jvlink_market import normalize
        return normalize(raw, request, acquired_at)
    data = json.loads(raw)
    require(isinstance(data, dict) and data.get('schema_version') == 'market-price-response-v1'
            and data.get('race_id') == request['race_id']
            and ticket_key(data.get('ticket')) == ticket_key(request['ticket']),
            'response race/ticket/schema mismatch')
    observed = iso(data.get('observed_at_jst'), 'response observed')
    require(observed <= acquired_at and observed <= iso(request['data_cutoff'], 'request cutoff')
            and observed <= iso(request['deadline_at_jst'], 'request deadline'), 'future observed price')
    odds = data.get('odds')
    require(type(odds) in (int, float) and math.isfinite(odds) and odds > 0, 'invalid observed odds')
    return data


def collect(request, evidence_dir, *, fetch=None,
            now=lambda: datetime.now(timezone.utc), sleep=time.sleep):
    deadline, cutoff, post = validate_request(request)
    request = copy.deepcopy(request)
    require(not Path(evidence_dir).is_absolute() and '..' not in Path(evidence_dir).parts,
            'relative response evidence directory required')
    marker = PROVIDER_TRANSPORT if any(r.get('provider') == 'JV_LINK' for r in request['routes']) else TRANSPORT
    history = {'schema_version': 'market-acquisition-v1', 'transport_schema': marker,
               'request': request, 'attempts': [], 'deadline_at_jst': request['deadline_at_jst'],
               'stopped_at_jst': None}
    market = {'status': 'NOT_ATTEMPTED', 'decision': 'NOT_EVALUATED', 'reason': '取得未試行',
              'odds': None, 'expected_value': None, 'attempted_at_jst': None,
              'acquired_at_jst': None, 'source_ref': None, 'acquisition': history}
    responses = {}
    stopped = False
    last = now()
    require(last < post, 'acquisition cannot start at/after post')
    for route in request['routes']:
        for route_attempt in range(route['max_attempts']):
            start = now()
            if start >= deadline:
                stopped = True; last = start; break
            timeout = min(request['timeout_seconds'], (deadline - start).total_seconds())
            native = route.get('provider') == 'JV_LINK'
            if fetch is None and native:
                from jvlink_market import fetch as transport
            else:
                transport = fetch or fetch_http
            status, raw, complete, error = transport(route['source_url'], timeout)
            finish = now(); last = finish
            require(start <= finish, 'acquisition clock moved backwards')
            ref = None
            if raw is not None:
                require(isinstance(raw, bytes), 'raw response bytes required')
                sha = hashlib.sha256(raw).hexdigest()
                path = (Path(evidence_dir)/'responses'/(sha+'.bin')).as_posix()
                responses[path] = raw
                ref = {'artifact_path': path, 'sha256': sha, 'bytes': len(raw), 'complete': complete}
            data = None
            if finish >= deadline:
                error = 'DEADLINE_EXCEEDED'; stopped = True
            elif complete is not True:
                error = error or 'INCOMPLETE_RESPONSE'
            elif type(status) is not int or not (status == 0 if native else 200 <= status < 300):
                error = error or ('JV_ERROR' if native else 'HTTP_ERROR')
            elif error is None:
                try:
                    data = decode_price(raw, request, finish, route.get('provider'))
                except (ValueError, KeyError, TypeError, UnicodeError):
                    error = 'INVALID_RESPONSE'
            attempt = {'attempt_no': len(history['attempts'])+1, 'source_ref': route['source_url'],
                       'started_at_jst': start.isoformat(), 'finished_at_jst': finish.isoformat(),
                       'result': 'ACQUIRED' if data is not None else 'FAILED',
                       'reason': '取得応答を照合済み' if data is not None else '価格取得失敗：'+str(error),
                       'observed_at_jst': data['observed_at_jst'] if data is not None else None,
                       'http_status': None if native else status,
                       'response_ref': ref, 'error_code': error}
            if native:
                attempt.update(provider='JV_LINK',jv_status=status)
            history['attempts'].append(attempt)
            if market['attempted_at_jst'] is None:
                market['attempted_at_jst'] = attempt['started_at_jst']
            if data is not None:
                market.update(status='ACQUIRED', reason='独立価格取得済み・期待値は未評価',
                              odds=data['odds'], source_ref=route['source_url'],
                              acquired_at_jst=attempt['finished_at_jst'])
                if 'price_details' in data:
                    market['price_details'] = data['price_details']
                break
            if stopped: break
            if route_attempt+1 < route['max_attempts']:
                remaining = (deadline-now()).total_seconds()
                if remaining <= request['retry_delay_seconds']:
                    sleep(max(0, remaining)); stopped = True; last = now(); break
                sleep(request['retry_delay_seconds'])
        if stopped or market['status'] == 'ACQUIRED': break
    if market['status'] != 'ACQUIRED':
        market['status'] = 'DEADLINE_STOPPED' if stopped else 'FAILED'
        market['reason'] = '締切により取得停止・購入判断は未完了' if stopped else '2経路の取得失敗・購入判断は未完了'
        if stopped: history['stopped_at_jst'] = last.isoformat()
    payload = {'schema_version': 'market-analysis-v2', 'mode': request['mode'],
               'race_id': request['race_id'], 'race_date_jst': request['race_date_jst'],
               'ticket': request['ticket'], 'data_cutoff': max(cutoff, last).isoformat(),
               'market': market}
    validate_market_payload(payload, payload['data_cutoff'])
    return payload, responses


def verify_responses(root, payload, *, require_forward=True):
    """保存原本から価格と固定race/券を再照合。自己申告hashだけでは受理しない。"""
    validate_market_payload(payload, payload['data_cutoff'])
    history = payload['market'].get('acquisition', {})
    if history.get('transport_schema') == 'market-chat-acquisition-v1':
        from chat_market_acquisition import verify
        return verify(root, payload, require_forward=require_forward)
    if history.get('transport_schema') not in {TRANSPORT, PROVIDER_TRANSPORT}:
        require('transport_schema' not in history and 'request' not in history and
                all('response_ref' not in a for a in history.get('attempts', [])),
                'HTTP acquisition metadata cannot omit transport schema')
        return
    request = history.get('request')
    deadline, _, _ = validate_request(request)
    require(not require_forward or payload.get('mode') == request['mode'] == 'FORWARD',
            'synthetic acquisition cannot certify live market')
    require(payload.get('mode') == request['mode'] and payload.get('race_id') == request['race_id']
            and payload.get('race_date_jst') == request['race_date_jst']
            and ticket_key(payload.get('ticket')) == ticket_key(request['ticket'])
            and history.get('deadline_at_jst') == request['deadline_at_jst'],
            'acquisition request/output mismatch')
    routes = [r['source_url'] for r in request['routes']]
    route_index = 0; counts = [0, 0]
    previous_attempt = None
    for attempt in history['attempts']:
        require(iso(attempt['started_at_jst'], 'request start') < deadline,
                'HTTP request started after deadline')
        source = attempt['source_ref']
        require(source in routes, 'unconfigured response source')
        index = routes.index(source)
        route = request['routes'][index]
        native = route.get('provider') == 'JV_LINK'
        require(not native or attempt.get('provider') == 'JV_LINK' and attempt.get('http_status') is None,
                'JV acquisition cannot claim HTTP status')
        status = attempt.get('jv_status') if native else attempt.get('http_status')
        require(index >= route_index, 'primary route resumed after fallback')
        if previous_attempt is not None and index == route_index:
            require((iso(attempt['started_at_jst'], 'retry start') -
                     iso(previous_attempt['finished_at_jst'], 'retry previous finish')).total_seconds()
                    >= request['retry_delay_seconds'], 'retry delay shorter than configured policy')
        if index > route_index:
            require(counts[0] == request['routes'][0]['max_attempts'], 'fallback before primary exhaustion')
        route_index = index; counts[index] += 1
        previous_attempt = attempt
        require(counts[index] <= request['routes'][index]['max_attempts'], 'response attempt count exceeded')
        ref = attempt.get('response_ref')
        if ref is None:
            require(attempt['result'] == 'FAILED' and attempt.get('http_status') is None
                    and attempt.get('error_code') in {'TRANSPORT_ERROR', 'DEADLINE_EXCEEDED',
                                                     'JV_UNAVAILABLE','JV_ERROR','JV_READ_LIMIT'},
                    'missing raw response is not acquisition success')
            require(native or attempt.get('error_code') in {'TRANSPORT_ERROR','DEADLINE_EXCEEDED'},
                    'HTTP route cannot claim native failure')
            if attempt.get('error_code') == 'JV_ERROR':
                require(type(status) is int and status != 0, 'false JV error')
            if attempt['error_code'] == 'DEADLINE_EXCEEDED':
                require(iso(attempt['finished_at_jst'], 'late transport finish') >= deadline and
                        payload['market']['status'] == 'DEADLINE_STOPPED', 'false deadline failure')
            continue
        raw = safe_path(root, ref.get('artifact_path')).read_bytes()
        require(hashlib.sha256(raw).hexdigest() == ref.get('sha256') and len(raw) == ref.get('bytes'),
                'market raw response hash/size mismatch')
        require(type(ref.get('complete')) is bool and
                (type(status) is int or native and attempt.get('error_code') == 'JV_READ_LIMIT'),
                'response completeness/status required')
        require(len(raw) <= MAX_BYTES if ref['complete'] else len(raw) == MAX_BYTES+1,
                'bounded response capture size mismatch')
        if attempt['result'] == 'ACQUIRED':
            require(ref['complete'] and (status == 0 if native else 200 <= status < 300)
                    and attempt.get('error_code') is None
                    and iso(attempt['finished_at_jst'], 'response finish') < deadline,
                    'invalid acquired HTTP response')
            data = decode_price(raw, request, iso(attempt['finished_at_jst'], 'response finish'),
                                route.get('provider'))
            require(data['odds'] == payload['market']['odds'] and
                    data['observed_at_jst'] == attempt['observed_at_jst'],
                    'raw response does not match acquired price')
            require(data.get('price_details') == payload['market'].get('price_details'),
                    'raw price details mismatch')
        else:
            error = attempt.get('error_code')
            if error == 'HTTP_ERROR':
                require(not native and not 200 <= status < 300, 'false HTTP failure')
            elif error == 'JV_ERROR':
                require(native and status != 0, 'false JV failure')
            elif error == 'JV_READ_LIMIT':
                require(native and status is None, 'false JV read limit')
            elif error == 'INCOMPLETE_RESPONSE':
                require(not ref['complete'], 'false incomplete response')
            elif error == 'INVALID_RESPONSE':
                require(ref['complete'] and (status == 0 if native else 200 <= status < 300),
                        'invalid response diagnostic mismatch')
                invalid = False
                try:
                    decode_price(raw, request, iso(attempt['finished_at_jst'], 'failed response finish'),
                                 route.get('provider'))
                except (ValueError, KeyError, TypeError, UnicodeError):
                    invalid = True
                require(invalid, 'valid response cannot be declared invalid')
            elif error == 'DEADLINE_EXCEEDED':
                require(iso(attempt['finished_at_jst'], 'late finish') >= deadline and
                        payload['market']['status'] == 'DEADLINE_STOPPED', 'false deadline failure')
            else:
                require(False, 'unknown raw HTTP failure diagnostic')
    if payload['market']['status'] == 'FAILED':
        require(counts == [r['max_attempts'] for r in request['routes']],
                'failed acquisition must exhaust both configured routes')


def save(root, directory, payload, responses):
    """専用新規runフォルダへ原応答→分析を追記保存。既存予想・台帳を操作しない。"""
    folder = safe_path(root, directory); folder.mkdir(parents=True, exist_ok=False)
    for relative, raw in responses.items():
        path = safe_path(root, relative)
        require(path.is_relative_to(folder), 'response outside acquisition run')
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream: stream.write(raw)
        require(path.read_bytes() == raw, 'response readback mismatch')
    verify_responses(root, payload, require_forward=False)
    path = folder/'analysis.json'
    raw = (json.dumps(payload, ensure_ascii=False, indent=2)+'\n').encode()
    with path.open('xb') as stream: stream.write(raw)
    require(path.read_bytes() == raw, 'analysis readback mismatch')
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request', type=Path, required=True)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--evidence-dir', required=True)
    parser.add_argument('--jvlink', action='store_true', help='official whole-ticket and ticket-specific routes')
    parser.add_argument('--alternate-first', action='store_true', help='probe the ticket-specific route first')
    args = parser.parse_args(argv)
    try:
        request = json.loads(args.request.read_text())
        require(not args.alternate_first or args.jvlink, 'alternate-first requires the JV-Link provider')
        if args.jvlink:
            from jvlink_market import routes_for
            request['routes'] = routes_for(request, args.alternate_first)
        payload, responses = collect(request, args.evidence_dir)
        path = save(args.root, args.evidence_dir, payload, responses)
        print(payload['market']['reason']+'。原応答・分析の保存読戻し：'+str(path))
        print('独立receipt・日次市場登録は別途必要。予想・推奨と期待値を認証しません。')
        return 0 if payload['market']['status'] == 'ACQUIRED' else 1
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print('任意価格取得を完了できません：'+str(exc))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
