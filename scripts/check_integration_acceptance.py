#!/usr/bin/env python3
"""Read-only integration acceptance using an authentic fetched origin/main tree."""
import argparse
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

from check_prediction_compliance import ComplianceError
from cycle04_operations import require
import run_release_readiness as readiness

UNMERGED = 'v1.7.0 has not been merged into the fetched main contract'


def git(root, *args):
    result = subprocess.run(['git', *args], cwd=root, text=True, capture_output=True)
    require(result.returncode == 0, 'Git input unavailable: ' + ' '.join(args))
    return result.stdout.strip()


def check_main_reference(root, expected_main_sha=None):
    root = Path(root).resolve()
    atomic = readiness.check(root)
    manifest = json.loads((root / readiness.MANIFEST).read_text())
    protected = {root / s['path']: (root / s['path']).read_bytes() for s in manifest['source_manifest']}
    protected[root / readiness.MANIFEST] = (root / readiness.MANIFEST).read_bytes()
    main_sha = git(root, 'rev-parse', 'refs/remotes/origin/main')
    require(expected_main_sha is None or main_sha == expected_main_sha,
            'fetched main differs from expected input')
    with tempfile.TemporaryDirectory(prefix='horse-man-main-check-') as directory:
        path = Path(directory) / 'main'
        added = False
        try:
            git(root, 'worktree', 'add', '--detach', str(path), main_sha)
            added = True
            require(git(path, 'rev-parse', 'HEAD') == main_sha, 'main worktree identity mismatch')
            # 取得済みmainはそのcommitの入口で検査する。候補で追加した
            # release固定対象を旧mainへ遡及適用して未マージ判定を阻害しない。
            process = subprocess.run(
                ['python3', str(path / 'scripts/run_release_readiness.py'),
                 '--root', str(path), '--require-main'],
                cwd=path, text=True, capture_output=True)
            require(process.returncode == 0,
                    'fetched main start check failed: ' + process.stderr.strip())
            deployed = json.loads(process.stdout)
            # 旧版入口にも未検証・失敗・古い受入を認証させない。
            from check_cycle04 import validate_acceptance
            main_contract = json.loads((path / 'docs/validation/contracts/cycle_04.json').read_text())
            validate_acceptance(path, main_contract)
            require(deployed.get('operational_ready') is True, 'fetched main is not operational ready')
            require(deployed['main_ref_commit'] == main_sha, 'main reference changed during check')
            main_manifest = json.loads((path / readiness.MANIFEST).read_text())
            try:
                branch = readiness.check(root, require_main=True)
            except ComplianceError as exc:
                # Missing refs, changed owners or failed atomic checks are not an
                # expected rejection. Only the exact unmerged-contract condition is.
                require(str(exc) == UNMERGED and main_manifest != manifest,
                        'unexpected branch start rejection: ' + str(exc))
                branch = {'operational_ready': False, 'status': 'UNMERGED_CONTRACT_REJECTED',
                          'reason': str(exc)}
            else:
                require(main_manifest == manifest, 'different contract was accepted as main')
                branch['status'] = 'MAIN_CONTRACT_MATCHED'
        finally:
            if added:
                git(root, 'worktree', 'remove', '--force', str(path))
    require(all(p.read_bytes() == raw for p, raw in protected.items()),
            'integration check changed monitored source files')
    return {'schema_version': 'integration-start-check-v1', 'read_only': True,
            'main_ref_commit': main_sha, 'main': deployed, 'branch': branch,
            'atomic': atomic, 'main_manifest_sources': len(main_manifest['source_manifest']),
            'branch_manifest_sources': len(manifest['source_manifest']),
            'monitored_sources_unchanged': True, 'live_races_executed': None,
            'performance_promoted': False, 'runtime_connected': False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--expected-main-sha', help='optional frozen input for this execution')
    parser.add_argument('--full', action='store_true', help='also recompute cycle03 and synthetic acceptance')
    args = parser.parse_args(argv)
    try:
        report = check_main_reference(args.root, args.expected_main_sha)
        if args.full:
            subprocess.run(['python3', 'scripts/cycle04_history.py', '--audit'],
                           cwd=args.root, check=True)
            from run_cycle04_acceptance import run
            acceptance = run(args.root.resolve())
            report['synthetic_acceptance'] = {k: v for k, v in acceptance.items() if k != 'source_manifest'}
            report['synthetic_acceptance']['source_manifest_sha256'] = hashlib.sha256(
                json.dumps(acceptance['source_manifest'], ensure_ascii=False, sort_keys=True,
                           separators=(',', ':')).encode()).hexdigest()
            report['synthetic_acceptance']['source_count'] = len(acceptance['source_manifest'])
        print('INTEGRATION_ACCEPTANCE_JSON ' + json.dumps(report, ensure_ascii=False, sort_keys=True))
        return 0
    except (ValueError, OSError, KeyError, TypeError, subprocess.CalledProcessError) as exc:
        print('統合受入不合格：' + str(exc))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
