#!/usr/bin/env python3
"""第4実運用：公式scope登録→選定→独立保存済み予想/推奨→結果/回顧→集計。"""
import argparse
import copy
import hashlib
import json
import sys
import os
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from check_cycle04 import CONTRACT_PATH, DATES, SCHEMA, validate_day
from cycle04_shadow_state import snapshot as shadow_snapshot, previous_items as prior_shadow_items
from cycle04_schedule_change import history as schedule_history, effective_post, assert_post
from check_prediction_compliance import iso, validate_gate
from cycle04_operations import require, safe_path, verified_artifact, selection_ref_post, validate_selection, validate_official_result, validate_formal_result, validate_market, validate_market_payload
from recommendation import verify as verify_recommendation, settle
from cycle04_review_metrics import (review_status, review_hash, independent_metrics,
                                    REVISION_SCHEMA)
from run_release_readiness import check as check_release
from two_axis_candidates import compare as compare_two_axis

DIRECTORY = 'docs/validation/records/cycle_04'


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def kpi(targets=()):
    return {'target_ids': list(targets), 'eligible_ids': [], 'ineligible_ids': [],
            'pending_ids': list(targets), 'reasons': {r: '工程未実施' for r in targets}}


def set_state(obj, race, state, reason):
    require(state in {'ELIGIBLE','INELIGIBLE','PENDING'}, 'unsupported KPI state')
    if race not in obj['target_ids']: obj['target_ids'].append(race)
    for field in ('eligible_ids','ineligible_ids','pending_ids'):
        obj[field] = [r for r in obj[field] if r != race]
    obj[{'ELIGIBLE':'eligible_ids','INELIGIBLE':'ineligible_ids','PENDING':'pending_ids'}[state]].append(race)
    obj['reasons'][race] = reason


def clear_state(obj, race):
    obj['target_ids'] = [r for r in obj['target_ids'] if r != race]
    for field in ('eligible_ids', 'ineligible_ids', 'pending_ids'):
        obj[field] = [r for r in obj[field] if r != race]
    obj['reasons'].pop(race, None)


def save(root, day, before=None):
    path = root/DIRECTORY/(day['race_date_jst']+'.json')
    path_for_validation(root,day)
    raw = (json.dumps(day,ensure_ascii=False,indent=2)+'\n').encode()
    path.parent.mkdir(parents=True,exist_ok=True)
    lock=path.with_suffix('.lock')
    try:
        handle=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    except FileExistsError:
        raise ValueError('day ledger writer already active; check the lock before retrying')
    staged=None
    try:
        os.close(handle)
        if before is None:
            require(not path.exists(), 'day already exists; use the current scope/history')
        else:
            require(path.read_bytes() == before, 'day ledger changed concurrently')
        with tempfile.NamedTemporaryFile(dir=path.parent,prefix='.'+path.stem+'-',delete=False) as stream:
            staged=Path(stream.name);stream.write(raw);stream.flush();os.fsync(stream.fileno())
        require(staged.read_bytes()==raw,'staged day readback mismatch')
        os.replace(staged,path)
        require(path.read_bytes()==raw,'day readback mismatch')
    finally:
        if staged is not None:staged.unlink(missing_ok=True)
        lock.unlink(missing_ok=True)
    return path


def path_for_validation(root, day):
    """恒久ファイルは不合格時に書換えない。終了時に一時検査ファイルを除去。"""
    import tempfile
    folder = tempfile.TemporaryDirectory(prefix='cycle04-validate-')
    path = Path(folder.name)/(day['race_date_jst']+'.json')
    path.write_text(json.dumps(day,ensure_ascii=False))
    try:
        validate_day(root,path,load(root/CONTRACT_PATH))
    finally:
        folder.cleanup()
    # save側の呼出しは既に検証済みのため、同内容の既存pathを要求しない。
    return day


def read_day(root, date):
    require(date in DATES, 'race date outside cycle04')
    path = root/DIRECTORY/(date+'.json')
    raw = path.read_bytes()
    validate_day(root,path,load(root/CONTRACT_PATH))
    return json.loads(raw), raw


