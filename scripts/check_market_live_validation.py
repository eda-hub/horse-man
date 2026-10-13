#!/usr/bin/env python3
"""2開催の発走前価格・出所両経路・独立receipt・Git原本を読取照合する。"""
import argparse
import json
import re
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime

from check_prediction_compliance import iso, receipt_records
from cycle04_operations import require, safe_path, verified_artifact, fingerprint
from market_acquisition import verify_responses
from jvlink_market import address


def git(root, *args):
    result = subprocess.run(['git',*args],cwd=root,capture_output=True,check=True)
    return result.stdout


def check(root, manifest):
    require(isinstance(manifest,dict) and manifest.get('schema_version') == 'market-live-validation-v1',
            'live market validation manifest required')
    entries = manifest.get('entries')
    require(isinstance(entries,list), 'live validation entries required')
    days = set(); specs = set(); ids = set()
    for entry in entries:
        require(isinstance(entry,dict), 'live entry object required')
        ref = entry.get('market_ref'); commit = entry.get('commit_sha')
        require(isinstance(ref,dict) and re.fullmatch(r'[0-9a-f]{40}',commit or ''),
                'fixed Git commit and independent market reference required')
        current = json.loads(safe_path(root,ref.get('artifact_path')).read_text())
        request = current['market']['acquisition']['request']
        post = request['scheduled_post_time_jst']
        payload, receipt = verified_artifact(root,ref,post)
        require(payload['mode'] == 'FORWARD' and payload['market']['status'] == 'ACQUIRED',
                'only actual acquired forward evidence can count')
        verify_responses(root,payload)
        date = payload['race_date_jst']; race = payload['race_id']
        from cycle04_workflow import read_day
        scope, _ = read_day(Path(root),date)
        require(race in scope['initial_scope'] and
                scope['races'][race]['scheduled_post_time_jst'] == post,
                'live measurement does not match saved official scope/post')
        require(ref['artifact_id'] not in ids, 'duplicate live acquisition identity')
        ids.add(ref['artifact_id'])
        fixed_time = git(root,'show','-s','--format=%cI',commit).decode().strip()
        require(iso(fixed_time,'Git fixation') < iso(post,'post'), 'market Git fixation at/after post')
        paths = [ref['artifact_path']]
        paths += [a['response_ref']['artifact_path'] for a in payload['market']['acquisition']['attempts']
                  if a.get('response_ref') is not None]
        for path in set(paths):
            original = git(root,'show',commit+':'+path)
            require(original == safe_path(root,path).read_bytes(), 'fixed Git market bytes mismatch')
        fixed_receipt = git(root,'show',commit+':'+ref['receipt_path'])
        with tempfile.TemporaryDirectory(prefix='market-receipt-check-') as directory:
            path = Path(directory)/'receipt.md'; path.write_bytes(fixed_receipt)
            matches = [r for r in receipt_records(path) if r.get('receipt_id') == ref['receipt_id']]
            require(matches == [receipt], 'fixed Git market receipt mismatch')
        require(all(r.get('provider') == 'JV_LINK' for r in request['routes']),
                'registered JV-Link sources required for this validation')
        spec, key = address(payload['market']['source_ref'],request)
        specs.add(spec); days.add(date)
    routes_complete = '0B30' in specs and bool(specs-{'0B30'})
    passed = len(days) >= 2 and routes_complete
    return {'schema_version':'market-live-validation-result-v1',
            'status':'PASS' if passed else 'CONTINUE_VALIDATION',
            'measured_meeting_dates':sorted(days), 'confirmed_dataspecs':sorted(specs),
            'required_meetings':2,'both_routes_confirmed':routes_complete,
            'performance_promoted':False,'prediction_recommendation_changed':False,
            'note':'合成・loopbackを数えず、原応答/receipt/Git/公式scopeの整合を照合。価格効果の認証はしない。'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument('manifest',type=Path)
    args = parser.parse_args(argv)
    try:
        result = check(args.root,json.loads(args.manifest.read_text()))
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return 0 if result['status'] == 'PASS' else 1
    except (ValueError,OSError,KeyError,TypeError,subprocess.CalledProcessError) as exc:
        print('実測受入を完了できません：'+str(exc)); return 1


if __name__ == '__main__': raise SystemExit(main())
