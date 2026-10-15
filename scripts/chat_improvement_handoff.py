#!/usr/bin/env python3
"""回顧から改善候補の採否・不足・保護対象・Owner・次試験を引継ぐ。"""
import argparse
import copy
import json
import re
from pathlib import Path
from chat_result_reconciliation import fixed_json
from cycle04_operations import require


STATES={'ADOPTION_CANDIDATE','CONTINUE_VALIDATION','REJECTED','DEFERRED'}


def pointer(data, value):
    require(isinstance(value,str) and value.startswith('/') and value!='/', 'explicit evidence JSON pointer required')
    node=data
    for token in value[1:].split('/'):
        token=token.replace('~1','/').replace('~0','~')
        if isinstance(node,list):
            require(re.fullmatch(r'0|[1-9]\d*',token) is not None and int(token)<len(node),'evidence index missing')
            node=node[int(token)]
        else:
            require(isinstance(node,dict) and token in node,'evidence pointer missing');node=node[token]
    return node


def handoff(root, request):
    require(isinstance(request,dict) and set(request)=={'review_package_ref','calibration_input_ref','candidates'},
            'explicit fixed review references/candidates required')
    package=fixed_json(root,request['review_package_ref'])
    require(package.get('schema_version')=='chat-review-package-v1' and package.get('read_only') is True,
            'review package required')
    calibration=None
    if request['calibration_input_ref'] is not None:
        calibration=fixed_json(root,request['calibration_input_ref'])
        require(calibration.get('schema_version')=='chat-calibration-review-input-v1' and calibration.get('read_only') is True,
                'calibration review input required; no performance promotion')
    candidates=request['candidates']
    require(isinstance(candidates,list),'explicit improvement candidate list required')
    out=[];seen=set()
    for candidate in candidates:
        require(isinstance(candidate,dict) and set(candidate)=={
            'candidate_id','title','status','owner','rationale','evidence','missing','protected_good_parts','next_test'},
                'improvement candidate fields invalid; direct update instructions are outside this handoff')
        ident=candidate['candidate_id']
        require(isinstance(ident,str) and re.fullmatch(r'[A-Za-z0-9_-]{1,80}',ident) and ident not in seen,
                'unique candidate ID required');seen.add(ident)
        require(candidate['status'] in STATES,'unsupported review disposition')
        require(all(isinstance(candidate[k],str) and candidate[k].strip()
                    for k in ('title','owner','rationale','next_test')),'title/owner/rationale/next test required')
        require(all(isinstance(candidate[k],list) and all(isinstance(v,str) and v.strip() for v in candidate[k])
                    for k in ('missing','protected_good_parts')) and candidate['protected_good_parts'],
                'explicit missing list and protected good parts required')
        evidence=candidate['evidence']
        require(isinstance(evidence,list) and evidence,'fixed review evidence required for every disposition')
        resolved=[]
        for ref in evidence:
            require(isinstance(ref,dict) and set(ref)=={'source','pointer','claim'} and isinstance(ref['claim'],str) and ref['claim'].strip(),
                    'evidence reference/claim required')
            require(ref['source'] in {'REVIEW_PACKAGE','CALIBRATION_INPUT'},'unsupported evidence source')
            source=package if ref['source']=='REVIEW_PACKAGE' else calibration
            require(source is not None,'calibration evidence unavailable')
            value=pointer(source,ref['pointer'])
            resolved.append({**ref,'fixed_source_ref':request['review_package_ref'] if ref['source']=='REVIEW_PACKAGE'
                             else request['calibration_input_ref'],'value':value})
        out.append({**copy.deepcopy(candidate),'resolved_evidence':resolved,
                    'approval':'HUMAN_OWNER_REVIEW_REQUIRED','automatic_adoption':False,
                    'non_degradation':'SEPARATE_REVIEW_REQUIRED','implementation_pr':'SEPARATE_PR_REQUIRED'})
    return {'schema_version':'chat-improvement-handoff-v1','review_package_ref':request['review_package_ref'],
            'calibration_input_ref':request['calibration_input_ref'],'candidates':out,'read_only':True,
            'cycle_completion':copy.deepcopy(package.get('cycle_completion')),
             'review_owner_gaps':copy.deepcopy((package.get('cycle_completion') or {}).get('review_owner_gaps', [])),
             'independent_review_metrics':copy.deepcopy(package.get('independent_review_metrics')),
            'closure_review':'HUMAN_OWNER_REVIEW_REQUIRED',
            'manual_updated':False,'prediction_original_updated':False,'database_updated':False,
            'performance_promotion':'NOT_APPROVED'}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('request',type=Path)
    p.add_argument('--root',type=Path,default=Path('.'));args=p.parse_args(argv)
    try:
        print(json.dumps(handoff(args.root,json.loads(args.request.read_text())),ensure_ascii=False,indent=2));return 0
    except (ValueError,TypeError,KeyError,OSError) as exc:
        print('改善候補引継ぎ保留：'+str(exc));return 1


if __name__=='__main__':raise SystemExit(main())
