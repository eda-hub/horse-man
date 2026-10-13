import unittest
import copy
import math
from two_axis_candidates import compare


class TwoAxisComparison(unittest.TestCase):
    def production(self):
        return {'ranking':[5,2,6,4,1,3,7], 'probabilities':[
            {'horse_no':h,'top3_probability':p} for h,p in [(5,.70),(2,.71),(6,.7),(4,.30),(1,.29),(3,.15),(7,.15)]]}

    def test_three_qualified_axes_use_fixed_rank_and_expand_each_unique_permutation(self):
        result=compare(self.production())
        self.assertEqual(result['axes'],[5,2])
        self.assertEqual(result['trio_points'],4)
        self.assertEqual(result['trifecta_points'],12)
        self.assertEqual(len({tuple(t['horses']) for t in result['trifecta_tickets']}),12)
        self.assertEqual(result['joint_probability_status'],'NOT_CALCULATED')
        self.assertEqual(result['performance_promotion'],'NOT_APPROVED')

    def test_one_qualified_horse_does_not_trigger_comparison(self):
        p=self.production()
        for row in p['probabilities']:
            if row['horse_no'] in (2,6):row['top3_probability']=.69
        self.assertEqual(compare(p)['status'],'NOT_APPLICABLE')

    def test_axis_threshold_before_equal_after(self):
        for rate,expected in [(math.nextafter(.70,0),'NOT_APPLICABLE'),(.70,'SHADOW_CANDIDATE'),(math.nextafter(.70,1),'SHADOW_CANDIDATE')]:
            p={'ranking':[1,2,3],'probabilities':[{'horse_no':h,'top3_probability':r} for h,r in [(1,.8),(2,rate),(3,.2)]]}
            self.assertEqual(compare(p)['status'],expected)

    def test_opponent_threshold_before_equal_after(self):
        for rate,count in [(math.nextafter(.30,0),0),(.30,6),(math.nextafter(.30,1),6)]:
            p={'ranking':[1,2,3],'probabilities':[{'horse_no':h,'top3_probability':r} for h,r in [(1,.8),(2,.7),(3,rate)]]}
            self.assertEqual(compare(p)['trifecta_points'],count)

    def test_missing_rate_row_and_null_are_information_shortage(self):
        for mutation in ('rows','row','null'):
            p=self.production()
            if mutation=='rows':p.pop('probabilities')
            elif mutation=='row':p['probabilities'].pop()
            else:p['probabilities'][0]['top3_probability']=None
            r=compare(p);self.assertEqual(r['status'],'MISSING');self.assertTrue(r['reason']);self.assertIsNone(r['joint_probability'])

    def test_invalid_probabilities_do_not_generate_candidates(self):
        for value in (True,-.1,1.1,float('nan'),float('inf'),'0.7'):
            p=self.production();p['probabilities'][0]['top3_probability']=value
            self.assertEqual(compare(p)['status'],'MISSING')

    def test_duplicate_or_unknown_rate_rows_are_missing(self):
        for horse in (5,99):
            p=self.production();p['probabilities'].append({'horse_no':horse,'top3_probability':.7})
            self.assertEqual(compare(p)['status'],'MISSING')

    def test_invalid_ranking_and_cancelled_identifiers(self):
        p=self.production()
        for ranking in (None,[],[5,5],[True,2]):
            bad=copy.deepcopy(p);bad['ranking']=ranking;self.assertEqual(compare(bad)['status'],'MISSING')
        for cancelled in ([99],[5,5],[True],None):self.assertEqual(compare(p,cancelled_horses=cancelled)['status'],'MISSING')

    def test_cancelled_axis_is_replaced_using_fixed_rank(self):
        p=self.production();before=copy.deepcopy(p);r=compare(p,cancelled_horses=[5])
        self.assertEqual(r['axes'],[2,6]);self.assertEqual(p,before)
        self.assertTrue(all(5 not in t['horses'] for t in r['trio_tickets']+r['trifecta_tickets']))
        self.assertEqual(r['trio_points'],4)

    def test_cancelled_opponent_removed_and_ranked_replacement_used(self):
        r=compare(self.production(),cancelled_horses=[4])
        self.assertEqual(r['trifecta_points'],6);self.assertEqual(r['trio_points'],4)
        self.assertTrue(any(7 in t['horses'] for t in r['trio_tickets']))

    def test_cancellation_leaves_only_one_axis(self):
        self.assertEqual(compare(self.production(),cancelled_horses=[5,2])['status'],'NOT_APPLICABLE')

    def test_cancelled_rate_can_be_missing_without_hiding_active_missing(self):
        p=self.production();p['probabilities'][0]['top3_probability']=None
        self.assertEqual(compare(p,cancelled_horses=[5])['status'],'SHADOW_CANDIDATE')
        p['probabilities'][1]['top3_probability']=None
        self.assertEqual(compare(p,cancelled_horses=[5])['status'],'MISSING')

    def test_points_are_unique_candidates_not_adopted_or_joint_probability(self):
        p=self.production();before=copy.deepcopy(p);r=compare(p)
        self.assertEqual(len({tuple(t['horses']) for t in r['trio_tickets']}),r['trio_points'])
        self.assertEqual(len({tuple(t['horses']) for t in r['trifecta_tickets']}),r['trifecta_points'])
        self.assertEqual(r['trifecta_points'],6*2);self.assertEqual(r['trio_points'],4)
        self.assertIsNone(r['selected_points']);self.assertIsNone(r['joint_probability'])
        self.assertEqual(r['standard_adoption'],'NOT_APPROVED');self.assertEqual(r['performance_promotion'],'NOT_APPROVED');self.assertEqual(p,before)