def register_scope(root, scope, now=None, extend=False):
    require(scope.get('schema_version') == 'cycle04-official-scope-v1' and
            scope.get('race_date_jst') in DATES, 'official scope/date required')
    date = scope['race_date_jst']; rows = scope.get('races')
    require(isinstance(rows,list) and rows and len({r.get('race_id') for r in rows}) == len(rows), 'unique official races required')
    observed = iso(scope.get('observed_at_jst'),'official scope observed')
    current = now or datetime.now(timezone.utc)
    require(observed <= current and all(current < iso(r.get('scheduled_post_time_jst'),'post') for r in rows),
            'scope cannot be declared after a requested race starts')
    require(isinstance(scope.get('source_url'),str) and scope['source_url'].startswith('https://'), 'official source URL required')
    scope=copy.deepcopy(scope);scope['registered_at_jst']=current.isoformat()
    ids = [r['race_id'] for r in rows]
    if extend:
        day,before=read_day(root,date)
        require(not(set(ids)&set(day['initial_scope'])),'scope extension cannot redefine an existing race/post')
        day.setdefault('scope_history',[copy.deepcopy(day['official_scope'])]).append(copy.deepcopy(scope))
        for race in rows:
            ident=race['race_id'];day['initial_scope'].append(ident)
            day['races'][ident]={'mode':'FORWARD','scheduled_post_time_jst':race['scheduled_post_time_jst'],
                                 'prediction_history':[],'shadow_history':[],'shadow_tracking_version':'phase-shadow-v1','recommendation_state':'PENDING'}
            set_state(day['kpis']['production'],ident,'PENDING','追加依頼・初回未実施')
        return save(root,day,before)
    day = {'schema_version':SCHEMA,'cycle_id':'cycle_04','manual_release':'v1.7.0','race_date_jst':date,
           'official_scope':copy.deepcopy(scope),'initial_scope':ids,'selected_scope':[], 'final_scope':[],
           'reviewed_scope':[],'unfinished_reasons':{},'kpis':{'production':kpi(ids),'recommendation':kpi(),
             'shadow':kpi(),'market':kpi(),'actual_purchase':kpi()},
           'races':{r['race_id']:{'mode':'FORWARD','scheduled_post_time_jst':r['scheduled_post_time_jst'],
                      'prediction_history':[],'shadow_history':[],'shadow_tracking_version':'phase-shadow-v1','recommendation_state':'PENDING'} for r in rows}}
    return save(root,day)


def register_post_change(root, date, ref, now=None, *, preview=False):
    """事前に独立保存した変更原本の参照を日別台帳に一件ずつ追記する。"""
    day, before = read_day(root, date)
    race = ref.get('race_id')
    require(race in day['initial_scope'], 'schedule change outside registered scope')
    require(set(ref) == {'race_id', 'change_ref'} and
            isinstance(ref['change_ref'], dict), 'fixed change reference required')
    row = day['races'][race]
    row.setdefault('schedule_changes', []).append(copy.deepcopy(ref['change_ref']))
    schedule_history(root, row, race, date, now=now)
    if preview:
        return path_for_validation(root, day)
    return save(root, day, before)


def select(root, date, ref):
    day, before = read_day(root,date)
    race = ref.get('race_id'); require(race in day['initial_scope'], 'selection outside initial scope')
    post = day['races'][race]['scheduled_post_time_jst']
    selected_post = selection_ref_post(root, ref['selection_ref'], post)
    history, latest_receipt = verified_artifact(root,ref['selection_ref'],selected_post)
    assert_post(root, day['races'][race], race, date, selected_post,
                at=latest_receipt['receipt_verified_at_jst'])
    verified = validate_selection(root,history,{race:post})
    require(race not in day['reviewed_scope'],'reviewed selection is immutable')
    row=day['races'][race]
    prior=row.get('selection_ref')
    if prior:
        old,_=verified_artifact(root,prior,selection_ref_post(root,prior,post))
        require(history['events'][:len(old['events'])]==old['events'], 'selection history cannot roll back or diverge')
    active=any(s['race_id']==race and s['purpose']=='RECOMMENDATION' for s in verified['active_selections'])
    require(active or prior is not None,'selection requires a recommendation purpose SELECT revision')
    if active:
        if race not in day['selected_scope']:day['selected_scope'].append(race)
        if race not in day['final_scope']:day['unfinished_reasons'][race]='選定済み・最終工程は未実施'
    else:
        require(race not in day['final_scope'],'completed FINAL cannot be removed from its historical scope')
        day['selected_scope']=[r for r in day['selected_scope'] if r!=race]
        day['unfinished_reasons'].pop(race,None)
    row['selection_ref']=copy.deepcopy(ref['selection_ref'])
    row.setdefault('selection_history',[])
    if ref['selection_ref'] not in row['selection_history']:row['selection_history'].append(copy.deepcopy(ref['selection_ref']))
    return save(root,day,before)


