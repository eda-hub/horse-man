"""自己申告フラグや捏造参照で削除を許可せず、固定Gitの原入力を再計算する。"""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import cycle04_history as history
import cycle04_migration as migration

ROOT=Path(__file__).resolve().parents[1]

class FixedHistoryTest(unittest.TestCase):
    def test_deleted_worktree_decisions_and_collection_remain_readable_from_git(self):
        for path in (history.DECISIONS,history.COLLECTION):
            self.assertFalse((ROOT/path).exists())
            self.assertIsInstance(history.read_json(ROOT,path),dict)
        result=history.recompute(ROOT)
        self.assertEqual(result['inputs'],64)
        self.assertEqual(result['pending_kpi_decisions'],57)
        self.assertEqual(result['scope']['initial'],158)
    def test_all_zero_blob_and_forged_deletion_flags_are_rejected(self):
        original=migration.read
        manifest=original(ROOT,migration.MANIFEST)
        for mutate in (
            lambda d:[x.update(git_blob_sha1='0'*40) for x in d['files']],
            lambda d:d.update(source_commit='0'*40),
            lambda d:d['files'][0].update(git_blob_sha1='0'*40,decision='DELETE_VERIFIED',
                       fixed_history_verified=True,references_retargeted=True,recomputed_results_verified=True),
            lambda d:d['files'].pop(),
        ):
            bad=copy.deepcopy(manifest);mutate(bad)
            with patch.object(migration,'read',side_effect=lambda r,p: bad if p==migration.MANIFEST else original(r,p)):
                with self.assertRaises(ValueError):migration.validate_manifest(ROOT)
    def test_missing_git_history_is_failure_not_a_skip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            with self.assertRaisesRegex(ValueError,'固定履歴'):
                history.fixed_bytes(root,history.COLLECTION)
    def test_real_blob_wrong_body_hash_is_rejected(self):
        item=json.loads((ROOT/history.MANIFEST).read_text())['files'][0]
        with self.assertRaisesRegex(ValueError,'本文hash'):
            history.fixed_bytes(ROOT,item['path'],item['git_blob_sha1'],'0'*64)
    def test_recomputation_must_match_even_when_boolean_flags_are_true(self):
        from build_cycle03_review import build
        def wrong(*args,**kwargs):
            report=build(*args,**kwargs);report['pending_kpi_decision_count']=0;return report
        with patch('build_cycle03_review.build',side_effect=wrong):
            with self.assertRaisesRegex(ValueError,'再計算値'):
                migration.validate_manifest(ROOT)

if __name__=='__main__':unittest.main()
