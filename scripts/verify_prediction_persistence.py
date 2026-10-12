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

PREDICTION_SNAPSHOT_SCHEMA = 'prediction-snapshot-v2'


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


def _relative(root, path):
    try:
        return str(path.relative_to(root))
    except ValueError as exc:
        raise ComplianceError(f'{path}: artifact must be under repository root') from exc


def resolve_snapshot(root, date, snapshot_id, declared_artifact_path=None):
    candidates=[]

    if declared_artifact_path:
        declared=root/declared_artifact_path
        if not declared.is_file():
            raise ComplianceError(f'{snapshot_id}: snapshot file missing: {declared}')
        paths=[declared]
    else:
        paths=[]
        legacy=root/'docs/validation/snapshots'/f'{date}.md'
        if legacy.is_file():
            paths.append(legacy)
        json_dir=root/'docs/validation/snapshots'/date
        if json_dir.exists():
            paths.extend(sorted(json_dir.rglob('*.json')))

    for path in paths:
        rel=_relative(root,path)
        if path.suffix=='.md':
            content=path.read_text(encoding='utf-8')
            try:
                section=snapshot_section(content,snapshot_id)
            except ComplianceError:
                if declared_artifact_path:
                    raise
                continue
            scope_blocks= re.findall(r'^(?:```|\\`\\`\\`)prediction-scope-v1[ \t]*\n(.*?)\n(?:```|\\`\\`\\`)[ \t]*$',section,re.M|re.S)
            scope=None
            if scope_blocks:
                if len(scope_blocks)!=1:
                    raise ComplianceError(f'{snapshot_id}: expected one prediction-scope-v1 block')
                scope=json.loads(scope_blocks[0]).get('race_ids')
            candidates.append({
                'kind':'markdown','path':path,'artifact_path':rel,'snapshot_id':snapshot_id,
                'working_branch':field(section,'working_branch'),
                'scheduled_post_time_jst':field(section,'scheduled_post_time_jst'),
                'race_ids':scope,'hash_bytes':section.encode('utf-8'),
            })
            continue

        if path.suffix=='.json':
            try:
                data=json.loads(path.read_text(encoding='utf-8'))
            except json.JSONDecodeError as exc:
                if declared_artifact_path:
                    raise ComplianceError(f'{snapshot_id}: invalid JSON snapshot: {path}') from exc
                continue
            if data.get('schema_version')!=PREDICTION_SNAPSHOT_SCHEMA or data.get('snapshot_id')!=snapshot_id:
                if declared_artifact_path:
                    raise ComplianceError(f'{snapshot_id}: declared JSON artifact does not match {PREDICTION_SNAPSHOT_SCHEMA}')
                continue
            race_id=data.get('race_id')
            if not isinstance(race_id,str) or not race_id:
                raise ComplianceError(f'{snapshot_id}: JSON snapshot race_id required')
            candidates.append({
                'kind':'json','path':path,'artifact_path':rel,'snapshot_id':snapshot_id,
                'working_branch':data.get('working_branch'),
                'scheduled_post_time_jst':data.get('scheduled_post_time_jst'),
                'race_ids':[race_id],'hash_bytes':path.read_bytes(),'data':data,
            })

    if not candidates:
        default=root/'docs/validation/snapshots'/f'{date}.md'
        raise ComplianceError(
            f'{snapshot_id}: snapshot file missing: {default} or JSON snapshot under docs/validation/snapshots/{date}/'
        )
    if len(candidates)!=1:
        raise ComplianceError(f'{snapshot_id}: expected one snapshot artifact, found {len(candidates)}')
    return candidates[0]


def snapshot_digest(snapshot):
    return hashlib.sha256(snapshot['hash_bytes']).hexdigest()


