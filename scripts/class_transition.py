"""初古馬対戦・昇級・比較根拠を別々に照合する準備用読取監査。"""
import argparse
import json
import math
from pathlib import Path
from check_prediction_compliance import ComplianceError, iso


def require(ok, reason):
    if not ok:raise ComplianceError(reason)


def text(value):
    return isinstance(value,str) and bool(value.strip())


def fact(item, cutoff, label, valid):
    require(isinstance(item,dict) and item.get('status') in {'ACQUIRED','MISSING'},label+'：取得/不足の明示が必要')
    require(text(item.get('reason')),label+'：理由が必要')
    if item['status']=='MISSING':
        require(item.get('value') is None,label+'：不足はnullが必要')
        return None
    require(valid(item.get('value')) and text(item.get('source_ref')),label+'：値と出所が必要')
    require(iso(item.get('observed_at_jst'),label+'観測') <=
            iso(item.get('acquired_at_jst'),label+'取得') <= cutoff,label+'：未来/逆順の証拠を拒否')
    return item['value']


def audit(data):
    require(isinstance(data,dict) and data.get('schema_version')=='class-transition-assessment-v1','準備用入力契約が必要')
    cutoff=iso(data.get('data_cutoff'),'cutoff')
    require(text(data.get('race_id')),'対象レースIDが必要')
    require(type(data.get('horse_no')) is int and data['horse_no']>0 and
            type(data.get('horse_age')) is int and data['horse_age']>=2,'馬番号/年齢が必要')
    target=data.get('target');require(isinstance(target,dict),'対象条件が必要')
    count_valid=lambda x:type(x) is int and x>=0
    weight_valid=lambda x:type(x) in (int,float) and math.isfinite(x) and x>0
    age_valid=lambda x:isinstance(x,str) and x in {'AGE_RESTRICTED','MIXED'}
    bool_valid=lambda x:type(x) is bool
    gaps=[]
    def get(item,label,valid):
        value=fact(item,cutoff,label,valid)
        if value is None:gaps.append(label)
        return value
    age=get(target.get('age_condition'),'対象年齢条件',age_valid)
    older_present=get(target.get('older_horses_present'),'対象古馬出走',bool_valid)
    current_class=get(target.get('class'),'対象クラス',text)
    weight=get(target.get('carried_weight_kg'),'対象斤量',weight_valid)
    if data['horse_age']==3 and age=='AGE_RESTRICTED':
        require(older_present is not True,'3歳限定と古馬出走が矛盾')
    total=get(data.get('prior_start_count'),'全過去走数',count_valid)
    encounters=data.get('older_encounters')
    older_count=get(encounters,'古馬既対戦数',count_valid)
    if older_count is not None:
        require(encounters.get('coverage')=='ALL_PRIOR_STARTS','近5走だけで全過去の既対戦数を確定しない')
        require(total is not None and older_count<=total,'古馬既対戦数と全過去走数が矛盾/不足')
    promoted=get(data.get('class_promotion'),'昇級判定',bool_valid)
    previous_class=get(data.get('previous_class'),'前走クラス',text)
    if promoted is not None:
        require(current_class is not None and previous_class is not None,'昇級判定には前走/対象クラスが必要')
        require(not promoted or previous_class!=current_class,'同じクラスを昇級としない')
    runs=get(data.get('recent_five_runs'),'近5走',lambda x:isinstance(x,list) and len(x)<=5)
    run_ids={};known_older=0;conditions=[];classes=[];weights=[];levels=[];times=[]
    for run in runs or []:
        require(isinstance(run,dict) and text(run.get('run_id')) and run['run_id'] not in run_ids and text(run.get('source_ref')),'近5走のID/出所/重複を検査')
        at=iso(run.get('race_at_jst'),'過去走時刻');require(at<=cutoff,'未来の出走を過去走へ使わない')
        require(type(run.get('horse_age')) is int and run['horse_age']>=2,'過去走時点の年齢が必要')
        require(at<=iso(data['recent_five_runs']['observed_at_jst'],'近5走確認'),'近5走確認より後の実走を入れない')
        times.append(at);run_ids[run['run_id']]=run
        condition=get(run.get('age_condition'),'過去走年齢条件',age_valid)
        encountered=get(run.get('older_horses_encountered'),'過去走古馬対戦',bool_valid)
        require(not(condition=='AGE_RESTRICTED' and run.get('horse_age')==3 and encountered is True),'3歳限定と古馬対戦が矛盾')
        known_older+=encountered is True
        conditions.append(condition);classes.append(get(run.get('class'),'過去走クラス',text))
        weights.append(get(run.get('carried_weight_kg'),'過去走斤量',weight_valid))
        levels.append(get(run.get('opponent_level'),'過去走相手レベル',text))
        for field in ('age_condition','older_horses_encountered','class','carried_weight_kg','opponent_level'):
            item=run[field]
            if item['status']=='ACQUIRED':require(at<=iso(item['observed_at_jst'],field+'観測'),'出走前に実走情報を取得したことにしない')
    require(times==sorted(set(times),reverse=True),'近5走の時刻重複/順序不正')
    if runs is not None and total is not None:require(len(runs)==min(5,total),'利用可能な近5走を網羅する')
    if runs and previous_class is not None and classes[0] is not None:require(previous_class==classes[0],'前走クラスと近5走原本が不一致')
    if older_count is not None:require(older_count>=known_older,'全過去既対戦数が近5走の確認件数より少ない')
    if times:
        if total is not None:require(max(times)<=iso(data['prior_start_count']['observed_at_jst'],'全過去走確認'),'全過去走数の確認時点が古い')
        if older_count is not None:require(max(times)<=iso(encounters['observed_at_jst'],'既対戦確認'),'既対戦数の確認時点が古い')
    first=None
    if data['horse_age']==3:
        if age=='AGE_RESTRICTED' or older_present is False:first=False
        elif age=='MIXED' and older_present is True and older_count is not None:first=older_count==0
    evidence=data.get('comparison_evidence');require(isinstance(evidence,list),'比較根拠を空リストでも明示する')
    checked=[];seen=set()
    for item in evidence:
        require(isinstance(item,dict) and text(item.get('evidence_id')) and item['evidence_id'] not in seen,'比較根拠IDの欠落/重複')
        seen.add(item['evidence_id']);kind=item.get('kind')
        require(kind in {'DIRECT','STRONG_SUBSTITUTE','REFERENCE'},'比較根拠区分が必要')
        require(text(item.get('source_ref')) and text(item.get('claim')) and text(item.get('limitations')),'比較根拠の出所/説明/限界が必要')
        require(iso(item.get('evidence_at_jst'),'根拠時刻')<=iso(item.get('observed_at_jst'),'根拠観測')<=iso(item.get('acquired_at_jst'),'根拠取得')<=cutoff,'比較根拠に未来/逆順情報がある')
        dimensions=item.get('comparison_dimensions',[])
        require(isinstance(dimensions,list) and all(isinstance(x,str) for x in dimensions) and len(set(dimensions))==len(dimensions) and set(dimensions).issubset({'CLASS','AGE_CONTEXT','WEIGHT'}),'比較軸が不正')
        qualified=(current_class is not None and item.get('target_class')==current_class and weight is not None and age is not None and older_present is not None and set(dimensions)=={'CLASS','AGE_CONTEXT','WEIGHT'})
        if kind=='DIRECT':
            ref=item.get('run_id');require(ref in run_ids,'直接比較は確認済み実走へ参照する')
            require(iso(item['evidence_at_jst'],'直接根拠時刻')>=iso(run_ids[ref]['race_at_jst'],'実走時刻'),'実走前の直接比較証拠を拒否')
            index=list(run_ids).index(ref)
            qualified=qualified and classes[index] is not None and levels[index] is not None and weights[index] is not None and conditions[index] is not None and run_ids[ref]['older_horses_encountered']['status']=='ACQUIRED'
            relation=item.get('class_relation')
            higher=False
            if relation is not None:
                relation_value=fact(relation,cutoff,'直接実走のクラス比較',lambda x:isinstance(x,str) and x in {'SAME','HIGHER','LOWER'})
                require(relation_value!='SAME' or classes[index]==current_class,'同一クラスという直接比較と原本が矛盾')
                require(relation_value not in {'HIGHER','LOWER'} or classes[index]!=current_class,'異なるクラス水準という比較と原本が矛盾')
                higher=relation_value=='HIGHER'
            qualified=qualified and (classes[index]==current_class or higher)
            if relation is not None and relation.get('value')=='LOWER':qualified=False
            if older_present is True:qualified=qualified and run_ids[ref]['older_horses_encountered']['value'] is True
        if kind=='STRONG_SUBSTITUTE':qualified=qualified and text(item.get('comparison_method'))
        checked.append({'evidence_id':item['evidence_id'],'submitted_kind':kind,'qualified':bool(qualified) if kind!='REFERENCE' else False})
    direct=any(x['submitted_kind']=='DIRECT' and x['qualified'] for x in checked)
    substitute=any(x['submitted_kind']=='STRONG_SUBSTITUTE' and x['qualified'] for x in checked)
    sufficiency='DIRECT' if direct else 'STRONG_SUBSTITUTE' if substitute else 'REFERENCE' if checked else 'NOT_COMPARABLE'
    return {'race_id':data['race_id'],'horse_no':data['horse_no'],'data_cutoff':data['data_cutoff'],
            'older_encounter_count':older_count,'older_encounter_state':'UNKNOWN' if older_count is None else 'ZERO' if older_count==0 else 'POSITIVE',
            'first_older_encounter':first,'class_promotion':promoted,'previous_class':previous_class,'target_class':current_class,
            'target_age_condition':age,'older_horses_present':older_present,'target_weight_kg':weight,
            'recent_age_conditions':conditions,'recent_classes':classes,'recent_weights_kg':weights,'recent_opponent_levels':levels,
            'comparison_sufficiency':sufficiency,'evidence_checks':checked,'missing_fields':sorted(set(gaps)),
            'input_complete':not gaps,'evidence_authentication':False,'production_changed':False,'blanket_age_penalty':False,
            'performance_promotion':'NOT_APPROVED','mode':'PREPARATION_READ_ONLY'}


def describe(report):
    labels={'DIRECT':'直接比較','STRONG_SUBSTITUTE':'強い代替証拠','REFERENCE':'参考','NOT_COMPARABLE':'比較不能'}
    state=lambda x:'不明' if x is None else '該当' if x else '非該当'
    return {'古馬既対戦数':'不明' if report['older_encounter_count'] is None else report['older_encounter_count'],
            '3歳初古馬対戦':state(report['first_older_encounter']),'昇級':state(report['class_promotion']),
            '比較根拠の充足':labels[report['comparison_sufficiency']],'不足項目':report['missing_fields'],
            '証拠の扱い':'提出根拠の構造・時点確認。真偽・効果・校正の認証ではない'}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('path',type=Path)
    args=parser.parse_args(argv)
    try:
        print(json.dumps(describe(audit(json.loads(args.path.read_text(encoding='utf-8')))),ensure_ascii=False,indent=2));return 0
    except (ValueError,TypeError,KeyError,OSError) as exc:
        print('クラス移行の照合失敗：'+str(exc));return 1


if __name__=='__main__':raise SystemExit(main())
