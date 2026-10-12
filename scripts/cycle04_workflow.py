#!/usr/bin/env python3
"""第4実運用：公式scope登録→選定→独立保存済み予想/推奨→結果/回顧→集計。"""
import argparse
import copy
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from check_cycle04 import CONTRACT_PATH, DATES, SCHEMA, validate_day
from check_prediction_compliance import iso, validate_gate
from cycle04_operations import require, safe_path, verified_artifact, validate_selection
from recommendation import verify as verify_recommendation, settle
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


def save(root, day, before=None):
    path = root/DIRECTORY/(day['race_date_jst']+'.json')
    path_for_validation(root,day)
    raw = (json.dumps(day,ensure_ascii=False,indent=2)+'\n').encode()
    path.parent.mkdir(parents=True,exist_ok=True)
    if before is None:
        require(not path.exists(), 'day already exists; use the current scope/history')
        with path.open('xb') as handle: handle.write(raw)
    else:
        require(path.read_bytes() == before, 'day ledger changed concurrently')
        path.write_bytes(raw)
    require(path.read_bytes() == raw, 'day readback mismatch')
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
    return json.loads(raw), raw


def register_scope(root, scope, now=None):
    require(scope.get('schema_version') == 'cycle04-official-scope-v1' and
            scope.get('race_date_jst') in DATES, 'official scope/date required')
    date = scope['race_date_jst']; rows = scope.get('races')
    require(isinstance(rows,list) and rows and len({r.get('race_id') for r in rows}) == len(rows), 'unique official races required')
    observed = iso(scope.get('observed_at_jst'),'official scope observed')
    current = now or datetime.now(timezone.utc)
    require(observed <= current and all(current < iso(r.get('scheduled_post_time_jst'),'post') for r in rows),
            'scope cannot be declared after a requested race starts')
    require(isinstance(scope.get('source_url'),str) and scope['source_url'].startswith('https://'), 'official source URL required')
    ids = [r['race_id'] for r in rows]
    day = {'schema_version':SCHEMA,'cycle_id':'cycle_04','manual_release':'v1.7.0','race_date_jst':date,
           'official_scope':copy.deepcopy(scope),'initial_scope':ids,'selected_scope':[], 'final_scope':[],
           'reviewed_scope':[],'unfinished_reasons':{},'kpis':{'production':kpi(ids),'recommendation':kpi(),
             'shadow':kpi(),'market':kpi(),'actual_purchase':kpi()},
           'races':{r['race_id']:{'mode':'FORWARD','scheduled_post_time_jst':r['scheduled_post_time_jst'],
                      'prediction_history':[],'recommendation_state':'PENDING'} for r in rows}}
    return save(root,day)


def select(root, date, ref):
    day, before = read_day(root,date)
    race = ref.get('race_id'); require(race in day['initial_scope'], 'selection outside initial scope')
    post = day['races'][race]['scheduled_post_time_jst']
    history, _ = verified_artifact(root,ref['selection_ref'],post)
    verified = validate_selection(root,history,{race:post})
    require(any(p['race_id'] == race and p['purpose'] == 'RECOMMENDATION' and p['active']
                for p in verified['plans'].values()), 'selection requires an active recommendation purpose revision')
    if race not in day['selected_scope']: day['selected_scope'].append(race)
    if race not in day['final_scope']: day['unfinished_reasons'][race] = '選定済み・最終工程は未実施'
    day['races'][race]['selection_ref'] = ref['selection_ref']
    return save(root,day,before)