def verify(root, date, snapshot_id, deadline=None, expected_races=(), expected_artifact_path=None):
    snapshot=resolve_snapshot(root,date,snapshot_id,expected_artifact_path)
    if snapshot.get('working_branch') != f'prediction/{date}':
        raise ComplianceError(f'{snapshot_id}: wrong working branch')
    if expected_races:
        scope=snapshot.get('race_ids')
        if not isinstance(scope,list):
            raise ComplianceError(f'{snapshot_id}: prediction scope required')
        if set(scope) != set(expected_races) or len(scope)!=len(expected_races):
            raise ComplianceError(f'{snapshot_id}: predicted race scope differs from intent')
    receipts=root/'docs/validation/persistence-receipts'/f'{date}.md'
    if not receipts.is_file(): raise ComplianceError(f'{snapshot_id}: receipt file missing: {receipts}')
    candidates=[r for r in receipt_records(receipts) if r.get('artifact_id')==snapshot_id]
    eligible=[r for r in candidates if r.get('artifact_path')==snapshot['artifact_path']
              and r.get('artifact_persist_status')=='PERSIST_VERIFIED'
              and r.get('receipt_persist_status')=='RECEIPT_VERIFIED'
              and r.get('timing_eligibility')=='PRE_RACE_ELIGIBLE']
    if not eligible: raise ComplianceError(f'{snapshot_id}: verified pre-race receipt missing')
    post=iso(deadline or snapshot.get('scheduled_post_time_jst') or
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
    artifact_path=intent.get('artifact_path')
    if artifact_path is not None:
        artifact=Path(artifact_path)
        if artifact.is_absolute() or '..' in artifact.parts or not str(artifact).startswith('docs/validation/snapshots/'):
            raise ComplianceError(f'{path}: invalid artifact_path')
    recommendation = intent.get('recommendation_scope')
    if recommendation is not None:
        if not isinstance(recommendation,dict) or not isinstance(recommendation.get('recommendation_id'),str) or not recommendation['recommendation_id']:
            raise ComplianceError(f'{path}: recommendation_scope.recommendation_id required')
        rec_path=recommendation.get('artifact_path')
        if not isinstance(rec_path,str):
            raise ComplianceError(f'{path}: recommendation_scope.artifact_path required')
        relative=Path(rec_path)
        if relative.is_absolute() or '..' in relative.parts or not rec_path.startswith('docs/validation/recommendations/') or relative.suffix!='.json' or relative.parent.name!=date:
            raise ComplianceError(f'{path}: invalid recommendation_scope.artifact_path')
        if len(races)!=1 or recommendation.get('race_id')!=races[0]:
            raise ComplianceError(f'{path}: recommendation_scope must match one predicted race')
    return verify(root,date,snapshot_id,deadline,races,artifact_path)


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
    parser.add_argument('--artifact-path',help='repository-relative snapshot artifact path')
    parser.add_argument('--recommendation-id',help='optional predeclared next-contract recommendation ID')
    parser.add_argument('--recommendation-artifact-path',help='optional predeclared recommendation JSON path')
    parser.add_argument('--task-complete',action='store_true',help='require saved intent and exact fixed-content hash before declaring task complete')
    parser.add_argument('--fixed-content-sha256',help='hash of the FIXED snapshot section before writing')
    parser.add_argument('--completion-status',action='store_true',help='read-only independent completion checks with Japanese output')
    parser.add_argument('--status-json',action='store_true',help='machine-readable completion result including internal diagnostics')
    args=parser.parse_args()
    if args.completion_status and (not args.snapshot_id or args.prepare or args.audit):
        parser.error('--completion-status requires direct --snapshot-id verification')
    if args.status_json and not args.completion_status:
        parser.error('--status-json requires --completion-status')
    if args.task_complete and (not args.snapshot_id or args.prepare or args.audit):
        parser.error('--task-complete requires direct --snapshot-id verification')
    if (args.audit and (args.prepare or args.snapshot_id)) or (not args.audit and not args.prepare and not args.snapshot_id):
        parser.error('choose --audit, --prepare with --snapshot-id, or direct --snapshot-id')
    if (args.prepare or args.snapshot_id) and not args.date:
        parser.error('--date is required for preparation or direct verification')
    try:
        if args.completion_status:
            from task_completion import prediction_completion, render_completion
            result=prediction_completion(args.root,args.date,args.snapshot_id,
                intent_id=args.intent_id,fixed_content_sha256=args.fixed_content_sha256,
                artifact_path=args.artifact_path)
            print(json.dumps(result,ensure_ascii=False,indent=2) if args.status_json else render_completion(result))
            return 0 if result['complete'] else 1
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
            if bool(args.recommendation_id) != bool(args.recommendation_artifact_path):
                raise ComplianceError('both --recommendation-id and --recommendation-artifact-path are required')
            if args.recommendation_id:
                if len(args.race_id)!=1 or not args.recommendation_id.strip():
                    raise ComplianceError('recommendation predeclaration requires exactly one race and ID')
                rec_path=Path(args.recommendation_artifact_path)
                if (rec_path.is_absolute() or '..' in rec_path.parts or
                    not str(rec_path).startswith('docs/validation/recommendations/') or
                    rec_path.suffix!='.json' or rec_path.parent.name!=args.date):
                    raise ComplianceError('invalid recommendation artifact path or date')
                intent['recommendation_scope']={
                    'race_id':args.race_id[0], 'recommendation_id':args.recommendation_id,
                    'artifact_path':str(rec_path)
                }
            if args.artifact_path:
                artifact=Path(args.artifact_path)
                if artifact.is_absolute() or '..' in artifact.parts or not str(artifact).startswith('docs/validation/snapshots/'):
                    raise ComplianceError('artifact_path must be a repository-relative snapshot path')
                intent['artifact_path']=str(artifact)
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
                snapshot=resolve_snapshot(args.root,args.date,args.snapshot_id,intent.get('artifact_path'))
                digest=snapshot_digest(snapshot)
                if not args.fixed_content_sha256 or digest!=args.fixed_content_sha256:
                    raise ComplianceError('task completion fixed/readback content hash mismatch')
            receipt=verify(args.root,args.date,args.snapshot_id,expected_artifact_path=args.artifact_path)
            from persistence_status import describe_persistence, render_persistence
            print(render_persistence(describe_persistence('予想本体の保存',write_attempted=True,
                  write_succeeded=True,readback_matches=True,
                  verification_succeeded=True if args.task_complete else None)))
            print('実行ゲート・適用Shadowは個別完了表示で別途確認してください。')
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
        for snapshot in sorted(snapshots.glob('*/*.json')):
            date=snapshot.parent.name
            if args.date and date!=args.date: continue
            try:
                data=json.loads(snapshot.read_text(encoding='utf-8'))
            except json.JSONDecodeError:
                continue
            if data.get('schema_version')!=PREDICTION_SNAPSHOT_SCHEMA:
                continue
            ident=data.get('snapshot_id')
            if not isinstance(ident,str) or not ident:
                failed+=1
                print(f'PERSISTENCE_INCOMPLETE {snapshot}: snapshot_id missing')
                continue
            if (date,ident) not in declared:
                failed+=1
                print(f'PERSISTENCE_INCOMPLETE {snapshot}: {ident}: NO_INTENT; v2 snapshot is not covered by a prior declaration')
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

