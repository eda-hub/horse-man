import json
import unittest
from chat_review_package import package
from cycle04_operations import fingerprint
import cycle04_workflow as workflow
import test_cycle04_workflow as operations
from test_recommendation import DATE, RACE


class ReviewPackage(unittest.TestCase):
    def setUp(self):
        self.case=operations.OperationalWorkflow();self.case.setUp();self.addCleanup(self.case.doCleanups)
        self.root=self.case.root;self.case.register();self.now=DATE+'T12:00:00+09:00'

    def manifest(self):
        path='docs/validation/records/cycle_04/'+DATE+'.json'
        return {'day_refs':[{'artifact_path':path,'sha256':fingerprint((self.root/path).read_bytes())}],
                'historical_purchase_refs':[]}

    def test_unfinalized_no_prediction_and_no_recommendation_are_retained(self):
        out=package(self.root,self.manifest(),self.now)
        self.assertEqual(out['initial_scope_count'],1);self.assertEqual(out['races'][0]['race_id'],RACE)
        self.assertFalse(out['races'][0]['finalized']);self.assertIsNone(out['races'][0]['prediction'])
        self.assertEqual(out['races'][0]['recommendation_state'],'PENDING')

    def test_fixed_initial_prediction_has_original_hash_cutoff_and_baseline(self):
        workflow.record_prediction(self.root,DATE,self.case.entry)
        before={str(p):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        out=package(self.root,self.manifest(),self.now);row=out['races'][0]
        self.assertEqual(row['prediction']['fixed_ref'],self.case.entry['operations']['prediction_ref'])
        self.assertTrue(row['prediction']['baseline_forecast_id']);self.assertTrue(row['prediction']['data_cutoff'])
        self.assertFalse(row['finalized']);self.assertFalse(out['external_ai_api_executed'])
        self.assertEqual(before,{str(p):p.read_bytes() for p in self.root.rglob('*') if p.is_file()})

    def test_review_package_uses_the_same_fixed_result_reconciliation(self):
        workflow.record_prediction(self.root,DATE,self.case.entry)
        entry=self.case.result_entry()
        workflow.review(self.root,DATE,entry)
        out=package(self.root,self.manifest(),self.now)
        result=out['races'][0]['result']
        self.assertEqual(result['text_reconciliation'],'MATCHED_FORWARD_FIXED')
        self.assertEqual(result['reconciliation_ref'],entry['result_reconciliation_ref'])
        self.assertFalse(result['diagnostic_formal_kpi_certified'])
        self.assertEqual(result['official_result']['race_id'],RACE)

    def test_initial_shadow_comparison_survives_final_not_applicable(self):
        gate=self.case.shadow_gate()
        self.case.entry['shadow_applicability']={'status':'APPLICABLE',
            'reason':'初回比較','item_ids':['TEST-SHADOW']}
        workflow.record_prediction(self.root,DATE,self.case.entry)
        self.case.select();self.case.final_without_shadow(gate)
        self.case.entry['shadow_applicability']={'status':'NOT_APPLICABLE',
            'reason':'最終条件では対象外','item_ids':[],
            'previous_item_dispositions':{
                'TEST-SHADOW':{'status':'NOT_APPLICABLE','reason':'対象条件なし'}}}
        workflow.record_prediction(self.root,DATE,self.case.entry)
        out=package(self.root,self.manifest(),self.now)
        race=out['races'][0]
        self.assertEqual(len(race['shadow_history']),2)
        self.assertEqual([h['phase'] for h in race['shadow_history']],['INITIAL','FINAL'])
        self.assertEqual(len(out['shadow_comparisons_by_fixed_phase']),1)
        self.assertEqual(out['shadow_comparisons_by_fixed_phase'][0]['phase'],'INITIAL')
        self.assertEqual(out['independent_kpis_by_day'][0]['independent_kpis']['shadow']['target_ids'],[])
        self.assertEqual(race['shadow_history_gaps'],[])

    def test_duplicate_day_and_mutation_rejected(self):
        manifest=self.manifest();manifest['day_refs']*=2
        with self.assertRaises(ValueError):package(self.root,manifest,self.now)
        manifest=self.manifest();manifest['day_refs'][0]['sha256']='0'*64
        with self.assertRaises(ValueError):package(self.root,manifest,self.now)

    def test_empty_package_is_not_measured_zero_or_ai_success(self):
        out=package(self.root,{'day_refs':[],'historical_purchase_refs':[]},self.now)
        self.assertIsNone(out['initial_scope_count']);self.assertFalse(out['formal_kpi_certified'])


if __name__=='__main__':unittest.main()