def record_prediction(root,date,entry,*,preview=False):
    day,before = read_day(root,date);race = entry.get('race_id')
    require(race in day['initial_scope'], 'prediction outside initial scope')
    row = day['races'][race];phase = entry.get('phase')
    require(race not in day['reviewed_scope'],'reviewed prediction is immutable; preserve its prior result')
    require(phase in {'INITIAL','FINAL'}, 'INITIAL/FINAL phase required')
    require(phase != 'INITIAL' or race not in day['final_scope'], 'INITIAL cannot replace a completed FINAL')
    require(phase != 'FINAL' or race in day['selected_scope'], 'FINAL requires prior selected scope')
    if phase=='FINAL':
        latest=row.get('selection_ref');incoming=entry['operations'].get('selection_ref')
        if latest!=incoming:
            prior,_=verified_artifact(root,latest,selection_ref_post(root,latest,row['scheduled_post_time_jst']))
            updated,select_receipt=verified_artifact(root,incoming,selection_ref_post(root,incoming,row['scheduled_post_time_jst']))
            assert_post(root, row, race, date, selection_ref_post(root,incoming,row['scheduled_post_time_jst']),
                        at=select_receipt['receipt_verified_at_jst'])
            verified=validate_selection(root,updated,{race:row['scheduled_post_time_jst']})
            require(len(updated['events'])>len(prior['events']) and
                    updated['events'][:len(prior['events'])]==prior['events'] and
                    any(s['race_id']==race and s['purpose']=='RECOMMENDATION' for s in verified['active_selections']),
                    'FINAL must extend the latest selected history reference')
            row['selection_ref']=copy.deepcopy(incoming)
            if incoming not in row['selection_history']:row['selection_history'].append(copy.deepcopy(incoming))
    gate = validate_gate(root,safe_path(root,entry.get('prediction_gate_path')))
    # 通常系の受入順序は保持し、変更がある場合だけ追加の独立receiptを確認する。
    if row.get('schedule_changes'):
        _, gate_receipt = verified_artifact(root, entry['operations']['prediction_ref'],
                                             gate['scheduled_post_time_jst'])
        assert_post(root, row, race, date, gate['scheduled_post_time_jst'],
                    at=gate_receipt['receipt_verified_at_jst'],
                    forward=gate['kpi_eligibility']['production'] == 'ELIGIBLE')
    require(gate['race_id'] == race and gate['race_date_jst'] == date and gate['manual_release'] == 'v1.7.0',
            'prediction identity/release mismatch')
    row.update(prediction_gate_path=entry['prediction_gate_path'],operations=entry['operations'],
               input_complete=entry['input_complete'],input_gap_reason=entry.get('input_gap_reason'),
               uncertainty_effect=entry.get('uncertainty_effect'),
               market=row['market'] if row.get('market_ref') else entry['market'],data_cutoff=gate['data_cutoff'])
    identity = {'phase':phase,'prediction_gate_path':entry['prediction_gate_path'],
                'prediction_gate_sha256':hashlib.sha256(safe_path(root,entry['prediction_gate_path']).read_bytes()).hexdigest(),
                'prediction_ref':copy.deepcopy(entry['operations']['prediction_ref']),
                'intent_ref':copy.deepcopy(entry['operations']['intent_ref']),
                'fix_ref':copy.deepcopy(entry['operations']['fix_ref']),
                'baseline_forecast_id':gate['production']['baseline_forecast_id']}
    previous = row['prediction_history']
    shadows = row.setdefault('shadow_history', [])
    same_gate = identity in previous
    old_items = prior_shadow_items(previous[:-1] if same_gate else previous, root,
                                   shadows[:-1] if same_gate else shadows)
    record = shadow_snapshot(root, gate, identity, entry.get('shadow_applicability'), old_items)
    if identity in previous:
        require(previous[-1] == identity and shadows and shadows[-1] == record,
                'same prediction gate cannot replace shadow applicability/history')
    else:
        previous.append(identity)
        shadows.append(record)
    set_state(day['kpis']['production'],race,gate['kpi_eligibility']['production'],'保存・独立FIX・入力・対象gateを照合')
    if record['kpi_state'] == 'NOT_APPLICABLE':
        clear_state(day['kpis']['shadow'], race)
    else:
        set_state(day['kpis']['shadow'],race,record['kpi_state'],
                  record['phase']+' Shadow：'+record['applicability']['reason'])
    if phase == 'FINAL':
        rec_path = entry.get('recommendation_gate_path')
        require(rec_path, 'FINAL requires recommendation state and independent gate')
        rec = verify_recommendation(root,safe_path(root,rec_path))
        require(rec['race_id'] == race and rec['race_date_jst'] == date, 'recommendation identity mismatch')
        row['two_axis_comparison'] = compare_two_axis(gate['production'],
                                                    cancelled_horses=rec.get('cancelled_horses',[]))
        row['recommendation_gate_path'] = rec_path; row['recommendation_state'] = rec['status']
        rec_gate = load(safe_path(root,rec_path))
        set_state(day['kpis']['recommendation'],race,rec_gate['kpi_eligibility'],'固定推奨の独立状態：'+rec['status'])
        if race not in day['final_scope']: day['final_scope'].append(race)
        day['unfinished_reasons'].pop(race,None)
    if preview:
        return path_for_validation(root,day)
    return save(root,day,before)


