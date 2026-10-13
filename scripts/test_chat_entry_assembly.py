import copy
import json
import unittest
from unittest.mock import patch

import test_cycle04_workflow as fixtures
from chat_entry_assembly import assemble


class EntryAssembly(unittest.TestCase):
    def setUp(self):
        self.case = fixtures.OperationalWorkflow(); self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.case.register(); self.root = self.case.root
        self.entry = copy.deepcopy(self.case.entry)
        self.input = json.loads((self.root/self.entry['operations']['inputs_ref']['artifact_path']).read_text())

    def preview(self, entry=None, proof=None):
        with patch('chat_entry_assembly.verify_saved', return_value=proof or {'input':self.input}):
            return assemble(self.root, entry or self.entry, {'capture':'fixture'}, {'conversion':'fixture'})

    def test_preview_runs_real_validator_without_writing_or_recreating_prediction(self):
        before = {str(p.relative_to(self.root)):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        entry = copy.deepcopy(self.entry)
        result = self.preview()
        self.assertTrue(result['read_only']); self.assertFalse(result['ledger_saved'])
        self.assertEqual(self.entry, entry)
        self.assertEqual(before, {str(p.relative_to(self.root)):p.read_bytes() for p in self.root.rglob('*') if p.is_file()})

    def test_conversion_substitution_and_final_before_selection_rejected(self):
        wrong = copy.deepcopy(self.input); wrong['horse_numbers'] = [1]
        with self.assertRaises(ValueError): self.preview(proof={'input':wrong})
        entry = copy.deepcopy(self.entry); entry['phase'] = 'FINAL'
        with self.assertRaises(ValueError): self.preview(entry)

    def test_wrong_race_and_market_purchase_data_cannot_be_accepted(self):
        entry = copy.deepcopy(self.entry); entry['race_id'] = 'other-race'
        with self.assertRaises(ValueError): self.preview(entry)
        entry = copy.deepcopy(self.entry); entry['market'] = {'status':'ACQUIRED','odds':0}
        with self.assertRaises(ValueError): self.preview(entry)


if __name__ == '__main__': unittest.main()
