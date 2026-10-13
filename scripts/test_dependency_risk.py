"""31番の構成依存と任意資金・共同結果モデルの合成検査。"""
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path
from contextlib import redirect_stdout

from dependency_risk import audit, describe, main
from recommendation import display


def ticket(kind='WIDE',horses=None,scenario='s1'):
    return {'type':kind,'horses':horses or [1,2],'scenario_id':scenario}


def allocations(items,amounts):
    return [dict(t,amount_yen=a) for t,a in zip(items,amounts)]


def model(method='UNCALIBRATED'):
    return {'coverage':'EXHAUSTIVE_DISJOINT','source_ref':'synthetic-model-not-live',
            'probability_method':method,'place_places':2,
            'outcomes':[{'finish_order':[1,2,3],'probability':.7},{'finish_order':[3,2,1],'probability':.3}]}


class DependencyRiskTests(unittest.TestCase):
    def test_candidate_and_selected_count_horse_and_anchor(self):
        proposed=[ticket(),ticket(horses=[1,3]),ticket('WIN',[1])];chosen=proposed[:2]
        before=copy.deepcopy(proposed);r=audit(proposed,chosen,1)
        self.assertEqual(r['candidate']['unique_ticket_count'],3);self.assertEqual(r['selected']['unique_ticket_count'],2)
        self.assertEqual(r['selected']['horse_ticket_counts'],{1:2,2:1,3:1})
        self.assertEqual(r['selected']['anchor_ticket_ratio'],1);self.assertEqual(proposed,before)
        self.assertIsNone(r['finance']['total_allocation_yen'])

    def test_unknown_candidates_anchor_and_empty_are_not_zero_probability(self):
        r=audit(None,[],None);self.assertIsNone(r['candidate']);self.assertIsNone(r['selected']['anchor_ticket_ratio'])
        self.assertEqual(describe(r)['候補点数'],'未記録');self.assertEqual(describe(r)['全損率'],'未算定')

    def test_partial_and_no_anchor_dependency(self):
        self.assertEqual(audit(None,[ticket(),ticket('WIN',[3])],1)['selected']['anchor_ticket_ratio'],.5)
        self.assertEqual(audit(None,[ticket('WIN',[3])],1)['selected']['anchor_ticket_ratio'],0)

    def test_scenario_overlap_is_separate_from_horse_counts(self):
        r=audit(None,[ticket(),ticket('WIN',[1]),ticket('PLACE',[3],'s2')],1)
        self.assertEqual(r['selected']['scenario_ticket_counts'],{'s1':2,'s2':1})
        self.assertEqual(r['selected']['unique_ticket_count'],3)

    def test_reversed_unordered_and_cross_scenario_duplicates_rejected(self):
        for duplicate in (ticket(horses=[2,1]),ticket(scenario='s2')):
            with self.assertRaises(ValueError):audit(None,[ticket(),duplicate],1)
            with self.assertRaises(ValueError):audit([ticket(),duplicate],[ticket()],1)

    def test_ordered_tickets_remain_separate(self):
        r=audit(None,[ticket('EXACTA',[1,2]),ticket('EXACTA',[2,1])],1)
        self.assertEqual(r['selected']['unique_ticket_count'],2)

    def test_selected_subset_and_scenario_consistency(self):
        with self.assertRaises(ValueError):audit([ticket()],[ticket('WIN',[1])],1)
        with self.assertRaises(ValueError):audit([ticket()],[ticket(scenario='s2')],1)

    def test_cancelled_or_unknown_horse_and_missing_scenario_rejected(self):
        with self.assertRaises(ValueError):audit(None,[ticket()],1,field_horses=[1,3])
        t=ticket();del t['scenario_id']
        with self.assertRaises(ValueError):audit(None,[t],1)

    def test_hypothetical_money_concentration_and_no_full_loss_guess(self):
        items=[ticket(),ticket('WIN',[1]),ticket('PLACE',[3])]
        r=audit(None,items,1,allocations=allocations(items,[100,200,50]))
        f=r['finance'];self.assertEqual(f['total_allocation_yen'],350);self.assertEqual(f['max_single_ticket_yen'],200)
        self.assertEqual(f['horse_dependent_allocation_yen'],{1:300,2:100,3:50})
        self.assertIsNone(f['full_loss_probability'])

    def test_missing_duplicate_negative_noninteger_allocation_rejected(self):
        items=[ticket()];a=allocations(items,[100])
        for bad in ([],a+a,allocations(items,[-1]),allocations(items,[True]),allocations(items,[1.5])):
            with self.assertRaises(ValueError):audit(None,items,1,allocations=bad)

    def test_zero_exposure_has_no_full_loss_rate(self):
        items=[ticket()];r=audit(None,items,1,allocations=allocations(items,[0]))
        self.assertIsNone(r['finance']['full_loss_probability'])

    def test_explicit_joint_model_calculates_full_loss_without_marginal_product(self):
        items=[ticket('WIN',[1]),ticket('EXACTA',[1,2])]
        r=audit(None,items,1,field_horses=[1,2,3],allocations=allocations(items,[100,100]),joint_model=model())
        self.assertAlmostEqual(r['finance']['full_loss_probability'],.3)
        self.assertFalse(r['finance']['calibration_authenticated']);self.assertFalse(r['performance_promoted'])

    def test_winning_zero_amount_ticket_does_not_hide_full_loss(self):
        items=[ticket('WIN',[1]),ticket('WIN',[3])]
        r=audit(None,items,1,field_horses=[1,2,3],allocations=allocations(items,[0,100]),joint_model=model())
        self.assertAlmostEqual(r['finance']['full_loss_probability'],.7)

    def test_unfunded_model_unknown_field_and_nonexhaustive_rejected(self):
        items=[ticket('WIN',[1])]
        with self.assertRaises(ValueError):audit(None,items,1,joint_model=model())
        with self.assertRaises(ValueError):audit(None,items,1,allocations=allocations(items,[100]),joint_model=model())
        m=model();m['coverage']='PARTIAL'
        with self.assertRaises(ValueError):audit(None,items,1,field_horses=[1,2,3],allocations=allocations(items,[100]),joint_model=m)

    def test_joint_sum_duplicate_order_missing_probability_and_future_calibration_claim_rejected(self):
        items=[ticket('WIN',[1])]
        changes=[lambda m:m['outcomes'][0].update(probability=.9),
                 lambda m:m['outcomes'][1].update(finish_order=[1,2,3]),
                 lambda m:m['outcomes'][0].update(probability=None),
                 lambda m:m.update(probability_method='CALIBRATED'),
                 lambda m:m['outcomes'][1].update(finish_order=[3,2,4])]
        for change in changes:
            m=model();change(m)
            with self.assertRaises(ValueError):audit(None,items,1,field_horses=[1,2,3],allocations=allocations(items,[100]),joint_model=m)

    def test_frames_are_not_allocated_to_each_horse(self):
        items=[{'type':'BRACKET_QUINELLA','frames':[1,1],'scenario_id':'s1'}]
        a=[dict(items[0],amount_yen=100)]
        r=audit(None,items,1,field_horses=[1,2,3],frames={1:1,2:1,3:2},allocations=a,joint_model=model())
        self.assertEqual(r['finance']['frame_dependent_allocation_yen'],{1:100})
        self.assertEqual(r['finance']['horse_dependent_allocation_yen'],{})
        self.assertEqual(describe(r)['枠別仮想依存額'],{1:100})
        self.assertAlmostEqual(r['finance']['full_loss_probability'],.3)

    def test_display_is_readonly_and_requires_no_money(self):
        from test_recommendation import RecommendationTest
        f=RecommendationTest();f.addCleanup=self.addCleanup;root,_,pred=f.root();r=f.rec(root,pred)
        before=copy.deepcopy(r);text=display(r)
        self.assertIn('馬別依存点数',text);self.assertIn('候補全点数: 未記録',text);self.assertEqual(r,before)

    def test_cli_success_and_failure_preserve_input(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'risk.json';p.write_text(json.dumps({'selected':[ticket()],'anchor':1}))
            before=p.read_bytes();out=io.StringIO()
            with redirect_stdout(out):self.assertEqual(main([str(p)]),0)
            self.assertIn('全損率',out.getvalue());self.assertEqual(p.read_bytes(),before)
            p.write_text('{}')
            with redirect_stdout(out):self.assertEqual(main([str(p)]),1)

    def test_all_ticket_hits_follow_joint_finish_order(self):
        from dependency_risk import hit
        cases=[('WIN',(1,),True),('WIN',(2,),False),('PLACE',(2,),True),('PLACE',(3,),False),
               ('QUINELLA',(1,2),True),('WIDE',(1,3),True),('EXACTA',(1,2),True),('EXACTA',(2,1),False),
               ('TRIO',(1,2,3),True),('TRIFECTA',(1,2,3),True),('TRIFECTA',(3,2,1),False),
               ('BRACKET_QUINELLA',(1,1),True)]
        for kind,values,expected in cases:
            self.assertEqual(hit((kind,values),[1,2,3],{1:1,2:1,3:2},2),expected)

    def test_malformed_tickets_are_rejected_without_guess(self):
        for items in ([None],[{'type':'WIN','horses':None}], [ticket('WIN',[True])]):
            with self.assertRaises(ValueError):audit(None,items,1)


if __name__=='__main__':unittest.main()
