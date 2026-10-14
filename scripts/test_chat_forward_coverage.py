import copy
import json
import unittest
from pathlib import Path
from chat_forward_coverage import coverage, applicability
from class_transition import audit
from check_prediction_compliance import validate_gate
from cycle04_operations import fingerprint
import cycle04_workflow as workflow
import test_cycle04_workflow as operations
import test_class_transition as assessment
from test_recommendation import DATE, RACE


class ForwardCoverage(unittest.TestCase):
    def setUp(self):
        self.case=operations.OperationalWorkflow();self.case.setUp();self.addCleanup(self.case.doCleanups)
        self.root=self.case.root;self.case.register()
        workflow.record_prediction(self.root,DATE,self.case.entry)
        self.path='docs/validation/records/cycle_04/'+DATE+'.json'
        self.plan=json.loads((Path(__file__).resolve().parents[1]/'docs/validation/class-transition/forward-plan.json').read_text())
        self.manifest={'plan':self.plan,'days':[{'artifact_path':self.path,'sha256':fingerprint((self.root/self.path).read_bytes())}],
                       'assessments':[],'items':[]}
        self.now=DATE+'T12:00:00+09:00'

    def add_assessment(self):
        gate=validate_gate(self.root,self.root/self.case.entry['prediction_gate_path'])
        rows=[]
        for horse in gate['production']['ranking']:
            a=assessment.fixture();a.update(race_id=RACE,data_cutoff=gate['data_cutoff'],horse_no=horse)
            rows.append(a)
        data={'schema_version':'chat-forward-assessments-v1','mode':'FORWARD','race_id':RACE,
              'data_cutoff':gate['data_cutoff'],'assessments':rows}
        ref=self.case.fixture.artifact('coverage-assessments','coverage/assessments.json',data,at='09:40')
        self.manifest['assessments']=[{'race_id':RACE,'assessment_ref':ref}]

    def test_missing_assessment_is_unknown_not_nonapplicable_and_no_writes(self):
        before={str(p):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        out=coverage(self.root,self.manifest,self.now)
        self.assertEqual(out['unknown_ids'],[RACE]);self.assertEqual(out['not_applicable_ids'],[])
        self.assertFalse(out['sample_coverage_verified']);self.assertFalse(out['trial_complete'])
        self.assertEqual(before,{str(p):p.read_bytes() for p in self.root.rglob('*') if p.is_file()})

    def test_complete_applicable_assessments_keep_missing_pair(self):
        self.add_assessment();out=coverage(self.root,self.manifest,self.now)
        self.assertEqual(out['applicable_ids'],[RACE]);self.assertEqual(out['missing_ids'],[RACE])
        self.assertFalse(out['sample_coverage_verified'])

    def test_duplicate_unknown_or_late_assessment_rejected(self):
        self.add_assessment();self.manifest['assessments']*=2
        with self.assertRaises(ValueError):coverage(self.root,self.manifest,self.now)
        self.manifest['assessments']=self.manifest['assessments'][:1]
        self.manifest['assessments'][0]['race_id']='unknown'
        with self.assertRaises(ValueError):coverage(self.root,self.manifest,self.now)

    def test_submitted_comparison_binds_initial_phase_after_final(self):
        case=operations.OperationalWorkflow();case.setUp();self.addCleanup(case.doCleanups)
        case.register();initial=case.shadow_gate()
        gate_path=case.entry['prediction_gate_path']
        case.entry['shadow_applicability']={'status':'APPLICABLE',
                                            'reason':'初回の比較を固定','item_ids':['TEST-SHADOW']}
        workflow.record_prediction(case.root,DATE,case.entry)
        case.select();case.final_without_shadow(initial)
        case.entry['shadow_applicability']={'status':'NOT_APPLICABLE',
            'reason':'最終時点では条件非該当','item_ids':[],
            'previous_item_dispositions':{
                'TEST-SHADOW':{'status':'NOT_APPLICABLE','reason':'最終条件非該当'}}}
        workflow.record_prediction(case.root,DATE,case.entry)
        self.case=case;self.root=case.root
        self.path='docs/validation/records/cycle_04/'+DATE+'.json'
        self.manifest={'plan':self.plan,'days':[{
             'artifact_path':self.path,'sha256':fingerprint((self.root/self.path).read_bytes())}],
             'assessments':[],'items':[]}
        self.add_assessment()
        result_path='result.json'
        (self.root/result_path).write_text(json.dumps({
            'race_id':RACE,'race_date_jst':DATE,'status':'OFFICIAL',
            'source_url':'https://www.jra.go.jp/test/result',
            'retrieved_at_jst':DATE+'T11:00:00+09:00',
            'finish_groups':[[5],[2],[6],[4],[1],[3]],'place_places':3}))
        self.manifest['items']=[{
            'gate_path':gate_path,
            'gate_ref':{'artifact_path':gate_path,
                        'sha256':fingerprint((self.root/gate_path).read_bytes())},
            'shadow_item_id':'TEST-SHADOW',
            'result_path':result_path,
            'result_ref':{'artifact_path':result_path,
                          'sha256':fingerprint((self.root/result_path).read_bytes())}}]
        report=coverage(self.root,self.manifest,self.now)
        self.assertEqual(report['submitted_pair_bindings'][RACE]['phase'],'INITIAL')
        self.assertEqual(report['submitted_pair_bindings'][RACE]['shadow_item_id'],'TEST-SHADOW')
        self.assertFalse(report['sample_coverage_verified'])

    def test_empty_scope_is_waiting_not_a_measured_zero(self):
        m={'plan':self.plan,'days':[],'assessments':[],'items':[]}
        out=coverage(self.root,m,self.now)
        self.assertIsNone(out['eligible_pair_count']);self.assertFalse(out['sample_coverage_verified'])
        self.assertFalse(out['all_planned_days_present'])

    def test_unknown_cannot_be_silently_classified_as_nonapplicable(self):
        report=audit(assessment.direct_fixture())
        self.assertEqual(applicability(report),'NOT_APPLICABLE')
        report['input_complete']=False;report['class_promotion']=None
        self.assertEqual(applicability(report),'UNKNOWN')
        report['class_promotion']=True
        self.assertEqual(applicability(report),'APPLICABLE')


if __name__=='__main__':unittest.main()
