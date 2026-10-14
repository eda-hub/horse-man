import unittest
from pathlib import Path
from check_foreign_pedigree_review import Document, parse_table, check

class ForeignReviewTests(unittest.TestCase):
    def test_incomplete_table_cannot_be_promoted(self):
        with self.assertRaises(AssertionError):
            parse_table(Document(b'<table class="blood_table"><tr><td>unknown</td></tr></table>').root)

    def test_saved_originals_and_registry_paths(self):
        if not Path('data/pedigree/reconciliations/2026-10-10-foreign-review').exists():
            self.skipTest('saved dataset is not present')
        result = check()
        self.assertEqual(result['ancestor_positions'], result['registered_rows'] * 62)
        self.assertEqual(result['finished'] + result['scratched'], 42)

if __name__ == '__main__':
    unittest.main()
