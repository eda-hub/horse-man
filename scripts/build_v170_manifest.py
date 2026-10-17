#!/usr/bin/env python3
"""v1.7.0の全入口・Owner・監査を同じbytesへ固定する（main有効化とは別）。"""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUTPUT='docs/validation/contracts/v170-release.json'


def build(root):
    paths=set(root.glob('docs/manual/*.md')) | set(root.glob('scripts/*.py')) | set(root.glob('docs/jravan/phases/phase_[3456]_*.md'))
    paths |= {root/p for p in ('.github/workflows/check-cycle04.yml','.github/workflows/check-integration-acceptance.yml','AGENTS.md','DECISIONS.md','README.md','docs/jravan/phases/README.md','docs/jravan/00_project_plan.md',
        'docs/jravan/04_prediction_engine.md','docs/jravan/07_review_ai.md','docs/jravan/10_operations.md',
        'docs/validation/README.md','docs/validation/cycle_04.md','docs/validation/contracts/cycle_04.json','docs/validation/contracts/cycle04_operations.md',
        'docs/validation/reviews/cycle_04/carryover.json','docs/validation/reviews/cycle_04/migration-manifest.json','docs/validation/reviews/cycle_04/summary.json','docs/validation/records/cycle_04/2026-10-17.json','.agents/skills/horse-racing-forecast/SKILL.md','docs/validation/reviews/cycle_04/acceptance.json','docs/validation/execution-gates/contract-state.json',
        'docs/validation/reviews/cycle_03/decisions.json','docs/validation/templates/chatgpt_prediction_task.md',
        'docs/validation/market-chat-acquisition.md','docs/validation/contracts/chat-market-acquisition.json',
        'docs/validation/market-chat-research/2026-10-13/replay-pages.json',
        'docs/validation/probability-presentation.md','docs/validation/dependency-risk.md',
        'docs/validation/class-transition/fixed-cases.json','docs/validation/class-transition/forward-plan.json')}
    return {'schema_version':'manual-release-readiness-v1','manual_release':'v1.7.0',
            'activation_policy':'MAIN_MERGE','cycle_id':'cycle_04','performance_promotion':'NOT_APPROVED',
            'source_manifest':[{'path':p.relative_to(root).as_posix(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
                               for p in sorted(paths)]}


if __name__=='__main__':
    (ROOT/OUTPUT).write_text(json.dumps(build(ROOT),ensure_ascii=False,indent=2)+'\n')
    print('v1.7.0の切替対象hashを固定。main確認・実測は別途必要。')