def record_market(root,date,entry):
    day,before=read_day(root,date);race=entry.get('race_id')
    require(race in day['final_scope'],'optional market requires a fixed FINAL scope')
    require(race not in day['reviewed_scope'],'reviewed market is immutable')
    row=day['races'][race]
    market_post=entry.get('scheduled_post_time_jst',row['scheduled_post_time_jst'])
    payload,market_receipt=verified_artifact(root,entry.get('market_ref'),market_post)
    assert_post(root,row,race,date,market_post,at=market_receipt['receipt_verified_at_jst'])
    require(payload.get('race_id')==race and
            payload.get('race_date_jst')==date,'independent market identity mismatch')
    cutoff=payload.get('data_cutoff')
    require(iso(cutoff,'market cutoff')<iso(market_post,'post'),'market cutoff must precede post')
    state=validate_market_payload(payload,cutoff)
    from market_acquisition import verify_responses
    verify_responses(root,payload)
    row['market_ref']=copy.deepcopy(entry['market_ref']);row['market']=copy.deepcopy(payload['market'])
    row['market_cutoff']=cutoff
    row['market_scheduled_post_time_jst']=market_post
    set_state(day['kpis']['market'],race,'ELIGIBLE' if state=='ACQUIRED' else 'PENDING',
              '任意市場の独立保存・取得状態：'+state)
    return save(root,day,before)


def request_review(root, date, entry, now=None):
    """公式結果を先に照合・登録し、回顧をまだ保存していない不足を監査へ渡す。"""
    day,before=read_day(root,date)
    race=entry.get('race_id');require(race in day['initial_scope'],'review request outside scope')
    current=now or datetime.now(timezone.utc)
    row=day['races'][race]
    path=safe_path(root,entry.get('result_path'));raw=path.read_bytes();result=json.loads(raw)
    post=effective_post(root,row,race,date,at=current.isoformat(),now=current)
    validate_official_result(result,race=race,date=date,post=post.isoformat())
    require(iso(result['retrieved_at_jst'],'result retrieved')<=current,'future result request')
    ref={'artifact_path':entry['result_path'],'sha256':hashlib.sha256(raw).hexdigest()}
    manifest_ref=entry.get('result_reconciliation_ref')
    from cycle04_result_binding import verify_result_bindings, pair
    frozen=verify_result_bindings(root,row,race,date,now=current)
    require(not frozen or frozen['active']==pair(ref,manifest_ref), 'result request cannot replace fixed result/manifest')
    require(not row.get('result_correction_history'), '訂正後の回顧前固定参照を置換できません')
    validate_formal_result(root,row,race=race,date=date,result_ref=ref,manifest_ref=manifest_ref)
    row['result_ready_ref']=ref
    row['result_ready_reconciliation_ref']=copy.deepcopy(manifest_ref)
    row.setdefault('review_requested_at_jst',current.isoformat())
    return save(root,day,before)


