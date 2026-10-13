import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from class_transition import audit,describe,main
from check_prediction_compliance import ComplianceError

CUTOFF='2026-10-17T09:00:00+09:00'


def fact(value):
    return {'status':'ACQUIRED','value':value,'reason':'合成の事前確認','source_ref':'synthetic-source',
            'observed_at_jst':'2026-10-16T12:00:00+09:00','acquired_at_jst':'2026-10-16T13:00:00+09:00'}


def missing():return {'status':'MISSING','value':None,'reason':'取得できず不明'}


def fixture():
    return {'schema_version':'class-transition-assessment-v1','race_id':'synthetic-target','data_cutoff':CUTOFF,'horse_no':1,'horse_age':3,
            'target':{'age_condition':fact('MIXED'),'older_horses_present':fact(True),'class':fact('OP'),'carried_weight_kg':fact(55)},
            'prior_start_count':fact(1),'older_encounters':{**fact(0),'coverage':'ALL_PRIOR_STARTS'},
            'class_promotion':fact(True),'previous_class':fact('3WIN'),
            'recent_five_runs':fact([{'run_id':'prior-1','horse_age':3,'race_at_jst':'2026-09-20T15:00:00+09:00','source_ref':'synthetic-result',
                'age_condition':fact('AGE_RESTRICTED'),'older_horses_encountered':fact(False),'class':fact('3WIN'),
                'carried_weight_kg':fact(57),'opponent_level':fact('同世代の3勝水準')}]),'comparison_evidence':[]}


def evidence(kind='STRONG_SUBSTITUTE'):
    return {'evidence_id':'e1','kind':kind,'source_ref':'synthetic-comparison','claim':'今回条件との比較根拠',
            'limitations':'条件差と少数例の限界あり','evidence_at_jst':'2026-10-16T12:00:00+09:00',
            'observed_at_jst':'2026-10-16T13:00:00+09:00','acquired_at_jst':'2026-10-16T14:00:00+09:00',
            'target_class':'OP','comparison_dimensions':['CLASS','AGE_CONTEXT','WEIGHT'],'comparison_method':'時計/ラップ/負荷を対象条件と比較','run_id':'prior-1'}


def direct_fixture():
    p=fixture();p['older_encounters']['value']=1;p['class_promotion']['value']=False;p['previous_class']['value']='OP'
    r=p['recent_five_runs']['value'][0];r['class']['value']='OP';r['age_condition']['value']='MIXED';r['older_horses_encountered']['value']=True
    return p


