#!/usr/bin/env python3
"""校正・非劣化のOwner審査へ固定入力を渡す。採用閾値は作らない。"""
import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from chat_forward_coverage import coverage
from chat_result_reconciliation import fixed_json
from check_prediction_compliance import validate_gate
from cycle04_operations import require, safe_path, verified_artifact
from recommendation import verify as verify_recommendation


def export_inputs(root, manifest, as_of=None):
    scope=coverage(root,manifest,as_of)
    rows=[]
    for item in manifest['items']:
        fixed=fixed_json(root,item['gate_ref']);race=fixed['race_id']
        if race not in scope['accepted_ids']:continue
        gate=validate_gate(root,safe_path(root,item['gate_path']))
        matches=[s for s in gate.get('shadow_items',[]) if s['item_id']==item['shadow_item_id']]
        require(len(matches)==1,'unique verified comparison required')
        pair,_=verified_artifact(root,matches[0]['evidence_ref'],gate['scheduled_post_time_jst'])
        result=fixed_json(root,item['result_ref'])
        report=next(r for r in scope['collection']['paired_reports'] if r['race_id']==race)
        ranking=pair['baseline']['ranking']
        # 比較時点の固定phaseを優先。最新のFINAL推奨をINITIAL比較へ逆流させない。
        binding=scope.get('submitted_pair_bindings',{}).get(race)
        require(isinstance(binding,dict) and binding.get('phase') in {'INITIAL','FINAL'} and
                binding.get('prediction_gate_sha256')==item['gate_ref']['sha256'] and
                binding.get('data_cutoff')==pair['data_cutoff'] and
                binding.get('baseline_forecast_id')==pair['baseline_forecast_id'] and
                binding.get('shadow_item_id')==item['shadow_item_id'],
                'calibration pair differs from fixed phase/baseline/cutoff')
        recommendation=None
        recommendation_binding_status='DIFFERENT_PHASE' if binding['phase']=='INITIAL' else 'NOT_RECORDED'
        for dayref in manifest['days']:
            day=fixed_json(root,dayref)
            if race not in day['races']:continue
            path=day['races'][race].get('recommendation_gate_path')
            if not path or binding['phase']!='FINAL':continue
            require(recommendation is None,'duplicate fixed recommendation race')
            rec=verify_recommendation(root,safe_path(root,path))
            require(rec['phase']=='FINAL' and rec['race_id']==race and
                    rec['data_cutoff']==pair['data_cutoff'] and
                    rec['prediction_ref']['baseline_forecast_id']==pair['baseline_forecast_id'],
                    'recommendation comparison cutoff/phase/baseline differs')
            production_ref=gate['production']['evidence_ref']
            # 双方のvalidatorがそれぞれhash/ID/receiptを検査済み。
            # gateのevidence_refと推奨のprediction_refでは補助キーの構成が異なる。
            require(rec['prediction_ref']['artifact_path']==production_ref['artifact_path'],
                    'recommendation prediction differs from fixed phase')
            recommendation={'status':rec['status'],'tickets':rec.get('tickets',[]),
                            'ticket_count':len(rec.get('tickets',[])),
                            'dependency_input':rec.get('dependency_audit'),
                            'recommendation_id':rec['recommendation_id']}
            recommendation_binding_status='MATCHED_FINAL'
        rates={kind:{r['horse_no']:r for r in pair[kind]['probabilities']} for kind in ('baseline','shadow')}
        positions={};position=1
        for group in result['finish_groups']:
            for horse in group:positions[horse]=position
            position+=len(group)
        observations=[]
        for horse in ranking:
            observations.append({'horse_no':horse,
                'baseline':{k:rates['baseline'][horse][k] for k in ('win_probability','top2_probability','top3_probability')},
                'shadow':{k:rates['shadow'][horse][k] for k in ('win_probability','top2_probability','top3_probability')},
                'outcomes':{k:int(positions.get(horse,999)<=n) for k,n in [('win_probability',1),('top2_probability',2),('top3_probability',3)]}})
        a=report['assessment']
        rows.append({'race_id':race,'race_date_jst':pair['race_date_jst'],
            'comparison_phase':binding['phase'] if binding else None,
            'data_cutoff':pair['data_cutoff'],
            'baseline_forecast_id':pair['baseline_forecast_id'],'common_input_sha256':pair['common_input_sha256'],
            'fixed_refs':{'gate':item['gate_ref'],'result':item['result_ref'],'pair':matches[0]['evidence_ref']},
            'stratum':{k:a[k] for k in ('target_class','target_age_condition','older_encounter_state','class_promotion','comparison_sufficiency')},
            'horse_observations':observations,'paired_metrics':report['metrics'],
            'recommendation_input':recommendation,'recommendation_binding_status':recommendation_binding_status})
    strata=defaultdict(list)
    for row in rows:strata[json.dumps(row['stratum'],sort_keys=True)].append(row)
    summary=[]
    for key,group in sorted(strata.items()):
        summary.append({'stratum':json.loads(key),'pair_count':len(group),
            'mean_delta':{k:math.fsum(r['paired_metrics']['delta'][k] for r in group)/len(group)
                          for k in group[0]['paired_metrics']['delta']}})
    return {'schema_version':'chat-calibration-review-input-v1','coverage':scope,'pairs':rows,
            'pair_count':len(rows) if scope['initial_scope'] else None,'strata':summary,
            'mean_delta':scope['collection']['mean_delta'] if rows else None,
            'owner_review_ready':scope['sample_coverage_verified'] and bool(rows),
            'calibration':'NOT_ACCEPTED','non_degradation':'OWNER_REVIEW_REQUIRED',
            'performance_promotion':'NOT_APPROVED','probability_lower_bound':None,
            'new_threshold':None,'market_roi':None,'historical_purchase_roi':None,'read_only':True}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('manifest',type=Path)
    p.add_argument('--root',type=Path,default=Path('.'));p.add_argument('--as-of');args=p.parse_args(argv)
    try:
        print(json.dumps(export_inputs(args.root,json.loads(args.manifest.read_text()),args.as_of),ensure_ascii=False,indent=2));return 0
    except (ValueError,TypeError,KeyError,OSError) as exc:
        print('校正審査入力の出力保留：'+str(exc));return 1


if __name__=='__main__':raise SystemExit(main())
