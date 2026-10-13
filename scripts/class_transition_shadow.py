"""クラス移行の固定例と、保存済み基準/Shadowの同時点比較を読取検査する。"""
import argparse
import hashlib
import json
import math
import re
from datetime import datetime,timezone,timedelta
from pathlib import Path
from class_transition import audit,require,text
from check_prediction_compliance import iso,validate_gate,probability_item,evidence_item
from cycle04_operations import safe_path,verified_artifact,validate_official_result

FIELDS=('win_probability','top2_probability','top3_probability')
DATES=['2026-10-17','2026-10-18','2026-10-24','2026-10-25']


def load(path):return json.loads(Path(path).read_text(encoding='utf-8'))


def fixed_cases(cases):
    require(isinstance(cases,list) and 1<=len(cases)<=3,'固定比較は1バッチ最大3例')
    out=[];seen=set()
    for case in cases:
        require(isinstance(case,dict) and text(case.get('case_id')) and case['case_id'] not in seen,'固定例IDの欠落/重複')
        seen.add(case['case_id']);require(case.get('mode') in {'SYNTHETIC','REPLAY'},'固定例を前向き実測にしない')
        report=audit(case.get('assessment'))
        kind=case.get('kind')
        require(kind in {'RESTRICTED_STAKES_TO_OLDER_OP','MIXED_CLASS_TRANSITION','EXPERIENCED_OR_MISSING'},'固定例の条件区分が必要')
        if kind=='RESTRICTED_STAKES_TO_OLDER_OP':
            require(report['target_class']=='OP' and report['previous_class'] in {'G1','G2','G3'} and 'AGE_RESTRICTED' in report['recent_age_conditions'],'年齢限定重賞実走→OPの条件が必要')
        elif kind=='MIXED_CLASS_TRANSITION':
            require(report['target_age_condition']=='MIXED' and report['class_promotion'] is True and
                    'MIXED' in report['recent_age_conditions'],'混合クラス移行の条件が必要')
        else:require(report['older_encounter_state'] in {'POSITIVE','UNKNOWN'},'既対戦または不明の固定例が必要')
        out.append({'case_id':case['case_id'],'kind':kind,'mode':case['mode'],'assessment':report,
                    'forward_kpi_eligible':False,'non_degradation':'NOT_MEASURED','performance_promotion':'NOT_APPROVED'})
    return out


def probabilities(forecast):
    require(isinstance(forecast,dict),'基準/比較予想が必要')
    ranking=forecast.get('ranking');rows=forecast.get('probabilities')
    require(isinstance(ranking,list) and len(ranking)>=3 and all(type(h) is int and h>0 for h in ranking) and len(set(ranking))==len(ranking),'全頭順位が必要')
    require(isinstance(rows,list) and len(rows)==len(ranking),'全頭確率が必要')
    checked={}
    for row in rows:
        h=probability_item(row,'比較確率')
        require(h not in checked and h in ranking and all(type(row[k]) in (int,float) and math.isfinite(row[k]) for k in FIELDS),'確率重複/未知馬/不正値を拒否')
        checked[h]=row
    for field,total in zip(FIELDS,(1,2,3)):require(abs(math.fsum(r[field] for r in rows)-total)<=1e-6,'全頭確率総和が不正')
    return ranking,checked