def review(root,date,entry):
    day,before = read_day(root,date);race = entry.get('race_id')
    require(race in day['initial_scope'], 'review outside initial scope')
    result_path = safe_path(root,entry.get('result_path'));raw = result_path.read_bytes();result = json.loads(raw)
    require(result.get('race_id') == race and result.get('race_date_jst') == date and result.get('status') == 'OFFICIAL',
            'official result identity required')
    require(iso(result.get('retrieved_at_jst'),'result retrieved') >= effective_post(root, day['races'][race], race, date, at=result['retrieved_at_jst']),
            'future result used before race')
    analysis = entry.get('review')
    status = review_status(analysis)
    require(status['state'] in {'DRAFT', 'COMPLETE'},
            'new review requires schema, Owner items and DRAFT/COMPLETE state')
    row = day['races'][race]
    if row.get('prediction_gate_path'):
        prediction = validate_gate(root,safe_path(root,row['prediction_gate_path']))
        validate_official_result(result,race=race,date=date,post=effective_post(root, row, race, date, at=result['retrieved_at_jst']).isoformat(),
                                horses=prediction['production']['ranking'])
    result_ref={'artifact_path':entry['result_path'],'sha256':hashlib.sha256(raw).hexdigest()}
    manifest_ref = entry.get('result_reconciliation_ref')
    # レース単位で検査してから台帳を変更する。本文や不適格結果は消さない。
    validate_formal_result(root, row, race=race, date=date, result_ref=result_ref,
                           manifest_ref=manifest_ref)
    from cycle04_result_binding import bind_review_result
    result_changed=bind_review_result(root,row,race,date,result_ref,manifest_ref,entry.get('result_correction_ref'))
    earlier = row.get('review')
    if earlier is not None:
        require(result_changed or (row.get('result_ref') == result_ref and row.get('result_reconciliation_ref') == manifest_ref),
                'reviewed result is immutable; a different official result needs its own correction process')
        require(row.get('review_history') and
                row['review_history'][-1]['review'] == earlier,
                'older review cannot be replaced without its original revision history')
        ref = entry.get('revision_ref')
        require(isinstance(ref, dict) and set(ref) == {'artifact_path', 'sha256'},
                'reviewed result is immutable; use an explicit correction history')
        path = f'docs/validation/review-revisions/{date}/{race}/'
        require(ref['artifact_path'].startswith(path) and ref['artifact_path'].endswith('.json'),
                'review revision path invalid')
        raw_revision = safe_path(root, ref['artifact_path']).read_bytes()
        require(hashlib.sha256(raw_revision).hexdigest() == ref['sha256'],
                'review revision fixed hash mismatch')
        index = len(row['review_history']) + 1
        expected = {'schema_version': REVISION_SCHEMA, 'race_date_jst': date, 'race_id': race,
                    'revision': index, 'supersedes_sha256': row['review_history'][-1]['sha256'],
                    'review': analysis}
        require(json.loads(raw_revision) == expected, 'review revision identity or chain mismatch')
        require(race not in day['reviewed_scope'] or status['state'] == 'COMPLETE',
                'completed review cannot be downgraded to DRAFT')
        previous = row['review_history'][-1]['sha256']
    else:
        require(not entry.get('revision_ref'), 'first review cannot claim an amendment')
        previous = None
        ref = None
        index = 1
    row['result_ref'] = result_ref
    row['result_reconciliation_ref'] = copy.deepcopy(manifest_ref)
    row['review'] = copy.deepcopy(analysis)
    row.setdefault('review_history', []).append({'revision': index, 'previous_sha256': previous,
        'sha256': review_hash(analysis), 'review': copy.deepcopy(analysis),
        'revision_ref': copy.deepcopy(ref)})
    if status['state'] == 'COMPLETE' and race not in day['reviewed_scope']:
        day['reviewed_scope'].append(race)
    if row.get('recommendation_gate_path'):
        row['recommendation_result'] = settle(verify_recommendation(root,safe_path(root,row['recommendation_gate_path'])),result)
    return save(root,day,before)


