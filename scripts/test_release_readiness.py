"""候補branch・改変mainで有効化せず、同一全契約のmainだけ認証する。"""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import run_release_readiness as readiness
from build_v170_manifest import build
from check_prediction_compliance import ComplianceError

ROOT=Path(__file__).resolve().parents[1]


class ReleaseReadiness(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        for item in build(ROOT)['source_manifest']:
            p=self.root/item['path'];p.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(ROOT/item['path'],p)
        self.acceptance_path = 'docs/validation/reviews/cycle_04/acceptance.json'
        self.write_acceptance()
        manifest=build(self.root)
        (self.root/readiness.MANIFEST).write_text(json.dumps(manifest))
        self.git('init','-q')
        # 一時fixtureだけのGit設定。子maintenanceがcleanup中にobjectsを再作成しない。
        self.git('config','maintenance.auto','false')
        self.git('config','maintenance.autoDetach','false')
        self.git('config','gc.auto','0')
        self.git('config','gc.autoDetach','false')
        self.git('config','user.email','test@example.invalid')
        self.git('config','user.name','release test')
        self.git('add','.')
        self.git('commit','-qm','正式切替の合成fixture')

    def write_acceptance(self):
        from test_cycle04_acceptance import synthetic_acceptance
        (self.root/self.acceptance_path).write_text(json.dumps(synthetic_acceptance(self.root)))

    def reseal(self):
        (self.root/readiness.MANIFEST).write_text(json.dumps(build(self.root)))
        self.git('add', '.')
        self.git('commit', '-qm', '受入境界の合成fixture')
        self.main_ref()

    def test_main_rejects_not_run_failed_skipped_and_stale_acceptance(self):
        for state in ('NOT_RUN', 'FAIL', 'SKIPPED', 'STALE'):
            self.write_acceptance()
            path = self.root/self.acceptance_path
            report = json.loads(path.read_text())
            if state in ('NOT_RUN', 'FAIL'):
                report.update(result=state, tests_run=None, failures=None, skipped=None)
            elif state == 'SKIPPED':
                report['skipped'] = 1
            else:
                report['source_manifest'][0]['sha256'] = '0'*64
            path.write_text(json.dumps(report))
            self.reseal()
            with self.subTest(state=state), self.assertRaisesRegex(
                    ComplianceError, 'acceptance not passed|stale acceptance'):
                readiness.check(self.root, True)

    def git(self,*args):
        return subprocess.run(['git',*args],cwd=self.root,check=True,capture_output=True,text=True).stdout.strip()

    def main_ref(self):
        self.git('update-ref','refs/remotes/origin/main',self.git('rev-parse','HEAD'))

    def test_unmerged_candidate_is_never_operational_ready(self):
        self.assertFalse(readiness.check(self.root)['operational_ready'])
        with self.assertRaisesRegex(ComplianceError,'main reference unavailable'):
            readiness.check(self.root,True)

    def test_identical_main_contract_is_ready(self):
        self.main_ref()
        result=readiness.check(self.root,True)
        self.assertTrue(result['operational_ready'])
        self.assertEqual(result['main_ref_commit'],self.git('rev-parse','HEAD'))
        self.assertIsNone(result['live_races_executed'])

    def test_main_owner_modified_without_resealing_manifest_is_rejected(self):
        p=self.root/'docs/manual/30_betting.md';original=p.read_bytes()
        p.write_bytes(original+'\n意図しない変更\n'.encode());self.git('add','.');self.git('commit','-qm','不整合fixture')
        self.main_ref();p.write_bytes(original)
        with self.assertRaisesRegex(ComplianceError,'main/local release source mismatch'):
            readiness.check(self.root,True)

    def test_local_owner_modified_after_atomic_fix_is_rejected(self):
        self.main_ref()
        p=self.root/'docs/manual/60_market.md';p.write_text(p.read_text()+'\n改変\n')
        with self.assertRaisesRegex(ComplianceError,'source hash mismatch'):
            readiness.check(self.root,True)


class MainReferenceChecks(unittest.TestCase):
    setUp = ReleaseReadiness.setUp
    git = ReleaseReadiness.git
    main_ref = ReleaseReadiness.main_ref
    write_acceptance = ReleaseReadiness.write_acceptance

    def test_unverified_main_acceptance_is_not_an_expected_unmerged_rejection(self):
        path = self.root / self.acceptance_path
        report = json.loads(path.read_text())
        report.update(result='NOT_RUN', tests_run=None, failures=None, skipped=None)
        path.write_text(json.dumps(report))
        (self.root / readiness.MANIFEST).write_text(json.dumps(build(self.root)))
        self.git('add', '.')
        self.git('commit', '-qm', '未検証mainの合成fixture')
        self.main_ref()
        with self.assertRaisesRegex(ComplianceError, 'acceptance not passed'):
            self.check()

    def check(self, expected=None):
        from check_integration_acceptance import check_main_reference
        return check_main_reference(self.root, expected)

    def test_real_git_worktree_matches_ref_and_is_removed(self):
        self.main_ref()
        before = self.git('worktree', 'list', '--porcelain')
        result = self.check(self.git('rev-parse', 'HEAD'))
        self.assertTrue(result['main']['operational_ready'])
        self.assertEqual(result['branch']['status'], 'MAIN_CONTRACT_MATCHED')
        self.assertTrue(result['monitored_sources_unchanged'])
        self.assertEqual(before, self.git('worktree', 'list', '--porcelain'))

    def test_unmerged_contract_is_expected_rejection_and_keeps_sources(self):
        self.main_ref()
        main_sha = self.git('rev-parse', 'HEAD')
        p = self.root / 'docs/manual/60_market.md'
        p.write_text(p.read_text() + '\n合成変更\n')
        (self.root / readiness.MANIFEST).write_text(json.dumps(build(self.root)))
        before = self.git('worktree', 'list', '--porcelain')
        result = self.check(main_sha)
        self.assertTrue(result['main']['operational_ready'])
        self.assertFalse(result['branch']['operational_ready'])
        self.assertEqual(result['branch']['status'], 'UNMERGED_CONTRACT_REJECTED')
        self.assertEqual(before, self.git('worktree', 'list', '--porcelain'))

    def test_missing_main_reference_does_not_become_expected_rejection(self):
        with self.assertRaisesRegex(ComplianceError, 'Git input unavailable'):
            self.check()

    def test_unfrozen_main_is_rejected(self):
        self.main_ref()
        with self.assertRaisesRegex(ComplianceError, 'differs from expected input'):
            self.check('0' * 40)

    def test_modified_source_is_not_expected_unmerged_rejection(self):
        self.main_ref()
        p = self.root / 'docs/manual/60_market.md'
        p.write_text(p.read_text() + '\n不整合\n')
        with self.assertRaisesRegex(ComplianceError, 'source hash mismatch'):
            self.check()
