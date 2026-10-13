"""第4サイクルの入力・市場・用途・保存契約。履歴を作らず読取検査する。"""
import hashlib
import json
import math
from pathlib import Path

from check_prediction_compliance import ComplianceError, iso, receipt_records
from selection_history import validate_history

INPUT_SCHEMA = 'race-input-coverage-v1'
MARKET_STATES = {'NOT_ATTEMPTED', 'FAILED', 'DEADLINE_STOPPED', 'ACQUIRED'}
BET_TYPES = {'WIN': 1, 'PLACE': 1, 'QUINELLA': 2, 'WIDE': 2,
             'EXACTA': 2, 'TRIO': 3, 'TRIFECTA': 3, 'BRACKET_QUINELLA': 2}


def require(ok, message):
    if not ok:
        raise ComplianceError(message)


def safe_path(root, relative):
    require(isinstance(relative, str) and bool(relative), 'artifact path required')
    p = Path(relative)
    require(not p.is_absolute() and '..' not in p.parts, 'invalid artifact path')
    full = (Path(root) / p).resolve()
    require(full.is_relative_to(Path(root).resolve()), 'artifact escapes repository')
    return full


def fingerprint(raw):
    return hashlib.sha256(raw).hexdigest()


def verified_artifact(root, ref, post, *, expected_id=None):
    require(isinstance(ref, dict), 'independent artifact reference required')
    path = safe_path(root, ref.get('artifact_path'))
    raw = path.read_bytes()
    require(fingerprint(raw) == ref.get('sha256'), 'artifact hash mismatch')
    records = receipt_records(safe_path(root, ref.get('receipt_path')))
    matches = [r for r in records if r.get('receipt_id') == ref.get('receipt_id')]
    require(len(matches) == 1, 'exactly one artifact receipt required')
    r = matches[0]
    ident = expected_id or ref.get('artifact_id')
    require(isinstance(ident, str) and ident and ref.get('artifact_id') == ident,
            'artifact identity required')
    require(r.get('artifact_id') == ident and r.get('artifact_path') == ref['artifact_path']
            and r.get('content_sha256') == ref['sha256'], 'receipt identity/hash mismatch')
    require(r.get('artifact_persist_status') == 'PERSIST_VERIFIED'
            and r.get('receipt_persist_status') == 'RECEIPT_VERIFIED'
            and r.get('timing_eligibility') == 'PRE_RACE_ELIGIBLE', 'unverified artifact receipt')
    limit = iso(post, 'post')
    require(iso(r.get('scheduled_post_time_jst'), 'receipt post') == limit,
            'artifact receipt deadline mismatch')
    require(iso(r.get('persist_verified_at_jst'), 'persist') <=
            iso(r.get('receipt_verified_at_jst'), 'readback') < limit, 'late/reversed receipt')
    return json.loads(raw), r


def positive_set(values, label):
    require(isinstance(values, list) and values and
            all(type(x) is int and x > 0 for x in values) and len(set(values)) == len(values),
            label + ': unique positive horse numbers required')
    return set(values)


