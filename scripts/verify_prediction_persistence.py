#!/usr/bin/env python3
"""Verify a prediction snapshot and its receipt immediately after persistence.

Intents are written before prediction work, so the audit also detects a snapshot
that was never created. This tool does not create evidence or infer eligibility.
"""

import argparse
import hashlib
from datetime import datetime
import json
import re
import sys
from pathlib import Path

from check_prediction_compliance import ComplianceError, iso, receipt_records


def snapshot_section(content, snapshot_id):
    sections = re.split(r'(?=^##\s+)', content, flags=re.M)
    matched = [section for section in sections
               if re.search(r'^(?:-\s+)?snapshot_id:\s*'+re.escape(snapshot_id)+r'\s*$',section,re.M)]
    if len(matched) != 1:
        raise ComplianceError(f'{snapshot_id}: expected one snapshot section, found {len(matched)}')
    return matched[0]


def field(section, key):
    match = re.search(r'^(?:-\s+)?'+re.escape(key)+r':\s*(.*?)\s*$',section,re.M)
    return match.group(1).strip() if match else None


def verify(root, date, snapshot_id, deadline=None, expected_races=()):
    path = root/'docs/validation/snapshots'/f'{date}.md'
    if not path.is_file(): raise ComplianceError(f'{snapshot_id}: snapshot file missing: {path}')
    section = snapshot_section(path.read_text(encoding='utf-8'),snapshot_id)
    if field(section,'working_branch') != f'prediction/{date}':
        raise ComplianceError(f'{snapshot_id}: wrong working branch')
    if expected_races:
        # A structured scope block prevents another section's race IDs from
        # accidentally satisfying an all-race prediction intent.
        blocks = re.findall(r'^(?:```|\\`\\`\\`)prediction-scope-v1[ \t]*\n(.*?)\n(?:```|\\`\\`\\`)[ \t]*$',section,re.M|re.S)
        if len(blocks)!=1: raise ComplianceError(f'{snapshot_id}: prediction-scope-v1 required')
        scope=json.loads(blocks[0])
        if set(scope.get('race_ids',[])) != set(expected_races) or len(scope.get('race_ids',[]))!=len(expected_races):
            raise ComplianceError(f'{snapshot_id}: predicted race scope differs from intent')
    receipts=root/'docs/validation/persistence-receipts'/f'{date}.md'
    if not receipts.is_file(): raise ComplianceError(f'{snapshot_id}: receipt file missing: {receipts}')
    candidates=[r for r in receipt_records(receipts) if r.get('artifact_id')==snapshot_id]
    eligible=[r for r in candidates if r.get('artifact_path')==str(path.relative_to(root))
              and r.get('artifact_persist_status')=='PERSIST_VERIFIED'
              and r.get('receipt_persist_status')=='RECEIPT_VERIFIED'
              and r.get('timing_eligibility')=='PRE_RACE_ELIGIBLE']
    if not eligible: raise ComplianceError(f'{snapshot_id}: verified pre-race receipt missing')
    post=iso(deadline or field(section,'scheduled_post_time_jst') or
             eligible[-1].get('scheduled_post_time_jst'),f'{snapshot_id}/deadline')
    for receipt in eligible:
        verified=iso(receipt.get('persist_verified_at_jst'),f'{snapshot_id}/persist_verified_at_jst')
        receipt_time=receipt.get('receipt_verified_at_jst')
        receipt_post=receipt.get('scheduled_post_time_jst')
        limit=min(post,iso(receipt_post,f'{snapshot_id}/scheduled_post_time_jst')) if receipt_post else post
        if receipt_time and verified<limit and iso(receipt_time,f'{snapshot_id}/receipt_verified_at_jst')<limit:
            return receipt['receipt_id']
    raise ComplianceError(f'{snapshot_id}: receipt readback time missing or at/after deadline')


def check_intent(root, path):
    intent=json.loads(path.read_text(encoding='utf-8'))
    if intent.get('schema_version')!='prediction-persistence-intent-v1':
        raise ComplianceError(f'{path}: wrong intent schema')
    date=intent.get('race_date_jst')
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',str(date)) or path.parent.name!=date:
        raise ComplianceError(f'{path}: intent date/path mismatch')
    if intent.get('working_branch')!=f'prediction/{date}':
        raise ComplianceError(f'{path}: wrong working branch')
    snapshot_id=intent.get('snapshot_id')
    if not isinstance(snapshot_id,str) or not snapshot_id:
        raise ComplianceError(f'{path}: snapshot_id required')
    races=intent.get('required_race_ids')
    if not isinstance(races,list) or not races or any(not isinstance(x,str) or not x for x in races) or len(set(races))!=len(races):
        raise ComplianceError(f'{path}: required_race_ids must be unique and nonempty')
    deadline=intent.get('deadline_jst')
    iso(deadline,f'{path}/deadline_jst')
    return verify(root,date,snapshot_id,deadline,races)


