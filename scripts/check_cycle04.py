#!/usr/bin/env python3
"""第4の準備整合と実運用開始を分離。未定版・旧台帳・合成試験で開始認証しない。"""
import argparse
import json
import re
import sys
from pathlib import Path

from check_prediction_compliance import (ComplianceError, contract_state, iso, release,
                                         validate_gate, LEGACY_RELEASE)
from cycle04_schedule_change import history as schedule_history, effective_post, assert_post
from cycle04_operations import (fingerprint, positive_set, require, safe_path,
                               validate_inputs, validate_market, validate_market_payload, validate_selection, selection_ref_post,
                               validate_ticket_comparison, verified_artifact, validate_official_result,
                               validate_formal_result)
from recommendation import verify as verify_recommendation, settle
from cycle04_review_metrics import validate_revision_history
from cycle04_shadow_state import verify_history as verify_shadow_history

CONTRACT_PATH = 'docs/validation/contracts/cycle_04.json'
DATES = ['2026-10-17', '2026-10-18', '2026-10-24', '2026-10-25', '2026-10-31', '2026-11-01']
VENUES_BY_DATE = {date: ['TOK', 'KYO', 'NII'] if date <= '2026-10-25' else ['TOK', 'KYO']
                  for date in DATES}
SCHEMA = 'cycle04-day-v1'


def load(path):
    value = json.loads(path.read_text(encoding='utf-8'))
    require(isinstance(value, dict), 'JSON object required')
    return value


def check_preparation(root):
    c = load(root / CONTRACT_PATH)
    require(c.get('schema_version') == 'cycle04-contract-v1' and c.get('cycle_id') == 'cycle_04',
            'cycle04 contract required')
    require(c.get('race_dates') == DATES and c.get('venues') == ['TOK', 'KYO', 'NII'], 'cycle04 schedule mismatch')
    require(c.get('day_schema') == SCHEMA and c.get('status') in {'PREPARED', 'ACTIVE'}, 'invalid cycle04 contract state')
    require(c.get('current_release') == LEGACY_RELEASE, 'historical baseline release mismatch')
    if c['status'] == 'PREPARED':
        require(c.get('next_release') is None and c.get('effective_race_date') is None,
                'undecided cutover must remain null')
        require(release(root) == LEGACY_RELEASE and contract_state(root)['status'] == 'PENDING',
                'prepared contract cannot imply active cutover')
    else:
        require_active(root, c)
    decisions = load(safe_path(root, c.get('decisions_path')))
    require(decisions.get('schema_version') == 'cycle03-decisions-v1', 'individual decisions required')
    require(decisions.get('performance_promotion') == 'NOT_APPROVED', 'unsupported performance promotion')
    proposals = decisions.get('changes')
    required_ids = {f'C{i:02d}' for i in range(1, 17)}
    require(isinstance(proposals, list) and len(proposals) == 16 and
            {x.get('id') for x in proposals} == required_ids, 'all summary proposals require individual decisions')
    for item in proposals:
        require(item.get('decision') in {'ADOPT_OPERATION', 'CONTINUE_VALIDATION', 'OBSERVE',
                                         'RETAIN_FACTS', 'PREPARE_AGREED', 'REJECT'}, 'invalid decision')
        require(all(item.get(k) for k in ('title', 'owner', 'reason', 'evidence', 'next_test', 'protected')),
                'decision owner/evidence/retest/protection missing')
        for p in item['evidence']:
            require(safe_path(root, p).is_file(), 'decision evidence missing')
    expected_validation = {f'E-{i:02d}' for i in (3, 4, 7, 8, 9, 10, 11, 12, 13)} | {'51B', 'U-01', 'U-01Q', 'U-02'}
    validations = decisions.get('validation_items')
    require(isinstance(validations, list) and len(validations) == len(expected_validation)
            and {v.get('internal_id') for v in validations} == expected_validation,
            'individual validation dispositions missing')
    for v in validations:
        require(v.get('performance_promotion') == 'NOT_APPROVED' and v.get('next_test')
                and safe_path(root, v.get('owner')).is_file(), 'validation owner/retest missing')
    collection = load(root / 'docs/validation/reviews/cycle_03/collection.json')
    difference = {(date, race) for date, day in collection['daily'].items()
                  for race in day['selected_without_final_ids']}
    classifications = decisions.get('candidate_difference_classification')
    require(isinstance(classifications, list) and len(classifications) == len(difference)
            and {(r.get('race_date_jst'), r.get('race_id')) for r in classifications} == difference,
            'candidate difference classification missing/duplicated')
    for r in classifications:
        require(r.get('reason') and r.get('status') in {'DESELECTED_BY_USER', 'NOT_EXECUTED_CAUSE_UNRECORDED',
                'FINAL_STAGE_NOT_EXECUTED', 'OPERATIONAL_SELECTION_NOT_CLOSED', 'OMISSION_ACCEPTED_BY_USER'}
                and safe_path(root, r.get('evidence_path')).is_file(), 'candidate difference evidence missing')
    excluded = sum(r['status'] == 'DESELECTED_BY_USER' for r in classifications)
    require(decisions.get('candidate_difference_counts') == {'raw_difference': len(difference),
            'deselected_by_user': excluded, 'not_executed': len(difference) - excluded,
            'user_accepted_omissions_within_not_executed': sum(r['status'] == 'OMISSION_ACCEPTED_BY_USER' for r in classifications)},
            'candidate difference count mismatch')
    validate_acceptance(root, c)
    return c


