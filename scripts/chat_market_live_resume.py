#!/usr/bin/env python3
"""既存29番の実測再開入口。証跡なしを架空の0件受入にしない。"""
import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from chat_result_reconciliation import fixed_json
from check_chat_market_live_validation import check
from check_prediction_compliance import iso
from cycle04_operations import require


def resume(root, manifest_ref=None, as_of=None):
    if manifest_ref is None:
        return {'schema_version':'chat-market-live-resume-v1','status':'WAITING_REAL_EVIDENCE',
                'measured_meeting_count':None,'validation_result':None,
                'required_meetings':2,'required_ticket_types':8,'required_independent_sources':2,
                'next_check':'既存29番の実発走前本文/Git/receipt/公式scopeを揃えて再開',
                'prediction_recommendation_can_complete_without_market':True,
                'live_validation_accepted':False,'read_only':True}
    manifest=fixed_json(root,manifest_ref)
    require(isinstance(manifest.get('entries'),list) and manifest['entries'], 'empty manifest is not measured live evidence')
    now=iso(as_of,'current time') if as_of else datetime.now(timezone.utc)
    for entry in manifest['entries']:
        payload=fixed_json(root,{'artifact_path':entry['market_ref']['artifact_path'],'sha256':entry['market_ref']['sha256']})
        require(iso(payload['market']['acquired_at_jst'],'actual acquisition')<=now,'future acquisition is not live evidence')
    report=check(root,manifest)
    return {'schema_version':'chat-market-live-resume-v1','status':report['status'],
            'manifest_ref':manifest_ref,'validation_result':report,
            'live_validation_accepted':report['status']=='PASS',
            'prediction_recommendation_can_complete_without_market':True,'read_only':True}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--manifest-ref',type=Path)
    p.add_argument('--root',type=Path,default=Path('.'));p.add_argument('--as-of');args=p.parse_args(argv)
    try:
        out=resume(args.root,json.loads(args.manifest_ref.read_text()) if args.manifest_ref else None,args.as_of)
        print(json.dumps(out,ensure_ascii=False,indent=2));return 0 if out['live_validation_accepted'] else 1
    except (ValueError,TypeError,KeyError,OSError,subprocess.CalledProcessError) as exc:
        print('既存29番の実測再開保留：'+str(exc));return 1


if __name__=='__main__':raise SystemExit(main())
