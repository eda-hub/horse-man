"""非価格入力の組立/再開と任意市場の接続を実validatorで回帰する。"""
import copy
import json
import unittest
from unittest.mock import patch
from chat_entry_assembly import assemble
import test_cycle04_workflow as operations
import test_market_sidecar as markets
import cycle04_workflow as workflow
from test_recommendation import DATE, RACE


class HelperMarketIndependence(unittest.TestCase):
    def setUp(self):
        self.case=operations.OperationalWorkflow();self.case.setUp();self.addCleanup(self.case.doCleanups)
        self.root=self.case.root;self.entry=copy.deepcopy(self.case.entry);self.case.register()
        self.input=json.loads((self.root/self.entry['operations']['inputs_ref']['artifact_path']).read_text())

    def test_helper_assembly_needs_no_market_and_does_not_mutate_fixed_files(self):
        before={str(p):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        with patch('chat_entry_assembly.verify_saved',return_value={'input':self.input}):
            candidate=assemble(self.root,self.entry,{'synthetic':'capture'},{'synthetic':'conversion'})
        self.assertTrue(candidate['read_only']);self.assertFalse(candidate['ledger_saved'])
        self.assertEqual(before,{str(p):p.read_bytes() for p in self.root.rglob('*') if p.is_file()})

    def test_registered_market_states_preserve_helper_inputs_prediction_recommendation_and_kpis(self):
        workflow.record_prediction(self.root,DATE,self.entry);self.case.select()
        self.entry['phase']='FINAL';workflow.record_prediction(self.root,DATE,self.entry)
        day,_=workflow.read_day(self.root,DATE)
        rec_path=day['races'][RACE]['recommendation_gate_path'];rec_gate=json.loads((self.root/rec_path).read_text())
        paths=[self.entry['operations']['prediction_ref']['artifact_path'],self.entry['operations']['inputs_ref']['artifact_path'],
               rec_path,rec_gate['evidence_ref']['artifact_path']]
        raw={p:(self.root/p).read_bytes() for p in paths}
        frozen={k:copy.deepcopy(day['kpis'][k]) for k in ('production','recommendation')}
        for n,state in enumerate(('NOT_ATTEMPTED','FAILED','DEADLINE_STOPPED','ACQUIRED')):
            p=markets.payload(state)
            ref=self.case.fixture.artifact('helper-market-'+str(n),'markets/helper-'+str(n)+'.json',p,at='10:02')
            workflow.record_market(self.root,DATE,{'race_id':RACE,'market_ref':ref})
            after,_=workflow.read_day(self.root,DATE)
            self.assertEqual({k:after['kpis'][k] for k in frozen},frozen)
            self.assertEqual({path:(self.root/path).read_bytes() for path in paths},raw)
            self.assertNotEqual(p['data_cutoff'],after['races'][RACE]['data_cutoff'])
            snapshot={str(path):path.read_bytes() for path in self.root.rglob('*') if path.is_file()}
            with patch('chat_entry_assembly.verify_saved',return_value={'input':self.input}):
                candidate=assemble(self.root,self.entry,{'synthetic':'capture'},{'synthetic':'conversion'})
            self.assertTrue(candidate['read_only'])
            self.assertEqual(snapshot,{str(path):path.read_bytes() for path in self.root.rglob('*') if path.is_file()})


if __name__=='__main__':unittest.main()
