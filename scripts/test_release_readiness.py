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
        manifest=build(self.root)
        (self.root/readiness.MANIFEST).write_text(json.dumps(manifest))
        self.git('init','-q')
        self.git('config','user.email','test@example.invalid')
        self.git('config','user.name','release test')
        self.git('add','.')
        self.git('commit','-qm','正式切替の合成fixture')

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