def diagnostic_pair(pair,result):
    """形の検算だけでは前向きKPI適格にしない。"""
    require(isinstance(pair,dict) and pair.get('schema_version')=='class-transition-shadow-pair-v1','基準/比較契約が必要')
    require(pair.get('mode') in {'FORWARD','REPLAY','SYNTHETIC'},'比較の実施区分が必要')
    require(text(pair.get('comparison_method_id')) and text(pair.get('change_reason')),'比較方法と変更/据置理由が必要')
    cutoff=iso(pair.get('data_cutoff'),'比較cutoff');post=iso(pair.get('scheduled_post_time_jst'),'発走')
    require(cutoff<post,'事前cutoffが必要')
    baseline=pair.get('baseline');shadow=pair.get('shadow')
    old,op=probabilities(baseline);new,np=probabilities(shadow)
    require(set(old)==set(new),'基準/比較の全馬集合が不一致')
    for forecast in (baseline,shadow):
        require(forecast.get('data_cutoff')==pair['data_cutoff'] and
                forecast.get('common_input_sha256')==pair.get('common_input_sha256') and
                isinstance(forecast.get('common_input_sha256'),str) and len(forecast['common_input_sha256'])==64,'同一cutoff/入力hashが必要')
    assessment=audit(pair.get('assessment'))
    require(assessment['race_id']==pair.get('race_id') and assessment['data_cutoff']==pair['data_cutoff'] and assessment['horse_no'] in old,'比較対象/時点が不一致')
    validate_official_result(result,race=pair.get('race_id'),date=pair.get('race_date_jst'),post=pair['scheduled_post_time_jst'],horses=old)
    if result.get('scratched_horses') or any(len(g)>1 for g in result['finish_groups']):
        return {'status':'NOT_COMPARABLE','reason':'取消後未再固定または同着の比較は別検証','forward_kpi_eligible':False,'metrics':None,'assessment':assessment}
    finish={};position=1
    for group in result['finish_groups']:
        for h in group:finish[h]=position
        position+=len(group)
    winner=result['finish_groups'][0][0]
    def score(ranking,rates):
        values={field:math.fsum((rates[h][field]-int(finish.get(h,999)<=limit))**2 for h in ranking)/len(ranking) for field,limit in zip(FIELDS,(1,2,3))}
        values['anchor_win']=int(ranking[0]==winner)
        for k in (1,3,6):values['top'+str(k)+'_winner_capture']=int(winner in ranking[:k])
        return values
    a=score(old,op);b=score(new,np);delta={k:b[k]-a[k] for k in a}
    worsened=any(delta[k]>1e-12 for k in FIELDS) or any(delta[k]<0 for k in delta if k not in FIELDS)
    improved=any(delta[k]<-1e-12 for k in FIELDS) or any(delta[k]>0 for k in delta if k not in FIELDS)
    return {'status':'DIAGNOSTIC','forward_kpi_eligible':False,'metrics':{'baseline':a,'shadow':b,'delta':delta},
            'paired_observation':'WORSENED' if worsened else 'IMPROVED' if improved else 'NEUTRAL',
            'assessment':assessment,'ranking_changed':old!=new,'performance_promotion':'NOT_APPROVED'}


def verified_pair(root,item,plan,as_of):
    require(isinstance(item,dict),'比較参照はobjectが必要')
    gate=validate_gate(root,safe_path(root,item.get('gate_path')))
    require(gate['mode']=='FORWARD' and gate['race_date_jst'] in plan['race_dates'] and
            gate['kpi_eligibility']['production']=='ELIGIBLE' and gate['kpi_eligibility']['shadow']=='ELIGIBLE','前向きの基準/Shadow保存適格が必要')
    date=gate['race_date_jst'];venue=re.fullmatch('(?:'+date+'|'+date.replace('-','')+')-(TOKYO|KYOTO|NIIGATA|TOK|KYO|NII)-(0[1-9]|1[0-2])',gate['race_id'])
    require(venue is not None,'第4の東京/京都/新潟の対象レースが必要')
    matches=[s for s in gate.get('shadow_items',[]) if s['item_id']==item.get('shadow_item_id') and s['kpi_eligibility']=='ELIGIBLE']
    require(len(matches)==1,'同一Shadow項目を一意に照合する')
    pair,pair_receipt=verified_artifact(root,matches[0]['evidence_ref'],gate['scheduled_post_time_jst'])
    for key in ('race_id','race_date_jst','data_cutoff','scheduled_post_time_jst'):
        require(pair.get(key)==gate[key],'比較gateとの同一性不一致')
    require(pair.get('mode')=='FORWARD' and pair.get('baseline_forecast_id')==gate['production']['baseline_forecast_id'],'Replay/別基準の前向き評価を拒否')
    require(pair.get('comparison_method_id')==plan.get('comparison_method_id'),'試験途中の比較方法変更を拒否')
    ref=gate['production']['evidence_ref']
    prediction_hash=hashlib.sha256(safe_path(root,ref['artifact_path']).read_bytes()).hexdigest()
    _,baseline_receipt=verified_artifact(root,{**ref,'sha256':prediction_hash},gate['scheduled_post_time_jst'])
    require(text(prediction_hash) and pair.get('baseline_prediction_sha256')==prediction_hash,'基準Predictionの固定hash不一致')
    for key in ('ranking','probabilities'):require(pair['baseline'].get(key)==gate['production'][key],'基準予想の値を書き換えない')
    common,common_receipt=verified_artifact(root,pair.get('common_input_ref'),gate['scheduled_post_time_jst'])
    binding,binding_receipt=verified_artifact(root,pair.get('baseline_input_binding_ref'),gate['scheduled_post_time_jst'])
    require(common.get('schema_version')=='class-transition-common-input-v1' and common.get('race_id')==gate['race_id'] and common.get('data_cutoff')==gate['data_cutoff'] and
            pair.get('common_input_sha256')==pair['common_input_ref']['sha256'] and
            pair.get('assessment') in common.get('assessments',[]),'比較の入力原本/対象情報が不一致')
    require(binding.get('schema_version')=='class-transition-input-binding-v1' and binding.get('race_id')==gate['race_id'] and binding.get('data_cutoff')==gate['data_cutoff'] and
            binding.get('baseline_prediction_sha256')==prediction_hash and
            binding.get('common_input_sha256')==pair['common_input_ref']['sha256'],'基準の同一入力利用の事前証跡が必要')
    require(max(iso(common_receipt['receipt_verified_at_jst'],'共通入力読戻し'),iso(baseline_receipt['receipt_verified_at_jst'],'基準読戻し')) <=
            iso(binding_receipt['persist_verified_at_jst'],'binding保存') <=
            iso(binding_receipt['receipt_verified_at_jst'],'binding読戻し') <=
            iso(pair_receipt['persist_verified_at_jst'],'比較保存'),'共通入力/基準/binding/比較の保存順序が逆転')
    for assessment in common['assessments']:
        audited=audit(assessment)
        require(audited['race_id']==gate['race_id'] and audited['data_cutoff']==gate['data_cutoff'] and audited['horse_no'] in pair['baseline']['ranking'],'共通入力内の別対象/未来assessmentを拒否')
    require(isinstance(common.get('other_facts',[]),list),'その他の共通事実は根拠行リストが必要')
    for row in common.get('other_facts',[]):
        require(evidence_item(row,'共通事実',iso(gate['data_cutoff'],'cutoff')) in pair['baseline']['ranking'],'未知馬の共通事実を拒否')
    result=load(safe_path(root,item.get('result_path')))
    require(iso(result.get('retrieved_at_jst'),'結果取得')<=as_of,'評価時点より未来の結果を使わない')
    require(iso(gate['scheduled_post_time_jst'],'発走')<=as_of,'未開催を実測にしない')
    report=diagnostic_pair(pair,result)
    if report['status']=='DIAGNOSTIC' and report['assessment']['input_complete'] and report['assessment']['comparison_sufficiency'] in {'DIRECT','STRONG_SUBSTITUTE'}:
        report.update(status='VERIFIED_PAIR',forward_kpi_eligible=True)
    else:report.update(status='NOT_COMPARABLE',forward_kpi_eligible=False,reason=report.get('reason','入力/比較根拠不足'))
    report['race_id']=gate['race_id'];return report


