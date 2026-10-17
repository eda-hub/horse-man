"""保持中の旧台帳を含め、削除資料への全リンクと限定した表示変更を検査。"""
import tempfile
import unittest
from pathlib import Path
from cycle04_archive_links import verify_links,retarget
from cycle04_history import fixed_bytes,SOURCE_COMMIT
from cycle04_migration import ARCHIVABLE_PATHS,ROOT

class ArchiveLinkTest(unittest.TestCase):
    def test_inline_reference_html_encoded_and_root_relative_links_are_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);p=root/'nested/example.md';p.parent.mkdir()
            for text in ('[x](../docs/gone.md#part)', '[x][ref]\n[ref]: ../docs/gone.md',
                         '<a href="../docs/gone.md">x</a>', '<a href=../docs/gone.md>x</a>',
                         '<a href="../docs/gone&#46;md">x</a>', '![x](/docs/gone.md)',
                         '[x](../docs/%67one.md)', '[x](<../docs/gone.md>)'):
                with self.subTest(text=text):
                    p.write_text(text)
                    with self.assertRaises(ValueError):verify_links(root,{'docs/gone.md'})
                    p.write_bytes(retarget(root,p,p.read_bytes(),{'docs/gone.md'}))
                    verify_links(root,{'docs/gone.md'})
                    self.assertIn(SOURCE_COMMIT,p.read_text())
                    self.assertNotIn('#46;md',p.read_text())
    def test_unrelated_live_and_external_links_are_not_rewritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);p=root/'example.md'
            raw=b'[live](live.md) [web](https://example.com/gone.md) [here](#part)'
            self.assertEqual(retarget(root,p,raw,{'gone.md'}),raw)
    def test_retained_cycle03_is_exact_original_except_four_targets(self):
        path='docs/validation/cycle_03.md';original=fixed_bytes(ROOT,path)
        modified=retarget(ROOT,ROOT/path,original,ARCHIVABLE_PATHS)
        self.assertEqual((ROOT/path).read_bytes(),modified)
        self.assertEqual(modified.count((SOURCE_COMMIT+'/docs/').encode())-
                         original.count((SOURCE_COMMIT+'/docs/').encode()),4)
        verify_links(ROOT,ARCHIVABLE_PATHS)
    def test_non_utf8_html_does_not_disable_scanning(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);p=root/'old.html';p.write_bytes(b'\xe9<a href="gone.md">x</a>')
            with self.assertRaises(ValueError):verify_links(root,{'gone.md'})
            modified=retarget(root,p,p.read_bytes(),{'gone.md'})
            self.assertTrue(modified.startswith(b'\xe9'))
            p.write_bytes(modified);verify_links(root,{'gone.md'})

if __name__=='__main__':unittest.main()
