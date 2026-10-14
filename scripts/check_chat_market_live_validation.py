#!/usr/bin/env python3
"""チャット取得の2開催実測を公式scope・元Git・receiptと独立照合。"""
import argparse
import json
import re
import subprocess
import tempfile
from pathlib import Path

from check_prediction_compliance import iso, receipt_records
from cycle04_operations import require, safe_path, verified_artifact
from chat_market_acquisition import TRANSPORT, verify, source


def git(root,*args):
    return subprocess.run(['git',*args],cwd=root,capture_output=True,check=True).stdout


def check(root,manifest):
    require(isinstance(manifest,dict) and manifest.get('schema_version')=='chat-market-live-validation-v1',
            'チャット実測manifestが必要')
    entries=manifest.get('entries');require(isinstance(entries,list),'実測entry一覧が必要')
    days=set();sources=set();ids=set();tickets=set()
    for entry in entries:
        require(isinstance(entry,dict),'実測entryが不正')
        ref=entry.get('market_ref');commit=entry.get('commit_sha')
        require(isinstance(ref,dict) and re.fullmatch('[0-9a-f]{40}',commit or ''),'独立保存参照と固定Git commitが必要')
        current=json.loads(safe_path(root,ref.get('artifact_path')).read_text(encoding='utf-8'))
        h=current['market']['acquisition'];request=h['request'];post=request['scheduled_post_time_jst']
        payload,receipt=verified_artifact(root,ref,post)
        require(h.get('transport_schema')==TRANSPORT and payload['mode']=='FORWARD' and
                payload['market']['status']=='ACQUIRED','実際のFORWARD成功本文だけを実測へ数える')
        verify(root,payload)
        from cycle04_workflow import read_day
        scope,_=read_day(Path(root),payload['race_date_jst']);race=payload['race_id']
        require(race in scope['initial_scope'] and scope['races'][race]['scheduled_post_time_jst']==post,
                '公式scope/発走と実測が不一致')
        require(ref['artifact_id'] not in ids,'実測ID重複');ids.add(ref['artifact_id'])
        require(iso(git(root,'show','-s','--format=%cI',commit).decode().strip(),'Git固定')<iso(post,'発走'),
                '発走後のGit固定は実測へ数えない')
        paths={ref['artifact_path']}|{a['capture_ref']['artifact_path'] for a in h['attempts']}
        for path in paths:
            require(git(root,'show',commit+':'+path)==safe_path(root,path).read_bytes(),'当時Gitと本文/分析が不一致')
        with tempfile.TemporaryDirectory(prefix='chat-receipt-check-') as directory:
            p=Path(directory)/'receipt.md';p.write_bytes(git(root,'show',commit+':'+ref['receipt_path']))
            matches=[r for r in receipt_records(p) if r.get('receipt_id')==ref['receipt_id']]
            require(matches==[receipt],'当時の同一receiptが不一致')
        days.add(payload['race_date_jst']);sources.add(source(payload['market']['source_ref'])[0])
        tickets.add(payload['ticket']['type'])
    complete = len(days)>=2 and len(tickets)==8 and len(sources)>=2
    return {'schema_version':'chat-market-live-validation-result-v1',
            'status':'PASS' if complete else 'CONTINUE_VALIDATION',
            'required_meetings':2,'measured_meeting_dates':sorted(days),
            'confirmed_sources':sorted(sources),'confirmed_ticket_types':sorted(tickets),
            'eight_ticket_coverage_complete':len(tickets)==8,
            'independent_sources_confirmed':len(sources)>=2,
            'performance_promoted':False,'prediction_recommendation_changed':False,
            'note':'2開催の真正な保存を照合。8券種網羅/独立代替と価格性能の受入は別判定。'}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('manifest',type=Path)
    p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);a=p.parse_args(argv)
    try:
        result=check(a.root,json.loads(a.manifest.read_text(encoding='utf-8')))
        print(json.dumps(result,ensure_ascii=False,indent=2));return 0 if result['status']=='PASS' else 1
    except (ValueError,OSError,KeyError,TypeError,subprocess.CalledProcessError) as exc:
        print('チャット実測の受入未完了：'+str(exc));return 1


if __name__=='__main__':raise SystemExit(main())
