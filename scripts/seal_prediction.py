#!/usr/bin/env python3
"""新規JSON予想のFIX hashを先に独立保存し、読戻し証跡後に本体を保存する。"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from cycle04_operations import fingerprint, require, safe_path, verified_artifact
from check_prediction_compliance import iso


def exclusive(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    # 同一bytesの再試行だけ許容。異なる内容は新revisionへ。
    try:
        with path.open('xb') as stream:
            stream.write(raw)
    except FileExistsError:
        require(path.read_bytes() == raw, 'existing immutable artifact differs; use a new revision')


def seal(root, draft, artifact_path, fix_path, intent_ref, fix_ref=None, now=None):
    root = Path(root).resolve()
    raw = Path(draft).read_bytes()
    data = json.loads(raw)
    require(data.get('schema_version') == 'prediction-snapshot-v2', 'new JSON prediction required')
    post = data['scheduled_post_time_jst']
    current = now or datetime.now(timezone.utc)
    require(current.tzinfo is not None and current < iso(post, 'post'), 'cannot seal at/after deadline')
    fixed = iso(data.get('fixed_at_jst'), 'fixed')
    require(fixed <= current, 'FIX cannot be in the future')
    date = iso(post, 'post').astimezone(iso(post, 'post').tzinfo).date().isoformat()
    require(data.get('working_branch') == 'prediction/' + date, 'wrong daily branch')
    body = safe_path(root, artifact_path)
    fix = safe_path(root, fix_path)
    require(artifact_path.startswith('docs/validation/snapshots/' + date + '/') and body.suffix == '.json'
            and fix_path.startswith('docs/validation/fix-manifests/' + date + '/') and fix.suffix == '.json',
            'new immutable body/FIX paths required')
    intent, receipt = verified_artifact(root, intent_ref, post)
    require(intent.get('schema_version') == 'prediction-persistence-intent-v1' and
            intent.get('snapshot_id') == data['snapshot_id'] and intent.get('artifact_path') == artifact_path
            and intent.get('required_race_ids') == [data['race_id']] and intent.get('deadline_jst') == post,
            'predeclaration body/scope/deadline mismatch')
    require(iso(receipt['receipt_verified_at_jst'], 'intent readback') <= fixed,
            'prediction started before predeclaration readback')
    manifest = {'schema_version': 'prediction-fix-manifest-v1', 'snapshot_id': data['snapshot_id'],
                'artifact_path': artifact_path, 'fixed_content_sha256': fingerprint(raw),
                'fixed_at_jst': data['fixed_at_jst'], 'intent_ref': intent_ref}
    if fix_ref is None:
        require(not body.exists(), 'FIX hash cannot be prepared after body was persisted')
        exclusive(fix, (json.dumps(manifest, ensure_ascii=False, indent=2) + '\n').encode())
        return 'FIX hashを独立ファイルへ書込みました。Git保存と読戻し後、本体保存を実行してください。'
    require(fix_ref.get('artifact_path') == fix_path, 'different FIX manifest path')
    saved, fixed_receipt = verified_artifact(root, fix_ref, post)
    require(saved == manifest and iso(fixed_receipt['receipt_verified_at_jst'], 'FIX readback') <= current,
            'independent FIX manifest hash/readback mismatch')
    exclusive(body, raw)
    return '本体を書込みました。Git保存・読戻し・個別完了検査は未実施です。'


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, default=Path('.'))
    p.add_argument('--draft', type=Path, required=True)
    p.add_argument('--artifact-path', required=True)
    p.add_argument('--fix-path', required=True)
    p.add_argument('--intent-ref', type=Path, required=True)
    p.add_argument('--fix-ref', type=Path, help='独立FIX保存と読戻し済みの参照。指定時のみ本体を書込む')
    args = p.parse_args(argv)
    try:
        ref = json.loads(args.intent_ref.read_text())
        fixed = json.loads(args.fix_ref.read_text()) if args.fix_ref else None
        print(seal(args.root, args.draft, args.artifact_path, args.fix_path, ref, fixed))
        return 0
    except (ValueError, OSError, KeyError, TypeError, AttributeError) as exc:
        print('保存未完了：' + str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