def validate_inputs(data, *, race_id, horses, cutoff, post):
    require(isinstance(data, dict) and data.get('schema_version') == INPUT_SCHEMA,
            'explicit input coverage schema required')
    require(data.get('race_id') == race_id and data.get('data_cutoff') == cutoff,
            'input race/cutoff mismatch')
    expected = positive_set(horses, 'scope')
    require(positive_set(data.get('horse_numbers'), 'input scope') == expected, 'input scope mismatch')
    limit = iso(cutoff, 'cutoff')
    require(limit < iso(post, 'post'), 'input cutoff at/after post')
    result = {}
    opponent_missing = set()
    for field in ('body_weight', 'recent_five_runs'):
        rows = data.get(field)
        require(isinstance(rows, list) and len(rows) == len(expected), field + ': all-horse rows required')
        require({r.get('horse_no') for r in rows} == expected and
                len({r.get('horse_no') for r in rows}) == len(rows), field + ': duplicate/missing horse')
        missing = []
        for row in rows:
            state = row.get('status')
            require(state in {'ACQUIRED', 'MISSING', 'NOT_APPLICABLE'}, field + ': unknown input state')
            require(isinstance(row.get('reason'), str) and row['reason'].strip(), field + ': reason required')
            if state != 'ACQUIRED':
                require(row.get('value') is None, field + ': unavailable value must be null')
                require(state != 'NOT_APPLICABLE' or field == 'recent_five_runs',
                        'body weight cannot be silently treated as not applicable')
                if state == 'NOT_APPLICABLE':
                    require(row.get('prior_start_count') == 0 and row.get('source_ref'),
                            'debut status requires a source and zero prior starts')
                else:
                    missing.append(row['horse_no'])
                continue
            require(row.get('source_ref') and row.get('provider') in {'OFFICIAL', 'FALLBACK'},
                    field + ': input source required')
            observed = iso(row.get('observed_at_jst'), 'observed')
            acquired = iso(row.get('acquired_at_jst'), 'acquired')
            readback = iso(row.get('readback_at_jst'), 'input readback')
            require(observed <= acquired <= readback <= limit, field + ': future/reversed input')
            if row['provider'] == 'FALLBACK':
                require(row.get('official_attempt_reason'), 'fallback must record official acquisition failure')
            if field == 'body_weight':
                require(type(row.get('value')) is int and row['value'] > 0, 'missing weight cannot become zero')
            else:
                runs = row.get('value')
                count = row.get('prior_start_count')
                require(type(count) is int and count > 0 and isinstance(runs, list)
                        and len(runs) == min(5, count), 'recent runs must cover available last five')
                dates = [iso(r.get('race_at_jst'), 'run date') for r in runs]
                require(dates == sorted(set(dates), reverse=True) and all(t <= limit for t in dates),
                        'recent runs contain duplicate/future/out-of-order races')
                require(all(r.get('source_ref') and r.get('class') and r.get('opponent_level')
                            for r in runs), 'recent runs require class/opponent evidence')
                for run in runs:
                    opponent = run['opponent_level']
                    require(isinstance(opponent, dict) and opponent.get('status') in {'ACQUIRED', 'MISSING'},
                            'opponent level requires explicit acquired/missing status')
                    if opponent['status'] == 'MISSING':
                        require(opponent.get('value') is None and opponent.get('reason'),
                                'missing opponent level must remain null with reason')
                        opponent_missing.add(row['horse_no'])
                    else:
                        require(opponent.get('value') is not None and opponent.get('source_ref') and
                                iso(opponent.get('observed_at_jst'), 'opponent information time') <= limit,
                                'opponent level uses future or unverified information')
        result[field] = {'target_count': len(expected), 'missing_horses': missing,
                         'acquired_count': sum(r['status'] == 'ACQUIRED' for r in rows)}
    result['opponent_level_missing_horses'] = sorted(opponent_missing)
    result['complete'] = (not any(result[f]['missing_horses'] for f in ('body_weight', 'recent_five_runs'))
                          and not opponent_missing)
    return result


def validate_market(market, cutoff):
    require(isinstance(market, dict) and market.get('status') in MARKET_STATES, 'explicit market state required')
    state, decision = market['status'], market.get('decision')
    require(decision in {'NOT_EVALUATED', 'POSITIVE_EV', 'INSUFFICIENT_EV'}, 'explicit market decision required')
    require(isinstance(market.get('reason'), str) and market['reason'].strip(), 'market reason required')
    if state != 'ACQUIRED':
        require(decision == 'NOT_EVALUATED' and market.get('odds') is None
                and market.get('expected_value') is None, 'missing price is not insufficient expected value')
        if state == 'NOT_ATTEMPTED':
            require(market.get('attempted_at_jst') is None, 'unattempted market cannot have attempt time')
        else:
            history = market.get('acquisition')
            empty_stop = (state == 'DEADLINE_STOPPED' and isinstance(history, dict)
                          and history.get('attempts') == [] and market.get('attempted_at_jst') is None)
            require(empty_stop or iso(market.get('attempted_at_jst'), 'market attempt') <= iso(cutoff, 'cutoff'),
                    'future market attempt')
    else:
        require(iso(market.get('attempted_at_jst'), 'market attempt') <=
                iso(market.get('acquired_at_jst'), 'market acquired') <= iso(cutoff, 'cutoff'),
                'future/reversed market acquisition')
        odds, ev = market.get('odds'), market.get('expected_value')
        require(type(odds) in (int, float) and math.isfinite(odds) and odds > 0 and
                ((decision == 'NOT_EVALUATED' and ev is None) or
                 (type(ev) in (int, float) and math.isfinite(ev))) and market.get('source_ref'),
                'acquired price/EV/source required')
        require(decision == 'NOT_EVALUATED' or (decision == 'POSITIVE_EV') == (ev > 0),
                'market decision contradicts expected value')
    if 'acquisition' in market:
        validate_market_acquisition(market, cutoff)
    return state


