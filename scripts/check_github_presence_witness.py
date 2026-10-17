#!/usr/bin/env python3
"""保存済みGitHub API観測とGit原本を照合。発走前存在だけを判定する。"""
import argparse
import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path

MANIFEST = 'docs/validation/reconciliations/2026-10-17-github-witnesses.json'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def at(value):
    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    require(dt.tzinfo is not None, 'timezone required')
    return dt


def check(root, manifest=MANIFEST):
    root = Path(root).resolve()
    data = json.loads((root / manifest).read_text())
    require(data['schema_version'] == 'github-presence-witness-v1' and
            data['readback_proven'] is False and data['formal_kpi_promoted'] is False,
            'presence witness cannot certify readback or KPI')
    retrieved = at(data['retrieved_at_jst'])
    require(retrieved <= datetime.now(retrieved.tzinfo), 'future retrieval')
    groups = {}
    for item in data['items']:
        race, kind = item['race_id'], item['kind']
        require(kind in {'INTENT', 'FIX', 'PREDICTION'}, 'unknown evidence kind')
        group = groups.setdefault(race, {})
        require(kind not in group, 'duplicate evidence')
        path = Path(item['artifact_path'])
        require(not path.is_absolute() and '..' not in path.parts and
                str(path).startswith('docs/validation/'), 'invalid artifact path')
        raw = subprocess.check_output(['git', 'show', item['commit'] + ':' + str(path)], cwd=root)
        require(hashlib.sha256(raw).hexdigest() == item['sha256'] and
                raw == (root / path).read_bytes(), 'historical/current bytes mismatch')
        payload = json.loads(raw)
        run = item['run']
        require(run['repository'] == run['head_repository'] == 'eda-hub/horse-man' and
                run['head_sha'] == item['commit'] and run['event'] == 'push' and
                run['head_branch'] == 'prediction/' + race[:10] and
                item['api_url'] == run['url'] ==
                f"https://api.github.com/repos/eda-hub/horse-man/actions/runs/{run['id']}" and
                run['html_url'] == f"https://github.com/eda-hub/horse-man/actions/runs/{run['id']}",
                'GitHub run binding mismatch')
        created, started, post = at(run['created_at']), at(run['run_started_at']), at(item['scheduled_post_time_jst'])
        require(created <= started <= retrieved and created < post,
                'late or reversed server witness')
        # conclusion=successは条件にしない。失敗したrunでもそのcommitの存在を裏付ける。
        group[kind] = (item, payload, created)
    reports = []
    require(bool(groups), 'empty evidence')
    for race, group in groups.items():
        require(set(group) == {'INTENT', 'FIX', 'PREDICTION'}, 'incomplete evidence chain')
        intent, fix, pred = (group[k] for k in ('INTENT', 'FIX', 'PREDICTION'))
        i, f, p = intent[1], fix[1], pred[1]
        require(p['race_id'] == race and p['snapshot_id'] == f['snapshot_id'] == i['snapshot_id'] and
                i['required_race_ids'] == [race] and
                f['artifact_path'] == i['artifact_path'] == pred[0]['artifact_path'] and
                f['fixed_content_sha256'] == pred[0]['sha256'] and
                f['intent_ref']['artifact_path'] == intent[0]['artifact_path'] and
                f['intent_ref']['sha256'] == intent[0]['sha256'] and
                i['deadline_jst'] == p['scheduled_post_time_jst'] and
                all(x[0]['scheduled_post_time_jst'] == p['scheduled_post_time_jst']
                    for x in (intent, fix, pred)), 'artifact chain mismatch')
        fixed = at(p['fixed_at_jst'])
        require(f['fixed_at_jst'] == p['fixed_at_jst'] and fixed <= pred[2], 'invalid FIX time')
        reports.append({'race_id': race, 'pre_race_github_presence': 'CORROBORATED',
                        'intent_server_witness_before_fix': intent[2] <= fixed,
                        'server_witness_order_consistent': intent[2] <= fixed <= fix[2] <= pred[2],
                        'historical_readback': 'NOT_PROVEN_BY_THIS_EVIDENCE',
                        'formal_kpi_promoted': False})
    return {'witness_count': len(data['items']), 'races': reports,
            'limitation': 'GitHub API観測の保存内容とGit原本を照合。オフライン検査はAPI応答自体の真正性を独立認証しない。'}


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root', type=Path, default=Path('.'))
    ap.add_argument('--manifest', default=MANIFEST)
    args = ap.parse_args()
    print(json.dumps(check(args.root, args.manifest), ensure_ascii=False, indent=2))