def record_prediction(root,date,entry):
    day,before = read_day(root,date);race = entry.get('race_id')
    require(race in day['initial_scope'], 'prediction outside initial scope')
    row = day['races'][race];phase = entry.get('phase')
    require(phase in {'INITIAL','FINAL'}, 'INITIAL/FINAL phase required')
    require(phase != 'INITIAL' or race not in day['final_scope'], 'INITIAL cannot replace a completed FINAL')
    require(phase != 'FINAL' or race in day['selected_scope'], 'FINAL requires prior selected scope')
    gate = validate_gate(root,safe_path(root,entry.get('prediction_gate_path')))
    require(gate['race_id'] == race and gate['race_date_jst'] == date and gate['manual_release'] == 'v1.7.0',
            'prediction identity/release mismatch')
    row.update(prediction_gate_path=entry['prediction_gate_path'],operations=entry['operations'],
               input_complete=entry['input_complete'],input_gap_reason=entry.get('input_gap_reason'),
               uncertainty_effect=entry.get('uncertainty_effect'),market=entry['market'],data_cutoff=gate['data_cutoff'])
    identity = {'phase':phase,'prediction_gate_path':entry['prediction_gate_path'],
                'prediction_ref':copy.deepcopy(entry['operations']['prediction_ref']),
                'baseline_forecast_id':gate['production']['baseline_forecast_id']}
    if identity not in row['prediction_history']: row['prediction_history'].append(identity)
    set_state(day['kpis']['production'],race,gate['kpi_eligibility']['production'],'保存・独立FIX・入力・対象gateを照合')
    shadow_state = gate['kpi_eligibility']['shadow']
    if gate.get('shadow_items'):
        set_state(day['kpis']['shadow'],race,shadow_state,'該当Shadowの独立状態')
    if phase == 'FINAL':
        row['two_axis_comparison'] = compare_two_axis(gate['production'])
        rec_path = entry.get('recommendation_gate_path')
        require(rec_path, 'FINAL requires recommendation state and independent gate')
        rec = verify_recommendation(root,safe_path(root,rec_path))
        require(rec['race_id'] == race and rec['race_date_jst'] == date, 'recommendation identity mismatch')
        row['recommendation_gate_path'] = rec_path; row['recommendation_state'] = rec['status']
        rec_gate = load(safe_path(root,rec_path))
        set_state(day['kpis']['recommendation'],race,rec_gate['kpi_eligibility'],'固定推奨の独立状態：'+rec['status'])
        if race not in day['final_scope']: day['final_scope'].append(race)
        day['unfinished_reasons'].pop(race,None)
    return save(root,day,before)


def review(root,date,entry):
    day,before = read_day(root,date);race = entry.get('race_id')
    require(race in day['initial_scope'], 'review outside initial scope')
    result_path = safe_path(root,entry.get('result_path'));raw = result_path.read_bytes();result = json.loads(raw)
    require(result.get('race_id') == race and result.get('race_date_jst') == date and result.get('status') == 'OFFICIAL',
            'official result identity required')
    require(iso(result.get('retrieved_at_jst'),'result retrieved') >= iso(day['races'][race]['scheduled_post_time_jst'],'post'),
            'future result used before race')
    analysis = entry.get('review')
    require(isinstance(analysis,dict) and all(analysis.get(k) for k in ('error_classification','non_degradation','next_validation')),
            'review error/non-degradation/next validation required')
    row = day['races'][race]
    if row.get('prediction_gate_path'):
        prediction = validate_gate(root,safe_path(root,row['prediction_gate_path']))
        finished=[h for group in result.get('finish_groups',[]) for h in group]
        other=result.get('non_finishers',[])+result.get('scratched_horses',[])
        require(all(type(h) is int and h>0 for h in finished+other) and
                len(set(finished+other))==len(finished+other) and
                set(finished+other)==set(prediction['production']['ranking']),
                'official full-field result coverage mismatch')
    row['result_ref'] = {'artifact_path':entry['result_path'],'sha256':hashlib.sha256(raw).hexdigest()}
    row['review'] = copy.deepcopy(analysis)
    if race not in day['reviewed_scope']:day['reviewed_scope'].append(race)
    if row.get('recommendation_gate_path'):
        row['recommendation_result'] = settle(verify_recommendation(root,safe_path(root,row['recommendation_gate_path'])),result)
    return save(root,day,before)