def summary(root):
    contract = load(root/CONTRACT_PATH);days=[]
    for p in sorted((root/DIRECTORY).glob('*.json')):
        day = validate_day(root,p,contract)
        if day.get('registration_origin') != 'POSTRACE_RECONCILIATION':
            days.append(day)
    result = {'schema_version':'cycle04-operational-summary-v1','manual_release':'v1.7.0',
              'recorded_dates':[d['race_date_jst'] for d in days], 'expected_dates':DATES,
              'initial_races':sum(len(d['initial_scope']) for d in days),
              'reviewed_races':sum(len(d['reviewed_scope']) for d in days),'kpis':{},
              'prediction_performance':{'eligible_reviewed':0,'honmei_win':None,'honmei_top2':None,
                                         'honmei_top3':None,'top3_winner_capture':None,'win_brier':None,'top2_brier':None,'top3_brier':None,'topk_winner_capture':{},'calibration':{},'excluded_races':[] },
              'recommendation_performance':{'eligible_settled':0,'hit_race_rate':None,'valid_tickets':0,'hit_tickets':0,'states':{},'invalid_settled_races':[]},
              'additional_review_metrics':{'status':'PENDING_REVIEW_AGGREGATION','reason':'未回顧・比較入力不足は未測定として残す。','reviewed_count':0,'error_labels':{},
                   'by_prediction_confidence':{},'by_input_completeness':{},'by_race_period':{},
                   'initial_to_final':{'paired':0,'ranking_changed':0,'anchor_win_improved':0,'anchor_win_worsened':0,
                                       'unchanged_outcome':0,'missing_initial_ids':[], 'ambiguous_revision_ids':[]}}}
    for name in ('production','recommendation','shadow','market'):
        result['kpis'][name]={field:sum(len(d['kpis'][name][field]) for d in days)
                             for field in ('target_ids','eligible_ids','ineligible_ids','pending_ids')}
    for day in days:
        for race in day['final_scope']:
            state=day['races'][race].get('recommendation_state','PENDING')
            states=result['recommendation_performance']['states'];states[state]=states.get(state,0)+1
    predictions=[];recs=[]
    for day in days:
        for race in day['reviewed_scope']:
            row=day['races'][race];official=load(safe_path(root,row['result_ref']['artifact_path']))
            review_metrics=result['additional_review_metrics'];review_metrics['reviewed_count']+=1
            label=row['review']['error_classification']
            if isinstance(label,str):review_metrics['error_labels'][label]=review_metrics['error_labels'].get(label,0)+1
            comparable=True
            if race in day['kpis']['production']['eligible_ids']:
                gate=validate_gate(root,safe_path(root,row['prediction_gate_path']))
                prod=gate['production']
                if set(official.get('scratched_horses',[]))&set(prod['ranking']):
                    result['prediction_performance']['excluded_races'].append({'race_id':race,
                        'reason':'固定予想に取消馬が残り、実出走集合と異なるため精度比較不能'})
                    comparable=False
                groups=official['finish_groups'];position=0;finish={}
                for group in groups:
                    require(isinstance(group,list) and group and all(type(h) is int for h in group),'official finish group invalid')
                    for horse in group:
                        require(horse not in finish,'duplicate official finisher');finish[horse]=position+1
                    position+=len(group)
                ranking=prod['ranking'];anchor=ranking[0]
                require(set(finish) <= set(ranking),'official horse outside fixed prediction')
                win={h for h,p in finish.items() if p==1}
                if comparable:
                    for category,label in [('by_prediction_confidence',prod['prediction_confidence']),
                        ('by_input_completeness','COMPLETE' if row['input_complete'] else 'INCOMPLETE'),
                        ('by_race_period','MORNING' if iso(gate['scheduled_post_time_jst'],'post').astimezone(
                            iso(day['race_date_jst']+'T00:00:00+09:00','JST').tzinfo).hour<12 else 'AFTERNOON')]:
                        group=review_metrics[category].setdefault(label,{'count':0,'honmei_win_count':0,'honmei_top3_count':0})
                        group['count']+=1;group['honmei_win_count']+=int(anchor in win);group['honmei_top3_count']+=int(finish.get(anchor,999)<=3)
                    paired=review_metrics['initial_to_final']
                    history=row.get('prediction_history',[])
                    initial=[h for h in history if h['phase']=='INITIAL']
                    finals=[h for h in history if h['phase']=='FINAL']
                    if race in day['final_scope']:
                        if len(initial)==len(finals)==1:
                            first=validate_gate(root,safe_path(root,initial[0]['prediction_gate_path']))['production']['ranking']
                            paired['paired']+=1;paired['ranking_changed']+=int(first!=ranking)
                            old_hit=first[0] in win;new_hit=anchor in win
                            paired['anchor_win_improved']+=int(not old_hit and new_hit)
                            paired['anchor_win_worsened']+=int(old_hit and not new_hit)
                            paired['unchanged_outcome']+=int(old_hit==new_hit)
                        elif not initial:paired['missing_initial_ids'].append(race)
                        else:paired['ambiguous_revision_ids'].append(race)
                if comparable:predictions.append({'win':anchor in win,'top2':finish.get(anchor,999)<=2,'top3':finish.get(anchor,999)<=3,
                    'capture':bool(set(ranking[:3]) & win),'brier':sum((p['win_probability']-int(p['horse_no'] in win))**2 for p in prod['probabilities'])/len(ranking),
                    'top2_brier':sum((p['top2_probability']-int(finish.get(p['horse_no'],999)<=2))**2 for p in prod['probabilities'])/len(ranking),
                    'top3_brier':sum((p['top3_probability']-int(finish.get(p['horse_no'],999)<=3))**2 for p in prod['probabilities'])/len(ranking),
                    'capture_k':{str(k):bool(set(ranking[:k])&win) for k in (1,3,6)},
                    'calibration':{field:[(p[field],int(finish.get(p['horse_no'],999)<=pos)) for p in prod['probabilities']]
                                   for field,pos in [('win_probability',1),('top2_probability',2),('top3_probability',3)]}})
            if row.get('recommendation_result',{}).get('status')=='INVALID':
                result['recommendation_performance']['invalid_settled_races'].append(race)
            if race in day['kpis']['recommendation']['eligible_ids'] and row.get('recommendation_result',{}).get('status')=='SETTLED':
                recs.append(row['recommendation_result'])
    if predictions:
        metrics=result['prediction_performance'];metrics['eligible_reviewed']=len(predictions)
        for field,key in (('honmei_win','win'),('honmei_top2','top2'),('honmei_top3','top3'),
                          ('top3_winner_capture','capture'),('win_brier','brier'),('top2_brier','top2_brier'),('top3_brier','top3_brier')):
            metrics[field]=sum(p[key] for p in predictions)/len(predictions)
        metrics['topk_winner_capture']={str(k):sum(p['capture_k'][str(k)] for p in predictions)/len(predictions) for k in (1,3,6)}
        for field in ('win_probability','top2_probability','top3_probability'):
            pairs=[x for p in predictions for x in p['calibration'][field]]
            bins=[]
            for bucket in range(10):
                rows=[x for x in pairs if min(int(x[0]*10),9)==bucket]
                bins.append({'lower':bucket/10,'upper':(bucket+1)/10,'count':len(rows),
                             'mean_prediction':sum(x[0] for x in rows)/len(rows) if rows else None,
                             'observed_rate':sum(x[1] for x in rows)/len(rows) if rows else None})
            metrics['calibration'][field]=bins
    if recs:
        result['recommendation_performance'].update(eligible_settled=len(recs),hit_race_rate=sum(r['race_hit'] for r in recs)/len(recs),
             valid_tickets=sum(r['valid_tickets'] for r in recs),hit_tickets=sum(r['hit_tickets'] for r in recs))
        by_type={}
        for rec in recs:
            for ticket in rec['tickets']:
                if ticket['result']=='INVALID':continue
                group=by_type.setdefault(ticket['type'],{'valid_tickets':0,'hit_tickets':0})
                group['valid_tickets']+=1;group['hit_tickets']+=int(ticket['result']=='HIT')
        for group in by_type.values():group['hit_rate']=group['hit_tickets']/group['valid_tickets']
        result['recommendation_performance']['by_type']=by_type
        result['recommendation_performance']['tickets_per_race']=sum(r['valid_tickets'] for r in recs)/len(recs)
    result['independent_review_metrics'] = independent_metrics(root, days)
    review_metrics=result['additional_review_metrics']
    if review_metrics['reviewed_count']:review_metrics['status']='RECORDED_WITH_LIMITATIONS'
    for category in ('by_prediction_confidence','by_input_completeness','by_race_period'):
        for group in review_metrics[category].values():
            group['honmei_win_rate']=group['honmei_win_count']/group['count']
            group['honmei_top3_rate']=group['honmei_top3_count']/group['count']
    from cycle04_completion import evaluate_days
    from cycle04_migration import compute_summary
    result['migration_status'] = compute_summary(root)
    result['completion'] = evaluate_days(root, days)
    result['cycle_state'] = result['completion']['state']
    # 集計の表示だけではGit保存済みとは判定しない。
    return result


