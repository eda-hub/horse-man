import copy
import unittest
from pathlib import Path
from pedigree_registry import read, digest
from check_pedigree_alternative import DIRECTORY, parts, check_sheet


class AlternativeEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = Path(__file__).resolve().parents[1] / DIRECTORY
        cls.sheets = parts(cls.directory, 'pedigree_evidence')
        cls.profiles = {r['id']: r for r in read(cls.directory / 'published_aliases.json')['records']}
        cls.decisions = {r['netkeiba_id']: r for r in read(cls.directory / 'source_resolutions.json')['records']}

    def test_wrong_source_identity_cannot_become_selected_ancestor(self):
        for identity in ('000a011d67', '000a02545a'):
            original = next(s for s in self.sheets if any(a.get('resolution_id') == identity for a in s['resolved_ancestors'].values()))
            check_sheet(original, self.profiles, self.decisions)
            changed = copy.deepcopy(original)
            path = next(p for p, a in changed['resolved_ancestors'].items() if a.get('resolution_id') == identity)
            changed['resolved_ancestors'][path]['provider'] = 'NETKEIBA'
            changed['resolved_ancestors'][path]['id'] = identity
            changed['record_hash'] = digest({k: changed[k] for k in [
                'target','birth_year','netkeiba_ancestors','umanity_ancestors','resolved_ancestors','sources']})
            with self.assertRaises(AssertionError):
                check_sheet(changed, self.profiles, self.decisions)

    def test_secondary_missing_is_preserved_and_unknown_alias_is_not_accepted(self):
        original = next(s for s in self.sheets if s['secondary_missing_positions'])
        check_sheet(original, self.profiles, self.decisions)
        changed = copy.deepcopy(original)
        changed['secondary_missing_positions'] = []
        with self.assertRaises(AssertionError):
            check_sheet(changed, self.profiles, self.decisions)
        alias_sheet = next(s for s in self.sheets if s['aliases_used'])
        check_sheet(alias_sheet, self.profiles, self.decisions)
        with self.assertRaises(AssertionError):
            check_sheet(alias_sheet, {}, self.decisions)

    def test_birth_year_discrepancy_requires_original_and_decision(self):
        sheet = next(s for s in self.sheets if any(a['id'] == '000a01d79e' for a in s['netkeiba_ancestors'].values()))
        check_sheet(sheet, self.profiles, self.decisions)
        with self.assertRaises(AssertionError):
            check_sheet(sheet, self.profiles, {})
        changed = copy.deepcopy(sheet)
        path = next(p for p, a in changed['netkeiba_ancestors'].items() if a['id'] == '000a01d79e')
        changed['netkeiba_ancestors'][path]['birth_year'] = 1996
        with self.assertRaises(AssertionError):
            check_sheet(changed, self.profiles, self.decisions)


if __name__ == '__main__':
    unittest.main()