def validate_acceptance(root, contract):
    """準備検査と正式開始で同じ受入状態・固定ソースを検査する。"""
    c = contract
    acceptance = load(safe_path(root, c.get('acceptance_path')))
    require(acceptance.get('schema_version') == 'cycle04-acceptance-v1' and
            acceptance.get('mode') == 'SYNTHETIC' and acceptance.get('live_race_count') is None,
            'synthetic acceptance must not claim live races')
    require(acceptance.get('result') == 'PASS' and type(acceptance.get('failures')) is int and acceptance['failures'] == 0 and
            type(acceptance.get('skipped')) is int and acceptance['skipped'] == 0 and
            type(acceptance.get('tests_run')) is int and acceptance['tests_run'] > 0,
            'acceptance not passed')
    manifest = acceptance.get('source_manifest')
    require(isinstance(manifest, list) and bool(manifest), 'acceptance input hashes required')
    required_sources = {'scripts/check_cycle04.py', 'scripts/cycle04_operations.py',
                        'scripts/test_cycle04_acceptance.py', 'scripts/task_completion.py',
                        'scripts/check_prediction_compliance.py', 'scripts/recommendation.py',
                        'scripts/selection_history.py', 'scripts/verify_prediction_persistence.py',
                        'scripts/seal_prediction.py',
                        c['decisions_path']}
    required_sources |= {p.relative_to(root).as_posix() for p in
                         set(root.glob('scripts/*.py')) | set(root.glob('docs/manual/*.md'))}
    require(required_sources.issubset({x.get('path') for x in manifest}), 'acceptance source coverage missing')
    require(len({x.get('path') for x in manifest}) == len(manifest), 'duplicate acceptance source')
    for item in manifest:
        require(fingerprint(safe_path(root, item.get('path')).read_bytes()) == item.get('sha256'),
                'stale acceptance: source hash mismatch')
    return acceptance


def require_active(root, contract):
    state = contract_state(root)
    require(contract['status'] == 'ACTIVE' and state['status'] == 'ACTIVE',
            '第4サイクル開始不可：正式切替・版・有効日が未確定です')
    require(contract.get('next_release') == state.get('next_release') == release(root) and
            contract.get('effective_race_date') == state.get('effective_race_date'),
            'release/effective date cutover mismatch')
    require(state['effective_race_date'] <= DATES[0], 'cutover is not effective on first cycle04 race day')