def declared_intent_paths(directory):
    """Return active intent JSON files; failed-attempt payloads are audit history only."""
    if not directory.exists():
        return []
    return sorted(p for p in directory.glob('*/*.json') if p.parent.name != 'failed-attempts')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path('.'))
    parser.add_argument('--date',help='JST race date YYYY-MM-DD')
    parser.add_argument('--snapshot-id',help='verify one just-saved snapshot')
    parser.add_argument('--audit',action='store_true',help='report all declared intents without blocking prediction persistence')
    parser.add_argument('--prepare',action='store_true',help='write a prediction intent before prediction work')
    parser.add_argument('--intent-id',help='unique name for the attempt')
    parser.add_argument('--deadline-jst',help='earliest scheduled post time for this attempt')
    parser.add_argument('--race-id',action='append',default=[],help='one expected race ID; repeat for all races')
    parser.add_argument('--task-complete',action='store_true',help='require saved intent and exact fixed-content hash before declaring task complete')
    parser.add_argument('--fixed-content-sha256',help='hash of the FIXED snapshot section before writing')
    args=parser.parse_args()
    if args.task_complete and (not args.snapshot_id or args.prepare or args.audit):
        parser.error('--task-complete requires direct --snapshot-id verification')
    if (args.audit and (args.prepare or args.snapshot_id)) or (not args.audit and not args.prepare and not args.snapshot_id):
        parser.error('choose --audit, --prepare with --snapshot-id, or direct --snapshot-id')
    if (args.prepare or args.snapshot_id) and not args.date:
        parser.error('--date is required for preparation or direct verification')
    try:
        if args.prepare:
            if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',args.date):
                parser.error('--date must be YYYY-MM-DD')
            if not re.fullmatch(r'[a-zA-Z0-9_-]+',args.intent_id or '') or not args.snapshot_id:
                parser.error('--prepare requires --intent-id and --snapshot-id')
            if not args.race_id or len(args.race_id)!=len(set(args.race_id)):
                parser.error('--prepare requires unique --race-id values')
            deadline=iso(args.deadline_jst,'deadline_jst')
            if datetime.now(deadline.tzinfo)>=deadline:
                raise ComplianceError('cannot prepare an intent at/after its deadline')
            intent={'schema_version':'prediction-persistence-intent-v1',
                    'race_date_jst':args.date,'working_branch':f'prediction/{args.date}',
                    'snapshot_id':args.snapshot_id,'required_race_ids':args.race_id,
                    'deadline_jst':args.deadline_jst}
            path=args.root/'docs/validation/persistence-intents'/args.date/f'{args.intent_id}.json'
            path.parent.mkdir(parents=True,exist_ok=True)
            content=json.dumps(intent,ensure_ascii=False,indent=2)+'\n'
            if path.exists():
                if path.read_text(encoding='utf-8')!=content:
                    raise ComplianceError(f'{path}: existing intent differs; choose a new intent ID')
            else: path.write_text(content,encoding='utf-8')
            print(f'INTENT_PREPARED {path}; commit and read back before prediction work')
            return 0
        if args.snapshot_id:
            if args.task_complete:
                if not args.intent_id or not re.fullmatch(r'[a-zA-Z0-9_-]+',args.intent_id):
                    raise ComplianceError('task completion requires --intent-id')
                intent_path=args.root/'docs/validation/persistence-intents'/args.date/f'{args.intent_id}.json'
                intent=json.loads(intent_path.read_text(encoding='utf-8'))
                if intent.get('snapshot_id')!=args.snapshot_id:
                    raise ComplianceError('task completion intent/snapshot mismatch')
                check_intent(args.root,intent_path)
                section=snapshot_section((args.root/'docs/validation/snapshots'/f'{args.date}.md').read_text(encoding='utf-8'),args.snapshot_id)
                digest=hashlib.sha256(section.encode('utf-8')).hexdigest()
                if not args.fixed_content_sha256 or digest!=args.fixed_content_sha256:
                    raise ComplianceError('task completion fixed/readback content hash mismatch')
            receipt=verify(args.root,args.date,args.snapshot_id)
            state='TASK_PERSISTENCE_COMPLETE' if args.task_complete else 'PERSISTENCE_VERIFIED'
            print(f'{state} {args.snapshot_id} receipt={receipt}')
            return 0
        directory=args.root/'docs/validation/persistence-intents'
        paths=declared_intent_paths(directory)
        if args.date: paths=[p for p in paths if p.parent.name==args.date]
        failed=0
        declared=set()
        for path in paths:
            try:
                item=json.loads(path.read_text(encoding='utf-8'))
                declared.add((path.parent.name,item.get('snapshot_id')))
            except (OSError,ValueError):
                pass
        snapshots=args.root/'docs/validation/snapshots'
        for snapshot in sorted(snapshots.glob('*.md')):
            if args.date and snapshot.stem!=args.date: continue
            for ident in re.findall(r'^(?:-\s+)?snapshot_id:\s*(\S+)\s*$',snapshot.read_text(encoding='utf-8'),re.M):
                if (snapshot.stem,ident) not in declared:
                    failed+=1
                    print(f'PERSISTENCE_INCOMPLETE {snapshot}: {ident}: NO_INTENT; historical omission, not retroactively prepared')
        if not paths:
            print('NO_INTENTS: no declared prediction attempts; audit cannot establish completeness')
        for path in paths:
            try: print(f'PERSISTENCE_VERIFIED {path} receipt={check_intent(args.root,path)}')
            except (ComplianceError,OSError,ValueError) as exc:
                failed+=1; print(f'PERSISTENCE_INCOMPLETE {path}: {exc}')
        print(f'PERSISTENCE_AUDIT: intents={len(paths)} incomplete={failed}')
        return 0
    except (ComplianceError,OSError,ValueError) as exc:
        print(f'PERSISTENCE_INCOMPLETE: {exc}',file=sys.stderr)
        return 1


if __name__=='__main__': raise SystemExit(main())
