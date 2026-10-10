import unittest
from check_legacy_fact_followup import classify_paths
from import_legacy_subjects import parse_profile

class ExplicitPathTests(unittest.TestCase):
    def spec(self, **values):
        return {'kind': 'ANCESTOR_POSITIONS', 'depth': 5, 'prefix': '', 'expected_present': True, **values}

    def test_maternal_containment_does_not_prove_paternal_chain(self):
        status, paths = classify_paths(self.spec(kind='SIRE_CHAIN', prefix='S'), ['SDS', 'DS'], [])
        self.assertEqual((status, paths), ('FACT_COMPONENT_CONTRADICTED', []))

    def test_nested_paternal_roots_have_explicit_paths(self):
        self.assertEqual(classify_paths(self.spec(kind='SIRE_CHAIN', prefix='S'), ['SS', 'DSS'], []), ('FACT_COMPONENT_MATCHED', ['SS']))

    def test_negative_containment_requires_complete_ancestry(self):
        self.assertEqual(classify_paths(self.spec(expected_present=False), [], [{'path': 'D', 'status': 'UNVERIFIED'}])[0], 'ANCESTRY_INCOMPLETE')
        self.assertEqual(classify_paths(self.spec(expected_present=False), [], [])[0], 'FACT_COMPONENT_MATCHED')

    def test_only_claimed_side_and_five_generations_count(self):
        self.assertEqual(classify_paths(self.spec(prefix='D'), ['SS', 'DSSSSS'], []), ('FACT_COMPONENT_CONTRADICTED', []))
        self.assertEqual(classify_paths(self.spec(prefix='D'), ['DSSSS'], [])[0], 'FACT_COMPONENT_MATCHED')

    def test_cross_and_explicit_generations_are_not_interchangeable(self):
        self.assertEqual(classify_paths(self.spec(expected_generations='AT_LEAST_TWO_PATHS'), ['SSS'], [])[0], 'FACT_COMPONENT_CONTRADICTED')
        self.assertEqual(classify_paths(self.spec(expected_generations=[3, 4]), ['SSS', 'DSSS'], [])[0], 'FACT_COMPONENT_MATCHED')
        self.assertEqual(classify_paths(self.spec(expected_generations=[3, 4]), ['SSS', 'DSSSS'], [])[0], 'FACT_COMPONENT_CONTRADICTED')

    def test_ambiguous_side_or_depth_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'side prefix'):
            classify_paths(self.spec(prefix='maternal'), [], [])
        with self.assertRaisesRegex(ValueError, 'bound'):
            classify_paths(self.spec(depth=6), [], [])

    def test_profile_father_role_and_independent_id_are_required(self):
        raw = ('<title>シランケド｜JBIS</title><a href="/horse/0001322201/">本人</a>'
               '<dt>生年月日</dt><dd>2020.02.07</dd>'
               '<div class="data-3__male-hdg pc-only">父</div><div class="data-3__male"><div>'
               '<a href="/horse/0001181460/" class="txt-link">デクラレーションオブウォー(USA)</a>').encode()
        self.assertEqual(parse_profile(raw, '0001322201')['father_id'], '0001181460')
        with self.assertRaises(ValueError):
            parse_profile(raw.replace('父'.encode(), '母'.encode()), '0001322201')
        with self.assertRaises(ValueError):
            parse_profile(raw, '0001053814')

if __name__ == '__main__':
    unittest.main()