def check_working_branch(root,date):
    require(date in DATES,'race date outside cycle04')
    result=subprocess.run(['git','symbolic-ref','--quiet','--short','HEAD'],cwd=root,text=True,capture_output=True)
    require(result.returncode==0 and result.stdout.strip()=='prediction/'+date,
            'writes require the matching prediction/YYYY-MM-DD branch; main/detached/other dates are read-only')


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--register-scope',type=Path)
    mode.add_argument('--extend-scope',type=Path)
    mode.add_argument('--register-post-change',type=Path)
    mode.add_argument('--select',type=Path)
    mode.add_argument('--record-prediction',type=Path)
    mode.add_argument('--review',type=Path)
    mode.add_argument('--request-review',type=Path,help='確認済み公式結果を回顧前に登録')
    mode.add_argument('--record-market',type=Path)
    mode.add_argument('--summary',action='store_true')
    parser.add_argument('--date')
    parser.add_argument('--preview',action='store_true',help='公式発走変更の台帳保存前検査のみ')
    args=parser.parse_args(argv)
    try:
        root=args.root.resolve();check_release(root,require_main=True)
        require(not args.preview or bool(args.register_post_change),
                '--preview is supported only for --register-post-change')
        if args.summary:
            print(json.dumps(summary(root),ensure_ascii=False,indent=2));return 0
        if args.register_scope or args.extend_scope:
            scope=load(args.register_scope or args.extend_scope)
            check_working_branch(root,scope.get('race_date_jst'))
            out=register_scope(root,scope,extend=bool(args.extend_scope))
        else:
            require(args.date,'race date required')
            check_working_branch(root,args.date)
            if args.register_post_change:out=register_post_change(root,args.date,load(args.register_post_change),preview=args.preview)
            elif args.select:out=select(root,args.date,load(args.select))
            elif args.record_prediction:out=record_prediction(root,args.date,load(args.record_prediction))
            elif args.record_market:out=record_market(root,args.date,load(args.record_market))
            elif args.request_review:out=request_review(root,args.date,load(args.request_review))
            else:out=review(root,args.date,load(args.review))
        if args.preview:
            print('公式発走変更の検証成功（プレビューのみ・台帳未保存）。')
        else:
            print(f'日別台帳のローカル保存・検査成功：{out}。日次branchへのGit保存・読戻しを行ってください。')
        return 0
    except (ValueError,OSError,KeyError,TypeError) as exc:
        print('第4運用未完了：'+str(exc),file=sys.stderr);return 1


if __name__=='__main__':raise SystemExit(main())
