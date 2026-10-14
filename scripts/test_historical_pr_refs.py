import copy
import unittest
from pathlib import Path

from check_historical_pr_refs import REVIEW, read, index_evidence, intent_issues, verify_tree

ROOT = Path(__file__).resolve().parents[1]

class HistoricalPRRefTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evidence = read(ROOT / REVIEW / 'git-evidence.json.gz')

    def test_complete_pr_reference_evidence_is_valid(self):
        self.assertEqual(len(index_evidence(self.evidence)), 60)

    def test_recursive_tree_truncation_cannot_prove_absence(self):
        tree = copy.deepcopy(next(iter(self.evidence['docs'].values())))
        tree['truncated'] = True
        with self.assertRaisesRegex(ValueError, 'complete tree'):
            verify_tree(tree, True)

    def test_removed_file_invalidates_git_tree_hash(self):
        tree = copy.deepcopy(next(iter(self.evidence['docs'].values())))
        tree['tree'].pop()
        with self.assertRaises(ValueError):
            verify_tree(tree, True)

    def test_pr_history_page_omission_is_rejected(self):
        e = copy.deepcopy(self.evidence)
        e['collection']['commit_pages'].pop()
        with self.assertRaisesRegex(ValueError, 'all PR histories'):
            index_evidence(e)

    def test_changed_original_body_is_rejected(self):
        e = copy.deepcopy(self.evidence)
        next(iter(e['files'].values()))['content'] += '\n'
        with self.assertRaisesRegex(ValueError, 'Git blob bytes'):
            index_evidence(e)

    def test_missing_candidate_body_is_rejected(self):
        e = copy.deepcopy(self.evidence)
        e['files'].pop(next(iter(e['files'])))
        with self.assertRaisesRegex(ValueError, 'candidate bodies'):
            index_evidence(e)

    def test_valid_schema_does_not_override_wrong_date_or_branch(self):
        obj = {'schema_version': 'prediction-persistence-intent-v1', 'race_date_jst': '2026-10-03', 'working_branch': 'prediction/2026-10-03', 'required_race_ids': ['R1'], 'deadline_jst': '2026-10-03T09:50:00+09:00'}
        self.assertEqual(intent_issues(obj, 'validation/persistence-intents/2026-10-03/morning-v2.json', '2026-10-03'), [])
        obj['working_branch'] = 'main'
        self.assertIn('WORKING_BRANCH_MISMATCH', intent_issues(obj, 'validation/persistence-intents/2026-10-03/morning-v2.json', '2026-10-03'))
        self.assertIn('DATE_OR_PATH_MISMATCH', intent_issues(obj, 'validation/persistence-intents/2026-10-04/morning-v2.json', '2026-10-03'))

    def test_failed_attempt_is_history_even_with_valid_schema(self):
        issues = intent_issues({'schema_version': 'prediction-persistence-intent-v1'}, 'validation/persistence-intents/failed-attempts/morning.json', '2026-10-03')
        self.assertIn('FAILED_ATTEMPT_HISTORY_ONLY', issues)

if __name__ == '__main__':
    unittest.main()
