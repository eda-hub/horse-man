#!/usr/bin/env python3
"""v1.7.0の原子的整合とmainへの統合を別に確認する。"""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from check_prediction_compliance import contract_state, release
from cycle04_operations import require, safe_path

MANIFEST = 'docs/validation/contracts/v170-release.json'
OWNERS = ['README.md', '00_core.md', '10_prediction.md', '20_conditional.md',
          '30_betting.md', '40_shadow.md', '50_review.md', '60_market.md']


def contract_acceptance_path(root):
    contract = json.loads((root/'docs/validation/contracts/cycle_04.json').read_text())
    return contract.get('acceptance_path')


def check(root, require_main=False):
    root = Path(root).resolve()
    manifest = json.loads((root/MANIFEST).read_text())
    require(manifest.get('schema_version') == 'manual-release-readiness-v1' and
            manifest.get('manual_release') == 'v1.7.0' and
            manifest.get('activation_policy') == 'MAIN_MERGE', 'release activation contract mismatch')
    state = contract_state(root)
    require(release(root) == state.get('next_release') == 'v1.7.0' and state['status'] == 'ACTIVE' and
            state.get('activation_policy') == 'MAIN_MERGE' and
            state.get('recommendation_effective_race_date') == state['effective_race_date'],
            'Prediction/Recommendation release cutover mismatch')
    sources = manifest.get('source_manifest')
    require(isinstance(sources, list) and len({s['path'] for s in sources}) == len(sources), 'release source manifest invalid')
    required = {f'docs/manual/{name}' for name in OWNERS} | {'AGENTS.md', 'DECISIONS.md',
                'docs/validation/execution-gates/contract-state.json', 'docs/validation/contracts/cycle_04.json',
                'scripts/check_prediction_compliance.py', 'scripts/check_cycle04.py', 'scripts/cycle04_workflow.py',
                'scripts/recommendation.py', 'scripts/verify_prediction_persistence.py',
                'scripts/prediction_clock.py', 'scripts/prediction_persistence_io.py',
                '.agents/skills/horse-racing-forecast/SKILL.md',
                'docs/validation/daily-branches/README.md',
                'docs/validation/persistence-intents/README.md',
                'docs/validation/templates/chatgpt_prediction_task_v17.md',
                'docs/validation/templates/next_cycle_execution_v17.md',
                'docs/validation/README.md', 'docs/validation/cycle_04.md',
                'docs/jravan/phases/phase_3_rule_engine.md', 'docs/jravan/phases/phase_4_prediction_ui.md',
                'docs/jravan/phases/phase_5_odds_betting.md', 'docs/jravan/phases/phase_6_settlement_automation.md',
                'docs/validation/templates/chatgpt_prediction_task.md',
                contract_acceptance_path(root)}
    require(required <= {s['path'] for s in sources}, 'atomic release source coverage missing')
    for s in sources:
        require(hashlib.sha256(safe_path(root,s['path']).read_bytes()).hexdigest() == s['sha256'],
                'atomic release source hash mismatch: '+s['path'])
    for name in OWNERS[1:]:
        text = (root/'docs/manual'/name).read_text()
        require('\nmanual_release: v1.7.0\n' in text, 'Owner release mismatch: '+name)
    contract = json.loads((root/'docs/validation/contracts/cycle_04.json').read_text())
    require(contract['status'] == 'ACTIVE' and contract['next_release'] == 'v1.7.0' and
            contract['effective_race_date'] == state['effective_race_date'], 'cycle04 release mismatch')
    result = {'manual_release': 'v1.7.0', 'atomic_contract_verified': True,
              'activation_policy': 'MAIN_MERGE', 'operational_ready': False,
              'cycle_dates': contract['race_dates'], 'live_races_executed': None}
    if require_main:
        def git(*args):
            p = subprocess.run(['git', *args], cwd=root, text=True, capture_output=True)
            require(p.returncode == 0, 'main reference unavailable; fetch origin main before starting operations')
            return p.stdout
        main_sha = git('rev-parse', 'refs/remotes/origin/main').strip()
        main_manifest = json.loads(git('show', 'refs/remotes/origin/main:'+MANIFEST))
        require(main_manifest == manifest, 'v1.7.0 has not been merged into the fetched main contract')
        for source in sources:
            deployed = git('show', 'refs/remotes/origin/main:'+source['path']).encode('utf-8')
            require(hashlib.sha256(deployed).hexdigest() == source['sha256'],
                    'main/local release source mismatch: '+source['path'])
        # release hashだけでは未実行・失敗・古い受入を認証しない。
        from check_cycle04 import validate_acceptance
        validate_acceptance(root, contract)
        acceptance_path = contract.get('acceptance_path')
        deployed_acceptance = git('show', 'refs/remotes/origin/main:' + acceptance_path).encode('utf-8')
        require(deployed_acceptance == safe_path(root, acceptance_path).read_bytes(),
                'main/local acceptance mismatch')
        result.update(operational_ready=True, main_ref_commit=main_sha,
                      main_commit_time=git('log', '-1', '--format=%cI', main_sha).strip())
    return result


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument('--require-main', action='store_true')
    args = p.parse_args(argv)
    try:
        print(json.dumps(check(args.root,args.require_main),ensure_ascii=False,indent=2))
        return 0
    except (ValueError,OSError,KeyError,TypeError) as exc:
        print('運用開始確認不合格：'+str(exc),file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