def collection(root,items,plan,as_of=None):
    require(isinstance(plan,dict) and plan.get('schema_version')=='class-transition-forward-plan-v1' and
            plan.get('race_dates')==DATES and plan.get('venues')==['TOKYO','KYOTO','NIIGATA'] and
            plan.get('sample_policy')=='ALL_APPLICABLE_REQUESTED_RACES','確認済み4開催日の全該当例計画が必要')
    require(isinstance(items,list),'比較参照リストが必要')
    now=iso(as_of,'評価時点') if as_of else datetime.now(timezone.utc)
    accepted=[];excluded=[];seen=set()
    for item in items:
        try:
            report=verified_pair(root,item,plan,now)
            require(report['race_id'] not in seen,'同一レースの比較を重複集計しない');seen.add(report['race_id'])
            (accepted if report['forward_kpi_eligible'] else excluded).append(report)
        except (ValueError,TypeError,KeyError,OSError) as exc:
            excluded.append({'status':'NOT_COMPARABLE','gate_path':item.get('gate_path') if isinstance(item,dict) else None,'reason':str(exc)})
    metrics=None
    if accepted:
        keys=accepted[0]['metrics']['delta'];metrics={k:math.fsum(r['metrics']['delta'][k] for r in accepted)/len(accepted) for k in keys}
    return {'status':'PAIRED_DIAGNOSTICS_CONTINUE_VALIDATION' if accepted else 'WAITING_VERIFIED_FORWARD_DATA',
            'provided_pair_count':len(items),'eligible_pair_count':len(accepted) if items else None,'mean_delta':metrics,
            'paired_reports':accepted,'excluded_reports':excluded,'non_degradation':'NOT_ACCEPTED_OWNER_REVIEW_REQUIRED',
            'performance_promotion':'NOT_APPROVED','period_complete':now.astimezone(timezone(timedelta(hours=9))).date().isoformat()>DATES[-1],
            'sample_coverage_verified':False,'trial_complete':False,
            'calibration':'CONTINUE_VALIDATION','read_only':True}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('manifest',type=Path);parser.add_argument('--root',type=Path,default=Path('.'))
    args=parser.parse_args(argv)
    try:
        data=load(args.manifest)
        output=fixed_cases(data['cases']) if 'cases' in data else collection(args.root,data['items'],data['plan'])
        print(json.dumps(output,ensure_ascii=False,indent=2));return 0
    except (ValueError,TypeError,KeyError,OSError) as exc:
        print('クラス移行Shadowの確認失敗：'+str(exc));return 1


if __name__=='__main__':raise SystemExit(main())