class ClassTransitionTest(unittest.TestCase):
    def test_zero_positive_unknown_encounters_are_distinct(self):
        for value,state,first in [(0,'ZERO',True),(1,'POSITIVE',False),(None,'UNKNOWN',None)]:
            p=fixture();p['older_encounters']=missing() if value is None else {**fact(value),'coverage':'ALL_PRIOR_STARTS'}
            r=audit(p);self.assertEqual(r['older_encounter_state'],state);self.assertIs(r['first_older_encounter'],first)
            self.assertEqual(describe(r)['古馬既対戦数'],'不明' if value is None else value)

    def test_first_older_and_promotion_independent_four_combinations(self):
        for count in (0,1):
            for promoted in (False,True):
                p=fixture();p['older_encounters']['value']=count;p['class_promotion']['value']=promoted
                r=audit(p);self.assertEqual(r['first_older_encounter'],count==0);self.assertIs(r['class_promotion'],promoted)

    def test_mixed_entry_does_not_prove_older_opponents(self):
        p=fixture();p['target']['older_horses_present']=missing();r=audit(p)
        self.assertIsNone(r['first_older_encounter']);self.assertIn('対象古馬出走',r['missing_fields'])

    def test_restricted_or_no_older_target_is_not_first_encounter(self):
        for condition in ('AGE_RESTRICTED','MIXED'):
            p=fixture();p['target']['age_condition']['value']=condition;p['target']['older_horses_present']['value']=False
            self.assertIs(audit(p)['first_older_encounter'],False)

    def test_non_three_year_old_applicability_not_unknown(self):
        p=fixture();p['horse_age']=4;r=audit(p)
        self.assertIsNone(r['first_older_encounter']);self.assertEqual(describe(r)['3歳初古馬対戦'],'対象外')
        self.assertTrue(r['class_promotion']);self.assertFalse(r['blanket_age_penalty'])

    def test_lifetime_count_cannot_be_inferred_from_recent_five(self):
        p=fixture();p['older_encounters']['coverage']='RECENT_FIVE'
        with self.assertRaises(ComplianceError):audit(p)

    def test_partial_history_and_debut_coverage(self):
        p=fixture();p['prior_start_count']['value']=8
        with self.assertRaises(ComplianceError):audit(p)
        p=fixture();p['prior_start_count']['value']=0;p['recent_five_runs']['value']=[]
        self.assertEqual(audit(p)['recent_classes'],[])

    def test_recent_age_class_weight_and_opponent_are_separate(self):
        r=audit(fixture());self.assertEqual(r['recent_age_conditions'],['AGE_RESTRICTED'])
        self.assertEqual(r['recent_classes'],['3WIN']);self.assertEqual(r['recent_weights_kg'],[57]);self.assertEqual(r['target_weight_kg'],55)

    def test_recent_unknown_opponent_remains_missing(self):
        p=fixture();p['recent_five_runs']['value'][0]['opponent_level']=missing()
        r=audit(p);self.assertFalse(r['input_complete']);self.assertEqual(r['recent_opponent_levels'],[None])

    def test_future_fact_and_reverse_acquisition_rejected(self):
        for field,value in [('observed_at_jst','2026-10-18T10:00:00+09:00'),('acquired_at_jst','2026-10-15T10:00:00+09:00')]:
            p=fixture();p['target']['class'][field]=value
            with self.assertRaises(ComplianceError):audit(p)

    def test_opponent_later_success_cannot_backflow(self):
        p=fixture();p['recent_five_runs']['value'][0]['opponent_level']['observed_at_jst']='2026-11-01T12:00:00+09:00'
        with self.assertRaises(ComplianceError):audit(p)

    def test_future_run_duplicate_run_and_missing_runs_rejected(self):
        p=fixture();p['recent_five_runs']['value'][0]['race_at_jst']='2026-10-18T12:00:00+09:00'
        with self.assertRaises(ComplianceError):audit(p)
        p=fixture();p['recent_five_runs']['value']*=2
        with self.assertRaises(ComplianceError):audit(p)
        p=fixture();p['recent_five_runs']=missing();self.assertIn('近5走',audit(p)['missing_fields'])

    def test_lifetime_and_recent_encounter_contradiction(self):
        p=fixture();run=p['recent_five_runs']['value'][0];run['age_condition']['value']='MIXED';run['older_horses_encountered']['value']=True
        with self.assertRaises(ComplianceError):audit(p)
        p['older_encounters']['value']=1;self.assertIs(audit(p)['first_older_encounter'],False)

    def test_previous_class_and_promotion_contradictions(self):
        p=fixture();p['previous_class']['value']='OP'
        with self.assertRaises(ComplianceError):audit(p)
        p=fixture();p['previous_class']=missing()
        with self.assertRaises(ComplianceError):audit(p)

    def test_four_evidence_sufficiency_outputs(self):
        for kind,expected in [(None,'NOT_COMPARABLE'),('REFERENCE','REFERENCE'),('STRONG_SUBSTITUTE','STRONG_SUBSTITUTE'),('DIRECT','DIRECT')]:
            p=direct_fixture() if kind=='DIRECT' else fixture();p['comparison_evidence']=[] if kind is None else [evidence(kind)]
            self.assertEqual(audit(p)['comparison_sufficiency'],expected)

    def test_direct_requires_known_run_and_pre_cutoff_evidence(self):
        for mutation in ('run','future'):
            p=fixture();e=evidence('DIRECT');p['comparison_evidence']=[e]
            if mutation=='run':e['run_id']='unknown'
            else:e['evidence_at_jst']='2026-10-18T12:00:00+09:00'
            with self.assertRaises(ComplianceError):audit(p)

    def test_weight_context_class_and_method_shortages_are_reference(self):
        for gap in ('weight','age','class','method','dimensions'):
            p=fixture();e=evidence();p['comparison_evidence']=[e]
            if gap=='weight':p['target']['carried_weight_kg']=missing()
            elif gap=='age':p['target']['age_condition']=missing()
            elif gap=='class':e['target_class']='G1'
            elif gap=='method':e.pop('comparison_method')
            else:e['comparison_dimensions']=['CLASS']
            self.assertEqual(audit(p)['comparison_sufficiency'],'REFERENCE')

    def test_direct_priority_and_duplicate_evidence_rejection(self):
        p=direct_fixture();e=evidence('DIRECT');e['evidence_id']='e2';p['comparison_evidence']=[evidence(),e]
        self.assertEqual(audit(p)['comparison_sufficiency'],'DIRECT')
        p['comparison_evidence'].append(e)
        with self.assertRaises(ComplianceError):audit(p)

    def test_invalid_count_weight_and_unknown_not_zero(self):
        for value in (True,-1,1.5):
            p=fixture();p['older_encounters']['value']=value
            with self.assertRaises(ComplianceError):audit(p)
        for value in (0,True,float('nan')):
            p=fixture();p['target']['carried_weight_kg']['value']=value
            with self.assertRaises(ComplianceError):audit(p)
        p=fixture();p['class_promotion']=missing();self.assertIsNone(audit(p)['class_promotion'])

    def test_read_only_no_blanket_penalty_or_promotion(self):
        p=fixture();p['comparison_evidence']=[evidence()];before=copy.deepcopy(p);r=audit(p)
        self.assertEqual(p,before);self.assertFalse(r['production_changed']);self.assertFalse(r['blanket_age_penalty'])
        self.assertFalse(r['evidence_authentication']);self.assertEqual(r['performance_promotion'],'NOT_APPROVED')

    def test_lower_class_or_no_older_run_not_direct_by_label_alone(self):
        p=fixture();p['comparison_evidence']=[evidence('DIRECT')]
        self.assertEqual(audit(p)['comparison_sufficiency'],'REFERENCE')
        p=direct_fixture();p['recent_five_runs']['value'][0]['older_horses_encountered']['value']=False;p['comparison_evidence']=[evidence('DIRECT')]
        self.assertEqual(audit(p)['comparison_sufficiency'],'REFERENCE')

    def test_sourced_higher_class_direct_comparison_and_same_contradiction(self):
        p=direct_fixture();p['class_promotion']['value']=False;p['previous_class']['value']='G3';p['recent_five_runs']['value'][0]['class']['value']='G3'
        e=evidence('DIRECT');e['class_relation']=fact('HIGHER');p['comparison_evidence']=[e]
        self.assertEqual(audit(p)['comparison_sufficiency'],'DIRECT')
        e['class_relation']['value']='SAME'
        with self.assertRaises(ComplianceError):audit(p)

    def test_declared_lower_class_is_reference_and_equal_class_conflict_rejected(self):
        p=direct_fixture();p['previous_class']['value']='3WIN';p['recent_five_runs']['value'][0]['class']['value']='3WIN'
        e=evidence('DIRECT');e['class_relation']=fact('LOWER');p['comparison_evidence']=[e]
        self.assertEqual(audit(p)['comparison_sufficiency'],'REFERENCE')
        p['previous_class']['value']='OP';p['recent_five_runs']['value'][0]['class']['value']='OP'
        with self.assertRaises(ComplianceError):audit(p)

    def test_cli_missing_display_and_no_file_write(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'input.json';p=fixture();p['older_encounters']=missing();path.write_text(json.dumps(p))
            before=path.read_bytes();out=io.StringIO()
            with redirect_stdout(out):self.assertEqual(main([str(path)]),0)
            self.assertIn('不明',out.getvalue());self.assertEqual(path.read_bytes(),before)


if __name__=='__main__':unittest.main()