def string_set(value, label):
    require(isinstance(value, list) and all(isinstance(x, str) and x for x in value)
            and len(set(value)) == len(value), label + ': unique string list required')
    return set(value)


def validate_day(root, path, contract):
    d = load(path)
    require(d.get('schema_version') == SCHEMA and d.get('cycle_id') == 'cycle_04',
            '第3台帳・旧契約を第4へ流用できません')
    date = d.get('race_date_jst')
    require(date in DATES and path.stem == date, 'cycle04 date/path mismatch')
    initial = string_set(d.get('initial_scope'), 'initial')
    require(bool(initial), 'empty scope is not a completed day')
    for race in initial:
        require(re.fullmatch(date.replace('-', '') + '-(' + '|'.join(VENUES_BY_DATE[date]) + r')-(0[1-9]|1[0-2])', race),
                'race outside declared day/venues')
    selected = string_set(d.get('selected_scope'), 'selected')
    final = string_set(d.get('final_scope'), 'final')
    reviewed = string_set(d.get('reviewed_scope'), 'reviewed')
    require(final <= selected <= initial and reviewed <= initial, 'cycle04 stage scope mismatch')
    missing = d.get('unfinished_reasons')
    require(isinstance(missing, dict) and set(missing) == (selected - final) and
            all(isinstance(v, str) and v.strip() for v in missing.values()), 'all unfinal races require reasons')
    rows = d.get('races')
    require(isinstance(rows, dict) and set(rows) == initial, 'all initial races require a record')
    for race, row in rows.items():
        require(isinstance(row, dict), 'race record object required')
        post = iso(row.get('scheduled_post_time_jst'), 'race scheduled post')
        schedule_history(root, row, race, date)
        require(post.astimezone(iso(date + 'T00:00:00+09:00', 'race date').tzinfo).date().isoformat() == date,
                'race scheduled post date mismatch')
        if row.get('market_ref'):
            require(race in final, 'optional market requires fixed FINAL scope')
            payload, _ = verified_artifact(root, row['market_ref'], row['scheduled_post_time_jst'])
            cutoff = row.get('market_cutoff')
            require(payload.get('race_id') == race and payload.get('race_date_jst') == date
                    and payload.get('market') == row.get('market') and
                    payload.get('data_cutoff') == cutoff, 'independent market record mismatch')
            require(iso(cutoff, 'market cutoff') < post, 'market cutoff must precede post')
            validate_market_payload(payload, cutoff)
            from market_acquisition import verify_responses
            verify_responses(root, payload)
    if contract_state(root).get('full_horse_contract')=='REQUIRED':
        require(d.get('manual_release')==release(root),'day release mismatch')
        registrations=d.get('scope_history',[d.get('official_scope')])
        require(isinstance(registrations,list) and registrations,'official scope registration history required')
        declared=[]
        for registration in registrations:
            require(isinstance(registration,dict) and registration.get('schema_version')=='cycle04-official-scope-v1' and
                    registration.get('race_date_jst')==date and isinstance(registration.get('source_url'),str) and
                    registration['source_url'].startswith('https://'),'official scope/date/source mismatch')
            observed=iso(registration.get('observed_at_jst'),'official observed')
            registered=iso(registration.get('registered_at_jst'),'scope registered')
            require(observed<=registered,'scope registration precedes observation')
            require(isinstance(registration.get('races'),list) and registration['races'],'official race scope missing')
            for item in registration['races']:
                race=item.get('race_id');declared.append(race)
                require(race in rows and item.get('scheduled_post_time_jst')==rows[race]['scheduled_post_time_jst'] and
                        registered<iso(item['scheduled_post_time_jst'],'post'),'scope/post registration mismatch')
        require(len(declared)==len(set(declared)) and set(declared)==initial,'official scope/initial mismatch')
        for race,row in rows.items():
            require(not row.get('prediction_gate_path') or row.get('prediction_history'),
                    'saved prediction requires immutable history')
    for race, row in rows.items():
        ref = row.get('result_ref')
        if ref is None:
            require(race not in reviewed, 'reviewed race requires an official result artifact')
            require(row.get('review') is None and row.get('review_history') is None,
                    'review without official result')
            continue
        require(isinstance(ref, dict), 'official result reference must be an object')
        raw = safe_path(root, ref.get('artifact_path')).read_bytes()
        require(fingerprint(raw) == ref.get('sha256'), 'official result hash mismatch')
        result = json.loads(raw)
        prediction=validate_gate(root,safe_path(root,row['prediction_gate_path'])) if row.get('prediction_gate_path') else None
        validate_official_result(result,race=race,date=date,post=effective_post(root, row, race, date, at=result['retrieved_at_jst']).isoformat(),
                                horses=prediction['production']['ranking'] if prediction else None)
        validate_formal_result(root, row, race=race, date=date, result_ref=ref,
                               manifest_ref=row.get('result_reconciliation_ref'))
        status = validate_revision_history(root, row, race, date, row['scheduled_post_time_jst'])
        # 下書きは不足した誤差分類をそのまま残し、結果と改訂履歴だけを固定する。
        # 新v2のCOMPLETEはreview_statusが全Owner必須項目を検証済み。
        # 旧回顧だけは当時の3項目を保持し、遡及的な完了扱いはしない。
        if status['state'] == 'LEGACY_INCOMPLETE':
            require(not any(name in status['missing'] for name in
                            ('error_classification', 'non_degradation', 'next_validation')),
                    'reviewed scope requires error/non-degradation/next validation')
        if status['state'] == 'COMPLETE':
            require(race in reviewed, 'COMPLETE review must be in reviewed scope')
        elif status['state'] == 'DRAFT':
            require(race not in reviewed, 'DRAFT review cannot be marked complete')
        else:
            # 旧記録は読取可能でも新しいOwner完了要件を満たしたことにはしない。
            require(race in reviewed, 'legacy review must preserve historical reviewed scope')
        if row.get('recommendation_gate_path'):
            rec=verify_recommendation(root,safe_path(root,row['recommendation_gate_path']))
            require(row.get('recommendation_result')==settle(rec,result),'recommendation settlement mismatch')
    shadow_latest = {}
    for race,row in rows.items():
        history=row.get('prediction_history',[])
        require(isinstance(history,list),'prediction history list required')
        for entry in history:
            require(entry.get('phase') in {'INITIAL','FINAL'},'prediction history phase invalid')
            gate_path=safe_path(root,entry.get('prediction_gate_path'))
            require(fingerprint(gate_path.read_bytes())==entry.get('prediction_gate_sha256'),
                    'prediction history gate hash mismatch')
            gate=validate_gate(root,gate_path)
            require(gate['race_id']==race and gate['race_date_jst']==date and
                    gate['production']['baseline_forecast_id']==entry.get('baseline_forecast_id'),
                    'prediction history identity mismatch')
            body,history_receipt=verified_artifact(root,entry.get('prediction_ref'),gate['scheduled_post_time_jst'],
                                    expected_id=gate['production']['evidence_ref']['artifact_id'])
            assert_post(root, row, race, date, gate['scheduled_post_time_jst'],
                        at=history_receipt['receipt_verified_at_jst'],
                        forward=gate['kpi_eligibility']['production']=='ELIGIBLE')
            require(entry['prediction_ref']['artifact_path']==gate['production']['evidence_ref']['artifact_path'],
                    'prediction history body mismatch')
        if history:
            require(history[-1]['prediction_gate_path']==row.get('prediction_gate_path') and
                    history[-1]['prediction_ref']==row.get('operations',{}).get('prediction_ref'),
                    'latest prediction/history mismatch')
            require((history[-1]['phase']=='FINAL')==(race in final),'final/history scope mismatch')
        if row.get('shadow_tracking_version') is not None:
            require(row['shadow_tracking_version'] == 'phase-shadow-v1' and
                    len(row.get('shadow_history', [])) == len(history),
                    'complete phase shadow tracking required')
        latest = verify_shadow_history(root, row, race, date, history)
        if latest is not None:
            shadow_latest[race] = latest
    for name, scope in [('production', initial), ('recommendation', final), ('shadow', initial),
                        ('market', final), ('actual_purchase', initial)]:
        k = d.get('kpis', {}).get(name)
        require(isinstance(k, dict), 'independent KPI required: ' + name)
        target = string_set(k.get('target_ids'), name + '/target')
        require(target <= scope, 'KPI outside stage scope')
        if name=='actual_purchase':require(not target,'new actual purchase scope must remain empty')
        if name in {'production', 'recommendation'}:
            require(target == scope, 'production/final recommendation KPI cannot omit declared targets')
        groups = [string_set(k.get(s), name + '/' + s) for s in
                  ('eligible_ids', 'ineligible_ids', 'pending_ids')]
        require(set().union(*groups) == target and sum(map(len, groups)) == len(target), 'KPI partition mismatch')
        require(isinstance(k.get('reasons'), dict) and set(k['reasons']) == target
                and all(isinstance(v, str) and v.strip() for v in k['reasons'].values()), 'KPI reasons missing')
        if name == 'shadow':
            for race, latest in shadow_latest.items():
                state = latest['kpi_state']
                if state == 'NOT_APPLICABLE':
                    require(race not in target,
                            'stale shadow KPI must be cleared for explicit final non-applicability')
                else:
                    field = {'ELIGIBLE':'eligible_ids',
                             'INELIGIBLE':'ineligible_ids','PENDING':'pending_ids'}[state]
                    require(race in string_set(k[field], 'shadow latest '+field) and
                            k['reasons'].get(race) ==
                            latest['phase']+' Shadow：'+latest['applicability']['reason'],
                            'shadow latest KPI/state/reason mismatch')
        for race in groups[0]:
            require_active(root, contract)
            row = rows[race]
            require(row.get('mode') == 'FORWARD', 'Replay cannot certify a forward KPI')
            if name in {'production', 'shadow', 'recommendation'}:
                gate_path = safe_path(root, row.get('prediction_gate_path'))
                gate = validate_gate(root, gate_path)
                require(gate['race_id'] == race and gate['race_date_jst'] == date,
                        'gate race mismatch')
                _, verified_receipt = verified_artifact(root, gate['production']['evidence_ref'], gate['scheduled_post_time_jst'])
                assert_post(root, row, race, date, gate['scheduled_post_time_jst'],
                            at=verified_receipt['receipt_verified_at_jst'])
                if name == 'recommendation':
                    rec = verify_recommendation(root, safe_path(root, row.get('recommendation_gate_path')))
                    require(rec['race_id'] == race, 'recommendation race mismatch')
                    if 'recommendation_state' in row:
                        require(row['recommendation_state']==rec['status'],'recommendation state mismatch')
                    rec_gate = load(safe_path(root, row['recommendation_gate_path']))
                    require(rec_gate.get('kpi_eligibility') == 'ELIGIBLE', 'recommendation not certified')
                else:
                    require(gate['kpi_eligibility'][name] == 'ELIGIBLE', 'KPI gate not eligible')
                op = row.get('operations')
                require(isinstance(op, dict), 'input/FIX/selection contract required')
                horses = positive_set(op.get('horse_numbers'), 'active horse scope')
                require(horses == set(gate['production']['ranking']), 'all active horses must have a ranking')
                probs = gate['production']['probabilities']
                require({p['horse_no'] for p in probs} == horses and len(probs) == len(horses),
                        'all-horse probabilities required; top3-only cannot certify full prediction')
                for field, total in [('win_probability', 1), ('top2_probability', 2), ('top3_probability', 3)]:
                    require(abs(sum(p[field] for p in probs) - min(total,len(horses))) < 1e-6, 'probability total mismatch: ' + field)
                require({e['horse_no'] for e in gate['production']['evidence_items']} == horses,
                        'all-horse prediction evidence required')
                post = gate['scheduled_post_time_jst']
                snapshot, body_receipt = verified_artifact(root, op.get('prediction_ref'), post,
                                                           expected_id=gate['production']['evidence_ref']['artifact_id'])
                require(op['prediction_ref']['artifact_path'] == gate['production']['evidence_ref']['artifact_path'],
                        'operations refer to another prediction')
                fix, fix_receipt = verified_artifact(root, op.get('fix_ref'), post)
                intent, intent_receipt = verified_artifact(root, op.get('intent_ref'), post)
                require(fix.get('schema_version') == 'prediction-fix-manifest-v1' and
                        fix.get('snapshot_id') == snapshot['snapshot_id'] and
                        fix.get('artifact_path') == op['prediction_ref']['artifact_path'] and
                        fix.get('fixed_content_sha256') == op['prediction_ref']['sha256'] and
                        fix.get('fixed_at_jst') == snapshot.get('fixed_at_jst') and
                        fix.get('intent_ref') == op.get('intent_ref'),
                        'independent FIX manifest mismatch')
                require(intent.get('schema_version') == 'prediction-persistence-intent-v1' and
                        intent.get('snapshot_id') == snapshot['snapshot_id'] and
                        intent.get('required_race_ids') == [race] and
                        intent.get('artifact_path') == op['prediction_ref']['artifact_path'] and
                        iso(intent.get('deadline_jst'), 'intent deadline') == iso(post, 'post') and
                        intent.get('working_branch') == 'prediction/' + date,
                        'predeclaration scope/path/deadline mismatch')
                require(iso(intent_receipt['receipt_verified_at_jst'], 'intent readback') <=
                        iso(snapshot['fixed_at_jst'], 'FIX') <=
                        iso(fix_receipt['persist_verified_at_jst'], 'FIX hash save') <=
                        iso(fix_receipt['receipt_verified_at_jst'], 'FIX hash readback') <=
                        iso(body_receipt['persist_verified_at_jst'], 'body save'),
                        'FIX hash/intent must be saved independently before body persistence')
                data, input_receipt = verified_artifact(root, op.get('inputs_ref'), post)
                require(iso(input_receipt['receipt_verified_at_jst'], 'inputs readback') <=
                        iso(gate['data_cutoff'], 'cutoff'), 'inputs saved after prediction cutoff')
                coverage = validate_inputs(data, race_id=race, horses=op.get('horse_numbers'),
                                           cutoff=gate['data_cutoff'], post=post)
                require(row.get('input_complete') is coverage['complete'], 'input completeness misreported')
                if not coverage['complete']:
                    require(row.get('input_gap_reason') and row.get('uncertainty_effect'),
                            'missing input requires explicit uncertainty/impact')
                market_cutoff=row.get('market_cutoff',gate['data_cutoff'])
                require(iso(market_cutoff,'market cutoff')<iso(post,'post'),'market cutoff must precede post')
                validate_market(row.get('market'),market_cutoff)
                original_post = row['scheduled_post_time_jst']
                history, _ = verified_artifact(root, op.get('selection_ref'),
                                               selection_ref_post(root, op.get('selection_ref'), original_post))
                selection = validate_selection(root, history, {race: original_post})
                if race in final:
                    require(any(p['race_id'] == race and p['purpose'] == 'RECOMMENDATION' and p['active']
                                for p in selection['plans'].values()), 'final recommendation lacks selection revision')
                frames = {int(h): f for h, f in op.get('frames', {}).items()}
                validate_ticket_comparison(op.get('ticket_comparison'), horses=set(op['horse_numbers']), frames=frames)
            else:
                require(name != 'actual_purchase', 'v1.7.0 does not certify new actual purchase records')
                # 任意市場・実購入は専用証跡を要求。推奨の適格性を転用しない。
                payload, _ = verified_artifact(root, row.get(name + '_ref'), row.get('scheduled_post_time_jst'))
                require(payload.get('race_id') == race and payload.get('race_date_jst') == date,
                        'market/actual artifact race mismatch')
                if name == 'market':
                    require(payload.get('schema_version') in {'market-analysis-v1', 'market-analysis-v2'} and
                            payload.get('market') == row.get('market'), 'market artifact mismatch')
                    require(payload.get('data_cutoff',row.get('data_cutoff'))==row.get('market_cutoff',row.get('data_cutoff')),
                            'independent market cutoff mismatch')
                    require(iso(row.get('market_cutoff',row.get('data_cutoff')),'market cutoff')<
                            iso(row['scheduled_post_time_jst'],'post'),'market cutoff must precede post')
                    require(validate_market(row.get('market'), row.get('market_cutoff',row.get('data_cutoff'))) == 'ACQUIRED',
                            'market KPI needs acquired price')
                else:
                    require(payload.get('schema_version') == 'actual-purchase-v1'
                            and payload.get('confirmation') == 'USER_CONFIRMED', 'actual purchase must be confirmed')
                    tickets = payload.get('tickets')
                    require(isinstance(tickets, list) and tickets and
                            all(type(t.get('amount_yen')) is int and t['amount_yen'] > 0 for t in tickets)
                            and sum(t['amount_yen'] for t in tickets) == payload.get('total_amount_yen'),
                            'actual purchase ticket total mismatch')
    return d


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument('--require-active', action='store_true')
    p.add_argument('--require-complete', action='store_true',
                   help='正常一巡のみを要求。6日全scopeの工程と集計のGit読戻しが必要')
    p.add_argument('--completion-manifest', type=Path,
                   help='日別・集計の固定path/SHA256/Git commit参照JSON')
    p.add_argument('--closure-review', type=Path,
                   help='人間が審査・Git保存した理由付き終了記録の固定参照JSON')
    args = p.parse_args(argv)
    try:
        root = args.root.resolve()
        c = check_preparation(root)
        if args.require_active:
            require_active(root, c)
            if c.get('activation_policy') == 'MAIN_MERGE':
                from run_release_readiness import check
                check(root, require_main=True)
        days = []
        directory = root / 'docs/validation/records/cycle_04'
        for path in sorted(directory.glob('*.json')):
            days.append(validate_day(root, path, c))
        from cycle04_completion import evaluate_days
        require(not (args.require_complete and args.closure_review),
                '正常一巡と理由付き終了を同時申告できません')
        frozen = load(args.completion_manifest) if args.completion_manifest else None
        closure = load(args.closure_review) if args.closure_review else None
        result = evaluate_days(root, days, frozen_refs=frozen, closure_ref=closure)
        if args.require_complete:
            require(result['normal_cycle_complete'],
                    '正常一巡未完了：' + json.dumps(result['issues'], ensure_ascii=False) +
                    ('。集計のGit読戻し固定参照が未指定です' if frozen is None else ''))
        if result['issues']:
            print('不足対象・理由：' + json.dumps(result['issues'], ensure_ascii=False))
        print(f'第4検査契約の準備照合成功。実測{len(days)}/{len(DATES)}日。状態：{result["state"]}。'
              f'集計Git読戻し：{result["summary_git_readback_verified"]}。性能昇格：未採用。'
              f'正式切替状態：{c["status"]}。')
        return 0
    except (ValueError, OSError, TypeError, KeyError, AttributeError) as exc:
        print(f'第4検査不合格：{exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
