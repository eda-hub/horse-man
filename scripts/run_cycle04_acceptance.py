#!/usr/bin/env python3
"""全回帰の実行成功時だけ第4の合成受入を保存する。"""
import argparse
import hashlib
import io
import json
import sys
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = Path('docs/validation/reviews/cycle_04/acceptance.json')


def run(root):
    paths = sorted(set(root.glob('scripts/*.py')) | set(root.glob('docs/manual/*.md')) | {
        root / 'docs/validation/reviews/cycle_04/carryover.json',
        root / 'docs/validation/reviews/cycle_04/migration-manifest.json',
        root / 'docs/validation/reviews/cycle_04/summary.json',
        root / 'docs/validation/records/cycle_04/2026-10-17.json',
        root / '.agents/skills/horse-racing-forecast/SKILL.md',
        root / '.github/workflows/check-cycle04.yml',
        root / '.github/workflows/check-integration-acceptance.yml',
        root / 'docs/validation/contracts/cycle_04.json',
        root / 'docs/validation/contracts/cycle04_operations.md',
        root / 'docs/validation/execution-gates/contract-state.json',
        root / 'docs/validation/templates/chatgpt_prediction_task.md',
        root / 'docs/validation/market-chat-research/2026-10-13/replay-pages.json',
        root / 'docs/validation/class-transition/fixed-cases.json',
        root / 'docs/validation/class-transition/forward-plan.json',
    })
    before = {p: p.read_bytes() for p in paths}
    sys.path.insert(0, str(root / 'scripts'))
    suite = unittest.defaultTestLoader.discover(str(root / 'scripts'), pattern='test_*.py')
    stream = io.StringIO()
    with redirect_stdout(stream), redirect_stderr(stream):
        result = unittest.TextTestRunner(stream=stream, verbosity=1).run(suite)
    if not result.wasSuccessful() or result.skipped or any(p.read_bytes() != raw for p, raw in before.items()):
        print(stream.getvalue(), file=sys.stderr)
        raise ValueError('受入失敗・skip・入力変更があります。成功証跡を保存しません')
    return {'schema_version': 'cycle04-acceptance-v1', 'mode': 'SYNTHETIC', 'result': 'PASS',
            'tests_run': result.testsRun, 'failures': len(result.failures) + len(result.errors),
            'skipped': len(result.skipped), 'live_race_count': None,
            'performance_promotion': 'NOT_PERFORMED', 'formal_cutover': 'NOT_PERFORMED',
            'source_manifest': [{'path': p.relative_to(root).as_posix(),
                                 'sha256': hashlib.sha256(raw).hexdigest()} for p, raw in before.items()],
            'note': '正常系・異常系の合成検査。実レース、未完了研究、実runtime接続、正式版/有効日を認証しない。'}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--write', action='store_true')
    args = p.parse_args(argv)
    try:
        report = run(ROOT)
        if args.write:
            path = ROOT / OUTPUT
            path.parent.mkdir(parents=True, exist_ok=True)
            # 保存先の読戻しはGit側で別途行う。ここではローカル合成試験のみ。
            path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(f'合成受入成功：全{report["tests_run"]}回帰、失敗0、skip0。合成受入はmain反映・実測を認証しません。')
        return 0
    except (ValueError, OSError) as exc:
        print(f'合成受入不合格：{exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
