#!/usr/bin/env python3
"""初回依頼全件を固定参照から非UI回顧資料へまとめる。"""
import argparse
import copy
import json
from pathlib import Path
from chat_result_reconciliation import fixed_json
from check_prediction_compliance import validate_gate, iso
from cycle04_workflow import read_day
from cycle04_operations import require, safe_path, verified_artifact, validate_official_result, validate_formal_result
from recommendation import verify as verify_recommendation, settle


def package(root, manifest, as_of):
    require(isinstance(manifest,dict) and set(manifest)=={'day_refs','historical_purchase_refs'},'review manifest fields invalid')
    now=iso(as_of,'review time');rows=[];days=set();seen=set();kpis=[];shadow_pairs=[];pair_keys=set()
    require(isinstance(manifest['day_refs'],list) and isinstance(manifest['historical_purchase_refs'],list),'explicit reference lists required')
    for ref in manifest['day_refs']:
        fixed=fixed_json(root,ref);date=fixed.get('race_date_jst')
        require(date not in days and ref['artifact_path']=='docs/validation/records/cycle_04/'+str(date)+'.json','unique frozen day required')
        day,_=read_day(root,date);require(day==fixed,'day changed during review');days.add(date)
        kpis.append({'day_ref':ref,'race_date_jst':date,'independent_kpis':copy.deepcopy(day['kpis'])})
        for race in day['initial_scope']:
            require(race not in seen,'duplicate review race');seen.add(race);row=day['races'][race]
            out={'race_id':race,'race_date_jst':date,'scheduled_post_time_jst':row['scheduled_post_time_jst'],
                 'day_ref':ref,'selected':race in day['selected_scope'],'finalized':race in day['final_scope'],
                 'reviewed':race in day['reviewed_scope'],'unfinished_reason':day['unfinished_reasons'].get(race),
                 'recommendation_state':row.get('recommendation_state','PENDING'),
                 'input_complete':row.get('input_complete'),'input_gap_reason':row.get('input_gap_reason'),
                 'uncertainty_effect':row.get('uncertainty_effect'),'review':copy.deepcopy(row.get('review')),
                 'prediction':None,'result':None,'recommendation_result':None,
                  'shadow_history':copy.deepcopy(row.get('shadow_history',[])),
                  'shadow_history_gaps':[],'shadow_comparisons':[]}
            if row.get('prediction_gate_path'):
                history=row.get('prediction_history',[])
                matches=[h for h in history if h['prediction_gate_path']==row['prediction_gate_path']]
                require(bool(matches),'fixed prediction history required')
                fixed_gate=fixed_json(root,{'artifact_path':row['prediction_gate_path'],'sha256':matches[-1]['prediction_gate_sha256']})
                gate=validate_gate(root,safe_path(root,row['prediction_gate_path']))
                require(gate==fixed_gate,'prediction changed during review')
                original,receipt=verified_artifact(root,matches[-1]['prediction_ref'],gate['scheduled_post_time_jst'])
                require(iso(receipt['receipt_verified_at_jst'],'prediction receipt')<=now,'prediction evidence is from future')
                tracked=out['shadow_history']
                out['shadow_history_gaps']=[
                    h['phase'] for h in history[:len(history)-len(tracked)]]
                for shadow in tracked:
                    for item in shadow['items']:
                        pair_key=[race,shadow['phase'],shadow['prediction_gate_sha256'],
                                  shadow['baseline_forecast_id'],shadow['data_cutoff'],item['item_id']]
                        require(tuple(pair_key) not in pair_keys,'duplicate fixed shadow comparison')
                        pair_keys.add(tuple(pair_key))
                        comparison={'comparison_key':pair_key,'race_id':race,
                            'phase':shadow['phase'],'prediction_gate_path':shadow['prediction_gate_path'],
                            'prediction_gate_sha256':shadow['prediction_gate_sha256'],
                            'baseline_forecast_id':shadow['baseline_forecast_id'],
                            'data_cutoff':shadow['data_cutoff'],
                            'item':copy.deepcopy(item),'kpi_state':shadow['kpi_state'],
                            'applicability':copy.deepcopy(shadow['applicability'])}
                        out['shadow_comparisons'].append(comparison)
                        shadow_pairs.append(copy.deepcopy(comparison))
                out['prediction']={'data_cutoff':gate['data_cutoff'],'baseline_forecast_id':gate['production']['baseline_forecast_id'],
                    'fixed_ref':matches[-1]['prediction_ref'],'gate_sha256':matches[-1]['prediction_gate_sha256'],
                    'ranking':gate['production']['ranking'],'probabilities':gate['production']['probabilities'],
                    'history':copy.deepcopy(history),'mode':gate['mode']}
                require(original.get('ranking')==gate['production']['ranking'] and original.get('probabilities')==gate['production']['probabilities'],
                        'prediction original differs')
            if row.get('result_ref'):
                result=fixed_json(root,row['result_ref'])
                require(iso(result['retrieved_at_jst'],'result retrieval')<=now,'future result cannot enter review')
                validate_official_result(result,race=race,date=date,post=row['scheduled_post_time_jst'],
                                        horses=out['prediction']['ranking'] if out['prediction'] else None)
                audit=validate_formal_result(root,row,race=race,date=date,result_ref=row['result_ref'],
                                             manifest_ref=row.get('result_reconciliation_ref'))
                out['result']={'fixed_ref':row['result_ref'],
                               'reconciliation_ref':row['result_reconciliation_ref'],
                               'official_result':result,'text_reconciliation':'MATCHED_FORWARD_FIXED',
                               'diagnostic_formal_kpi_certified':audit['formal_kpi_certified']}
                if row.get('recommendation_gate_path'):
                    rec=verify_recommendation(root,safe_path(root,row['recommendation_gate_path']))
                    out['recommendation_result']=settle(rec,result)
            analysis=row.get('review') if isinstance(row.get('review'),dict) else {}
            out['error_classification']=analysis.get('error_classification')
            out['protected_good_parts']=analysis.get('protected_good_parts')
            out['non_degradation_review']=analysis.get('non_degradation')
            out['next_validation']=analysis.get('next_validation')
            out['missing_review_fields']=[key for key in ('error_classification','protected_good_parts','non_degradation','next_validation')
                                          if not analysis.get(key)]
            rows.append(out)
    history=[{'fixed_ref':ref,'diagnostic':fixed_json(root,ref),'formal_cycle04_kpi_eligible':False}
             for ref in manifest['historical_purchase_refs']]
    return {'schema_version':'chat-review-package-v1','as_of':as_of,'initial_scope_count':len(rows) if days else None,
            'races':rows,'independent_kpis_by_day':kpis,'shadow_comparisons_by_fixed_phase':shadow_pairs,
             'historical_purchase_diagnostics':history,
            'read_only':True,'external_ai_api_executed':False,'formal_kpi_certified':False,
            'performance_promotion':'NOT_APPROVED'}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('manifest',type=Path)
    p.add_argument('--root',type=Path,default=Path('.'));p.add_argument('--as-of',required=True);args=p.parse_args(argv)
    try:
        print(json.dumps(package(args.root,json.loads(args.manifest.read_text()),args.as_of),ensure_ascii=False,indent=2));return 0
    except (ValueError,TypeError,KeyError,OSError) as exc:
        print('非UI回顧資料の生成保留：'+str(exc));return 1


if __name__=='__main__':raise SystemExit(main())