def validate_market_acquisition(market, cutoff):
    """新規任意市場の出所・時点・全試行を検査。旧欠測履歴を補造しない。"""
    history = market.get('acquisition')
    require(isinstance(history, dict) and history.get('schema_version') == 'market-acquisition-v1',
            'market acquisition history required')
    attempts = history.get('attempts')
    require(isinstance(attempts, list), 'market attempt list required')
    limit = iso(cutoff, 'market cutoff')
    deadline_raw = history.get('deadline_at_jst')
    deadline = iso(deadline_raw, 'market deadline') if deadline_raw is not None else None
    previous = None
    for n, attempt in enumerate(attempts, 1):
        require(isinstance(attempt, dict) and type(attempt.get('attempt_no')) is int
                and attempt['attempt_no'] == n, 'market attempt sequence mismatch')
        require(isinstance(attempt.get('source_ref'), str) and attempt['source_ref'].strip()
                and isinstance(attempt.get('reason'), str) and attempt['reason'].strip(),
                'market attempt source/reason required')
        start = iso(attempt.get('started_at_jst'), 'market attempt start')
        finish = iso(attempt.get('finished_at_jst'), 'market attempt finish')
        require(start <= finish <= limit and (previous is None or previous <= start),
                'future/reversed/overlapping market attempts')
        result = attempt.get('result')
        late_failure = (market['status'] == 'DEADLINE_STOPPED' and result == 'FAILED'
                        and history.get('transport_schema') in {'market-http-acquisition-v1','market-provider-acquisition-v1','market-chat-acquisition-v1'}
                        and attempt.get('error_code') == 'DEADLINE_EXCEEDED'
                        and deadline is not None and start < deadline)
        require(deadline is None or finish <= deadline or late_failure, 'market attempt exceeds deadline')
        require(result in {'FAILED', 'ACQUIRED'}, 'market attempt result required')
        require(result != 'ACQUIRED' or n == len(attempts), 'market attempt after acquisition')
        if result == 'ACQUIRED':
            observed = iso(attempt.get('observed_at_jst'), 'market price observed')
            require(observed <= finish, 'market observed after acquisition')
        else:
            require(attempt.get('observed_at_jst') is None, 'failed attempt cannot claim observed price')
        previous = finish
    state = market['status']
    stopped_raw = history.get('stopped_at_jst')
    if state == 'NOT_ATTEMPTED':
        require(not attempts and market.get('attempted_at_jst') is None
                and market.get('acquired_at_jst') is None and market.get('source_ref') is None
                and stopped_raw is None, 'unattempted market has acquisition evidence')
    else:
        empty_stop = state == 'DEADLINE_STOPPED' and not attempts
        require((empty_stop and market.get('attempted_at_jst') is None) or
                (bool(attempts) and market.get('attempted_at_jst') == attempts[0]['started_at_jst']),
                'market first attempt mismatch')
        require((state == 'ACQUIRED') == (bool(attempts) and attempts[-1]['result'] == 'ACQUIRED'),
                'market acquisition status/history mismatch')
        if state == 'ACQUIRED':
            require(market.get('acquired_at_jst') == attempts[-1]['finished_at_jst']
                    and market.get('source_ref') == attempts[-1]['source_ref']
                    and stopped_raw is None, 'market acquired source/time mismatch')
        else:
            require(market.get('acquired_at_jst') is None, 'unacquired market has acquisition time')
        if state == 'DEADLINE_STOPPED':
            stopped = iso(stopped_raw, 'market stopped')
            require(deadline is not None and deadline <= stopped <= limit and
                    (previous is None or previous <= stopped),
                    'market deadline stop time mismatch')
        else:
            require(stopped_raw is None, 'market stop time without deadline stop')
    return history