def summary(root):
    contract = load(root/CONTRACT_PATH);days=[]
    for p in sorted((root/DIRECTORY).glob('*.json')):days.append(validate_day(root,p,contract))
    result = {'schema_version':'cycle04-operational-summary-v1','manual_release':'v1.7.0',
              'recorded_dates':[d['race_date_jst'] for d in days], 'expected_dates':DATES,
              'initial_races':sum(len(d['initial_scope']) for d in days),
              'reviewed_races':sum(len(d['reviewed_scope']) for d in days),'kpis':{},
              'prediction_performance':{'eligible_reviewed':0,'honmei_win':None,'honmei_top2':None,
                                         'honmei_top3':None,'top3_winner_capture':None,'win_brier':None,'top2_brier':None,'top3_brier':None,'topk_winner_capture':{},'calibration':{} },
              'recommendation_performance':{'eligible_settled':0,'hit_race_rate':None,'valid_tickets':0,'hit_tickets':0},
              'additional_review_metrics':{'status':'PENDING_REVIEW_AGGREGATION','reason':'確信度/変更理由/誤差/非劣化の構造化回顧は独立記録を集計する。未測定は0にしない。'}}
    for name in ('production','recommendation','shadow','market'):
        result['kpis'][name]={field:sum(len(d['kpis'][name][field]) for d in days)
                             for field in ('target_ids','eligible_ids','ineligible_ids','pending_ids')}
    predictions=[];recs=[]
    for day in days:
        for race in day['reviewed_scope']:
            row=day['races'][race];official=load(safe_path(root,row['result_ref']['artifact_path']))
            if race in day['kpis']['production']['eligible_ids']:
                gate=validate_gate(root,safe_path(root,row['prediction_gate_path']))
                prod=gate['production'];groups=official['finish_groups'];position=0;finish={}
                for group in groups:
                    require(isinstance(group,list) and group and all(type(h) is int for h in group),'official finish group invalid')
                    for horse in group:
                        require(horse not in finish,'duplicate official finisher');finish[horse]=position+1
                    position+=len(group)
                ranking=prod['ranking'];anchor=ranking[0]
                require(set(finish) <= set(ranking),'official horse outside fixed prediction')
                win={h for h,p in finish.items() if p==1}
                predictions.append({'win':anchor in win,'top2':finish.get(anchor,999)<=2,'top3':finish.get(anchor,999)<=3,
                    'capture':bool(set(ranking[:3]) & win),'brier':sum((p['win_probability']-int(p['horse_no'] in win))**2 for p in prod['probabilities'])/len(ranking),
                    'top2_brier':sum((p['top2_probability']-int(finish.get(p['horse_no'],999)<=2))**2 for p in prod['probabilities'])/len(ranking),
                    'top3_brier':sum((p['top3_probability']-int(finish.get(p['horse_no'],999)<=3))**2 for p in prod['probabilities'])/len(ranking),
                    'capture_k':{str(k):bool(set(ranking[:k])&win) for k in (1,3,6)},
                    'calibration':{field:[(p[field],int(finish.get(p['horse_no'],999)<=pos)) for p in prod['probabilities']]
                                   for field,pos in [('win_probability',1),('top2_probability',2),('top3_probability',3)]}})
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
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--register-scope',type=Path)
    mode.add_argument('--select',type=Path)
    mode.add_argument('--record-prediction',type=Path)
    mode.add_argument('--review',type=Path)
    mode.add_argument('--summary',action='store_true')
    parser.add_argument('--date')
    args=parser.parse_args(argv)
    try:
        root=args.root.resolve();check_release(root,require_main=True)
        if args.summary:
            print(json.dumps(summary(root),ensure_ascii=False,indent=2));return 0
        if args.register_scope:out=register_scope(root,load(args.register_scope))
        else:
            require(args.date,'race date required')
            if args.select:out=select(root,args.date,load(args.select))
            elif args.record_prediction:out=record_prediction(root,args.date,load(args.record_prediction))
            else:out=review(root,args.date,load(args.review))
        print(f'日別台帳のローカル保存・検査成功：{out}。日次branchへのGit保存・読戻しを行ってください。')
        return 0
    except (ValueError,OSError,KeyError,TypeError) as exc:
        print('第4運用未完了：'+str(exc),file=sys.stderr);return 1


if __name__=='__main__':raise SystemExit(main())
