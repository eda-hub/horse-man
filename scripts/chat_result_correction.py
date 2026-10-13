#!/usr/bin/env python3
"""訂正を旧結果・回顧・KPIの上書きなしで別履歴へ引き継ぐ。"""
import argparse
import json
import os
import re
import tempfile
from pathlib import Path
from chat_result_reconciliation import fixed_json, audit_saved
from chat_result_conversion import result_quote
from check_prediction_compliance import iso
from cycle04_operations import require, fingerprint, safe_path


def correction(root, request, as_of=None):
    require(isinstance(request,dict) and set(request)=={
        'correction_id','old_refs','new_refs','old_review_ref','old_kpi_ref',
        'previous_correction_ref','reason','owner','correction_quotation'}, 'correction request fields invalid')
    ident=request['correction_id']
    require(isinstance(ident,str) and re.fullmatch(r'[A-Za-z0-9_-]{1,80}',ident), 'safe correction ID required')
    require(all(isinstance(request[k],str) and request[k].strip() for k in ('reason','owner')), 'reason/owner required')
    old=audit_saved(root,request['old_refs'],as_of)
    new=audit_saved(root,request['new_refs'],as_of)
    require((old['race_id'],old['race_date_jst'])==(new['race_id'],new['race_date_jst']), 'correction race/date mismatch')
    for key in ('prediction_gate','prediction_original','recommendation_gate'):
        require(request['old_refs'][key]==request['new_refs'][key], 'correction cannot replace fixed prediction/recommendation')
    require(iso(new['result']['retrieved_at_jst'],'new result')>iso(old['result']['retrieved_at_jst'],'old result'),
            'correction must be observed after original result')
    bundle=fixed_json(root,request['new_refs']['capture'])
    source=result_quote(bundle,request['correction_quotation'])
    require('訂正' in request['correction_quotation']['quote'], 'explicit official correction quotation required')
    require(source['source_url']==new['result']['source_url'], 'correction notice/result source mismatch')
    diff={key:{'old':old['result'].get(key),'new':new['result'].get(key)}
          for key in ('finish_groups','scratched_horses','non_finishers','place_places')
          if old['result'].get(key)!=new['result'].get(key)}
    require(bool(diff), 'no result correction to record')
    historical_review=fixed_json(root,request['old_review_ref'])
    historical_kpi=fixed_json(root,request['old_kpi_ref'])
    prior=request['previous_correction_ref']
    if prior is not None:
        history=fixed_json(root,prior)
        require(history.get('schema_version')=='chat-result-correction-v1' and
                history['new_refs']==request['old_refs'] and history['correction_id']!=ident,
                'correction history cannot diverge or reuse an ID')
    return {'schema_version':'chat-result-correction-v1',**request,'race_id':old['race_id'],
            'race_date_jst':old['race_date_jst'],'difference':diff,
            'recommendation_difference':{'old':old['recommendation_result'],'new':new['recommendation_result']},
            'historical_review_preserved':True,'historical_kpi_preserved':True,
            'old_review_schema':historical_review.get('schema_version'),
            'old_kpi_schema':historical_kpi.get('schema_version'),
            'status':'OWNER_REVIEW_REQUIRED','kpi_adoption':'NOT_APPLIED',
            'formal_kpi_certified':False,'mode':new['mode']}


def append_history(root, record):
    require(record.get('schema_version')=='chat-result-correction-v1' and record.get('kpi_adoption')=='NOT_APPLIED',
            'review-only correction sidecar required')
    ident=record.get('correction_id')
    require(isinstance(ident,str) and re.fullmatch(r'[A-Za-z0-9_-]{1,80}',ident), 'safe correction ID required')
    path=safe_path(root,'docs/validation/records/result-corrections/'+ident+'.json')
    path.parent.mkdir(parents=True,exist_ok=True)
    raw=(json.dumps(record,ensure_ascii=False,indent=2)+'\n').encode()
    temp=None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent,delete=False) as stream:
            temp=Path(stream.name);stream.write(raw);stream.flush();os.fsync(stream.fileno())
        require(temp.read_bytes()==raw,'correction staged readback mismatch')
        os.link(temp,path)  # exclusive append; no replacement of history
        require(path.read_bytes()==raw,'correction readback mismatch')
    finally:
        if temp is not None:temp.unlink(missing_ok=True)
    return {'artifact_path':str(path.relative_to(Path(root).resolve())),'sha256':fingerprint(raw)}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('request',type=Path)
    p.add_argument('--root',type=Path,default=Path('.'));p.add_argument('--as-of');p.add_argument('--append',action='store_true')
    args=p.parse_args(argv)
    try:
        record=correction(args.root,json.loads(args.request.read_text()),args.as_of)
        print(json.dumps(append_history(args.root,record) if args.append else record,ensure_ascii=False,indent=2));return 0
    except (ValueError,TypeError,KeyError,OSError) as exc:
        print('公式訂正履歴保留：'+str(exc));return 1


if __name__=='__main__':raise SystemExit(main())