def validate_market_payload(payload, cutoff):
    require(isinstance(payload, dict) and payload.get('schema_version') in
            {'market-analysis-v1', 'market-analysis-v2'}, 'independent market schema required')
    market = payload.get('market')
    if payload['schema_version'] == 'market-analysis-v2':
        require(isinstance(market, dict) and 'acquisition' in market,
                'v2 market acquisition history required')
    return validate_market(market, cutoff)


def validate_selection(root, history, post_by_race):
    require(history.get('scheduled_posts') == post_by_race, 'selection deadline/scope mismatch')
    result = validate_history(history, root)
    for event in history['events']:
        core = {k: v for k, v in event.items() if k != 'evidence'}
        data, receipt = verified_artifact(root, event['evidence'], post_by_race[event['race_id']])
        require(data == core, 'selection original mismatch')
        require(iso(event['at'], 'event') <= iso(receipt['persist_verified_at_jst'], 'event persistence'),
                'selection persisted before event existed')
    return result


def ticket_event(ticket, *, horses, frames):
    """8券種の事象を検査。枠連同枠は異なる2頭の同時連対事象。"""
    kind = ticket.get('type')
    require(kind in BET_TYPES, 'unknown ticket type')
    values = ticket.get('frames' if kind == 'BRACKET_QUINELLA' else 'horses')
    require(isinstance(values, list) and len(values) == BET_TYPES[kind] and
            all(type(x) is int and x > 0 for x in values), 'wrong ticket arity')
    if kind == 'BRACKET_QUINELLA':
        require(set(frames) == set(horses) and all(type(v) is int and 1 <= v <= 8 for v in frames.values()),
                'complete horse/frame map required')
        require(set(values).issubset(set(frames.values())), 'unknown frame')
        require(values[0] != values[1] or sum(v == values[0] for v in frames.values()) >= 2,
                'same-frame quinella requires two active horses')
        return kind, tuple(sorted(values))
    require(len(set(values)) == len(values) and set(values).issubset(horses),
            'duplicate/cancelled/unknown ticket horse')
    return kind, tuple(values if kind in {'EXACTA', 'TRIFECTA'} else sorted(values))


def validate_ticket_comparison(rows, *, horses, frames):
    require(isinstance(rows, list) and len(rows) == 8 and {r.get('type') for r in rows} == set(BET_TYPES),
            'all eight ticket types must be classified')
    keys = set()
    for row in rows:
        require(row.get('status') in {'COMPARED', 'MISSING', 'NOT_APPLICABLE'} and row.get('reason'),
                'ticket comparison state/reason required')
        tickets = row.get('tickets')
        require(isinstance(tickets, list), 'explicit comparison tickets required')
        require(row['status'] == 'COMPARED' or not tickets, 'unavailable comparison cannot have tickets')
        require(row['status'] != 'COMPARED' or bool(tickets), 'compared type needs tickets')
        for t in tickets:
            require(t.get('type') == row['type'], 'comparison type mismatch')
            key = ticket_event(t, horses=horses, frames=frames)
            require(key not in keys, 'duplicate ticket event')
            keys.add(key)
            from probability_presentation import validate as validate_probability
            validate_probability(t)
    return {'event_count': len(keys), 'optimality_certified': False}


def validate_official_result(result, *, race, date, post, horses=None):
    """通常の公式確定結果の形・時点・全頭対応を共通検査する。"""
    require(isinstance(result,dict) and result.get('status')=='OFFICIAL' and
            result.get('race_id')==race and result.get('race_date_jst')==date,
            'official result identity mismatch')
    require(isinstance(result.get('source_url'),str) and result['source_url'].startswith('https://'),
            'official result source URL required')
    require(iso(result.get('retrieved_at_jst'),'official acquisition')>=iso(post,'post'),
            'future result used before post')
    groups=result.get('finish_groups')
    require(isinstance(groups,list) and groups and all(isinstance(g,list) and g for g in groups),
            'official finish groups missing')
    finished=[h for group in groups for h in group]
    other=[]
    for field in ('non_finishers','scratched_horses'):
        values=result.get(field,[])
        require(isinstance(values,list),'official '+field+' list required')
        other.extend(values)
    require(all(type(h) is int and h>0 for h in finished+other) and
            len(set(finished+other))==len(finished+other),'official duplicate/invalid horse')
    if horses is not None:
        require(set(finished+other)==set(horses) or
                set(finished+result.get('non_finishers',[]))==set(horses),
                'official full-field result coverage mismatch')
    return result
