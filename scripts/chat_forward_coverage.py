#!/usr/bin/env python3
"""初回依頼全件と事前assessment・提出ペアを読取集合照合する。"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from chat_result_reconciliation import fixed_json
from class_transition import audit
from class_transition_shadow import DATES, collection
from check_prediction_compliance import iso, validate_gate
from cycle04_workflow import read_day
from cycle04_operations import require, safe_path, verified_artifact


def applicability(report):
    flags=[report['class_promotion']]
    if report['first_older_encounter_applicability']=='THREE_YEAR_OLD':
        flags.append(report['first_older_encounter'])
    restricted=report['previous_class'] in {'G1','G2','G3'} and report['target_class']=='OP' and 'AGE_RESTRICTED' in report['recent_age_conditions']
    flags.append(restricted)
    if any(x is True for x in flags):return 'APPLICABLE'
    if not report['input_complete'] or any(x is None for x in flags):return 'UNKNOWN'
    return 'NOT_APPLICABLE'


def coverage(root, manifest, as_of=None):
    require(isinstance(manifest,dict) and set(manifest)=={'plan','days','assessments','items'}, 'coverage manifest fields invalid')
    now=iso(as_of,'coverage time') if as_of else datetime.now(timezone.utc)
    days=manifest['days'];assessments=manifest['assessments'];items=manifest['items']
    require(isinstance(days,list) and isinstance(assessments,list) and isinstance(items,list), 'explicit coverage lists required')
    scope={};dates=[]
    for ref in days:
        fixed=fixed_json(root,ref);date=fixed.get('race_date_jst')
        require(date in DATES and date not in dates and ref['artifact_path']=='docs/validation/records/cycle_04/'+date+'.json',
                'unique existing cycle04 day required')
        day,_=read_day(root,date);require(day==fixed,'day changed during coverage audit');dates.append(date)
        for race in day['initial_scope']:
            require(race not in scope,'duplicate initial-scope race')
            row=day['races'][race]
            require(row['mode']=='FORWARD','REPLAY/synthetic scope is outside actual coverage')
            scope[race]={'day':day,'row':row}
    require(set(scope) or not assessments and not items,'assessments/pairs cannot invent an initial scope')
    by_race={}
    for entry in assessments:
        require(isinstance(entry,dict) and set(entry)=={'race_id','assessment_ref'}, 'assessment binding fields invalid')
        race=entry['race_id'];require(race in scope and race not in by_race,'unknown/duplicate assessment race')
        row=scope[race]['row'];gate_path=row.get('prediction_gate_path')
        require(gate_path,'assessment cannot classify an absent fixed prediction')
        gate=validate_gate(root,safe_path(root,gate_path))
        data,receipt=verified_artifact(root,entry['assessment_ref'],row['scheduled_post_time_jst'])
        require(iso(receipt['receipt_verified_at_jst'],'assessment readback')<=iso(gate['data_cutoff'],'cutoff') and
                iso(receipt['receipt_verified_at_jst'],'assessment readback')<=now,'assessment must exist by fixed cutoff/current time')
        require(data.get('schema_version')=='chat-forward-assessments-v1' and data.get('race_id')==race and
                data.get('data_cutoff')==gate['data_cutoff'] and data.get('mode')=='FORWARD', 'fixed forward assessment identity required')
        rows=data.get('assessments')
        require(isinstance(rows,list) and len(rows)==len(gate['production']['ranking']) and
                {a.get('horse_no') for a in rows}==set(gate['production']['ranking']), 'all-horse assessment scope required')
        reports=[audit(a) for a in rows]
        require(all(a['race_id']==race and a['data_cutoff']==gate['data_cutoff'] for a in reports),'assessment race/cutoff mismatch')
        states=[applicability(a) for a in reports]
        state='APPLICABLE' if 'APPLICABLE' in states else 'UNKNOWN' if 'UNKNOWN' in states else 'NOT_APPLICABLE'
        by_race[race]={'state':state,'horse_states':{a['horse_no']:s for a,s in zip(reports,states)},
                      'assessment_ref':entry['assessment_ref'],'audited_assessments':reports}
    classified={race:by_race.get(race,{'state':'UNKNOWN','reason':'全頭事前assessment未確認'}) for race in scope}
    applicable={r for r,v in classified.items() if v['state']=='APPLICABLE'}
    submitted=set();clean=[]
    for item in items:
        require(isinstance(item,dict) and 'gate_ref' in item and 'result_ref' in item,'frozen pair gate/result hashes required')
        fixed=fixed_json(root,item['gate_ref']);race=fixed.get('race_id')
        require(race in applicable and race not in submitted,'unknown/nonapplicable/duplicate pair cannot be selected')
        require(item['gate_path']==item['gate_ref']['artifact_path']==scope[race]['row'].get('prediction_gate_path'),'pair gate differs from initial-scope original')
        result=fixed_json(root,item['result_ref'])
        require(item['result_path']==item['result_ref']['artifact_path'] and result.get('race_id')==race,'result reference mismatch')
        submitted.add(race);clean.append({k:v for k,v in item.items() if k not in {'gate_ref','result_ref'}})
    report=collection(root,clean,manifest['plan'],as_of)
    for pair_report in report['paired_reports']:
        require(pair_report['assessment'] in classified[pair_report['race_id']]['audited_assessments'],
                'submitted pair assessment differs from predeclared all-horse assessment')
    accepted={r['race_id'] for r in report['paired_reports']}
    unknown={r for r,v in classified.items() if v['state']=='UNKNOWN'}
    missing=applicable-accepted
    verified=bool(scope) and not unknown and not missing and not report['excluded_reports']
    return {'schema_version':'chat-forward-coverage-v1','initial_scope':sorted(scope),'classification':classified,
            'applicable_ids':sorted(applicable),'submitted_ids':sorted(submitted),'accepted_ids':sorted(accepted),
            'missing_ids':sorted(missing),'unknown_ids':sorted(unknown),
            'not_applicable_ids':sorted(r for r,v in classified.items() if v['state']=='NOT_APPLICABLE'),
            'sample_coverage_verified':verified,'all_planned_days_present':set(dates)==set(DATES),
            'eligible_pair_count':len(accepted) if scope else None,'collection':report,
            'trial_complete':False,'performance_promotion':'NOT_APPROVED','read_only':True}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('manifest',type=Path)
    p.add_argument('--root',type=Path,default=Path('.'));p.add_argument('--as-of');args=p.parse_args(argv)
    try:
        print(json.dumps(coverage(args.root,json.loads(args.manifest.read_text()),args.as_of),ensure_ascii=False,indent=2));return 0
    except (ValueError,TypeError,KeyError,OSError) as exc:
        print('前向き対象網羅の照合保留：'+str(exc));return 1


if __name__=='__main__':raise SystemExit(main())
