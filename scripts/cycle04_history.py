#!/usr/bin/env python3
"""固定commitの実blobを読み、旧集計を原入力から再計算する。作業ツリーへ復元しない。"""
import argparse
import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path, PurePosixPath

SOURCE_COMMIT = '885d7d490245ba4d948bb4594017371d17eadc04'
MANIFEST = 'docs/validation/reviews/cycle_04/migration-manifest.json'
DECISIONS = 'docs/validation/reviews/cycle_03/decisions.json'
COLLECTION = 'docs/validation/reviews/cycle_03/collection.json'


def git(root, *args):
    p = subprocess.run(['git', '-C', str(root), *args], capture_output=True)
    if p.returncode:
        raise ValueError('固定履歴を取得できません: ' + ' '.join(args))
    return p.stdout


def fixed_bytes(root, path, blob=None, sha256=None, commit=SOURCE_COMMIT):
    p = PurePosixPath(path)
    if (not isinstance(path, str) or p.is_absolute() or '..' in p.parts or
            str(p) != path or not path.startswith('docs/')):
        raise ValueError('固定履歴path不正')
    if commit != SOURCE_COMMIT:
        raise ValueError('移行基準commit不一致')
    if git(root, 'rev-parse', '--verify', commit + '^{commit}').decode().strip() != commit:
        raise ValueError('固定commit不一致')
    actual = git(root, 'rev-parse', commit + ':' + path).decode().strip()
    if blob is not None and actual != blob:
        raise ValueError('固定Git blob不一致: ' + path)
    if git(root, 'cat-file', '-t', actual).strip() != b'blob':
        raise ValueError('履歴参照はblobが必要')
    raw = git(root, 'cat-file', 'blob', actual)
    calculated = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
    if actual != calculated or (sha256 is not None and hashlib.sha256(raw).hexdigest() != sha256):
        raise ValueError('固定本文hash不一致: ' + path)
    return raw


def read(root, path):
    manifest = json.loads((Path(root) / MANIFEST).read_text())
    if manifest.get('source_commit') != SOURCE_COMMIT:
        raise ValueError('移行基準commit不一致')
    entries = [x for x in manifest['files'] if x['path'] == path]
    if len(entries) != 1:
        raise ValueError('固定履歴参照が未登録/重複: ' + path)
    ref = entries[0]
    return fixed_bytes(root, path, ref['git_blob_sha1'], ref['sha256'])


def read_json(root, path):
    return json.loads(read(root, path))


def recompute(root):
    """64原入力を固定Gitから実取得し、既存アルゴリズムで集合・KPI・精算を比較する。"""
    saved = read_json(root, COLLECTION)
    inputs = saved['source_manifest']
    if len({x['path'] for x in inputs}) != len(inputs) or not inputs:
        raise ValueError('履歴入力集合が不正')
    with tempfile.TemporaryDirectory(prefix='cycle04-fixed-history-') as folder:
        target = Path(folder)
        for ref in inputs:
            raw = fixed_bytes(root, ref['path'], ref['git_blob_sha'], ref['sha256'])
            if len(raw) != ref['bytes']:
                raise ValueError('履歴入力bytes不一致')
            path = target / ref['path']
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        from build_cycle03_review import build
        actual = build(target, saved['as_of_date_jst'], saved['basis_commit'])
        if actual != saved:
            raise ValueError('固定履歴の再計算値が不一致')
    return {'inputs': len(inputs), 'collection': saved['collection'],
            'scope': saved['scope_totals_recorded_days_only'],
            'settlement': saved['split_fixed_plan_reference'],
            'pending_kpi_decisions': saved['pending_kpi_decision_count']}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument('--audit', action='store_true')
    args = p.parse_args()
    try:
        print(json.dumps(recompute(args.root), ensure_ascii=False))
        return 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print('固定履歴検査不合格: ' + str(exc))
        return 1

if __name__ == '__main__':
    raise SystemExit(main())
