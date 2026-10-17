"""自己申告フラグや捏造参照で削除を許可せず、固定Gitの原入力を再計算する。"""
import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import cycle04_history as history
import cycle04_migration as migration

ROOT=Path(__file__).resolve().parents[1]

class RetainedHistoryTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.saved=history.read_json(ROOT,history.COLLECTION)
        manifest=migration.read(ROOT,migration.MANIFEST)
        paths={x['path'] for x in self.saved['source_manifest']}
        paths.update(x['path'] for x in manifest['files'] if (ROOT/x['path']).is_file())
        paths.update(migration.LIVE_READERS)
        paths.update([history.MANIFEST,migration.CARRYOVER])
        for path in paths:
            dest=self.root/path
            dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(ROOT/path,dest)
        self.root.joinpath('.git').symlink_to(ROOT/'.git',target_is_directory=True)

    def test_all_64_retained_inputs_reject_body_changes(self):
        self.assertEqual(history.verify_retained_inputs(self.root),64)
        for ref in self.saved['source_manifest']:
            path=self.root/ref['path']; original=path.read_bytes()
            with self.subTest(path=ref['path']):
                try:
                    path.write_bytes(original+b'\nunauthorized change\n')
                    with self.assertRaisesRegex(ValueError,'保持する履歴原入力'):
                        history.verify_retained_inputs(self.root)
                finally:path.write_bytes(original)

    def test_result_table_change_fails_both_real_recomputations_and_migration(self):
        path=self.root/'docs/validation/records/2026-10-04.md'
        original=path.read_text()
        changed=original.replace('3 ダノンダックス','3 別内容',1)
        self.assertNotEqual(original,changed)
        path.write_text(changed)
        for check in (history.recomputed_report,history.recompute,migration.validate_manifest):
            with self.subTest(check=check.__name__),self.assertRaisesRegex(ValueError,'保持する履歴原入力'):
                check(self.root)

    def test_deleted_or_symlinked_source_is_rejected(self):
        path=self.root/'docs/validation/records/2026-10-04.md'
        original=path.read_bytes();path.unlink()
        with self.assertRaisesRegex(ValueError,'保持する履歴原入力'):
            history.recompute(self.root)
        elsewhere=self.root/'original.md';elsewhere.write_bytes(original)
        path.symlink_to(elsewhere)
        with self.assertRaisesRegex(ValueError,'保持する履歴原入力'):
            history.recompute(self.root)

    def test_allowed_links_and_separate_correction_preserve_originals(self):
        correction=self.root/'docs/validation/review-revisions/legacy-correction.json'
        correction.parent.mkdir(parents=True)
        correction.write_text(json.dumps({'reason':'公式訂正の別履歴',
            'source_path':'docs/validation/records/2026-10-04.md',
            'source_sha256':next(x['sha256'] for x in self.saved['source_manifest']
                if x['path']=='docs/validation/records/2026-10-04.md')}))
        self.assertEqual(history.recomputed_report(self.root),self.saved)
        migration.validate_manifest(self.root)
        path=self.root/'docs/validation/records/2026-10-04.md'
        path.write_bytes(path.read_bytes()+b'\ncorrection\n')
        with self.assertRaisesRegex(ValueError,'保持する履歴原入力'):
            history.recompute(self.root)

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
