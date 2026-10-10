"""対象一覧の危険な誤解釈・欠落・遡及を拒否する回帰テスト。"""
import copy
import unittest
from pathlib import Path
from unittest.mock import patch

import check_designated_ancestor_scope as scope


ROOT = Path(__file__).resolve().parent.parent


class DesignatedAncestorScopeTests(unittest.TestCase):
    def rejected_edit(self, relative_path, edit, message):
        original = scope.read
        path = ROOT / relative_path
        document = copy.deepcopy(original(path))
        edit(document)
        def amended(requested):
            return document if Path(requested) == path else original(requested)
        with patch.object(scope, 'read', side_effect=amended):
            with self.assertRaisesRegex(ValueError, message):
                scope.check(ROOT)

    def test_missing_term_cannot_complete_checkpoint(self):
        self.rejected_edit(scope.BASE / 'designated-ancestor-batches/batch-06.json',
                           lambda d: d['reviews'].pop(), 'batch coverage')

    def test_same_name_cannot_replace_canonical_individual(self):
        self.rejected_edit(scope.BASE / 'designated-ancestor-batches/batch-05.json',
                           lambda d: d['reviews'][0].update(horse_key='jbis-0000337102'),
                           'term identity mapping')

    def test_danehill_dancer_is_not_danehill_exact_mention(self):
        self.rejected_edit(scope.BASE / 'designated-ancestor-batches/batch-04.json',
                           lambda d: d['reviews'][2].update(excluded_name_mentions=[]),
                           'different-name exclusion')

    def test_nasrullah_descendants_are_not_literal_inclusion(self):
        self.rejected_edit(scope.BASE / 'designated-ancestor-batches/batch-02.json',
                           lambda d: d['reviews'][4].update(roles=['ANCESTOR_INCLUSION']),
                           'Nasrullah descendant scope')

    def test_country_belongs_to_ancestor_not_its_parent(self):
        self.rejected_edit(scope.TARGET,
                           lambda d: d['subjects'][0]['training_country'].update(country='US'),
                           'existing country provenance')

    def test_unsearched_does_not_trigger_user_confirmation(self):
        self.rejected_edit(scope.TARGET,
                           lambda d: d['subjects'][3]['training_country'].update(user_input_required=True),
                           'unsearched is not zero matches')

    def test_future_review_is_rejected(self):
        self.rejected_edit(scope.TARGET,
                           lambda d: d.update(data_cutoff='2099-01-01T00:00:00+00:00',
                                              reviewed_at='2099-01-01T00:00:00+00:00'),
                           'review cutoff')


if __name__ == '__main__':
    unittest.main()
