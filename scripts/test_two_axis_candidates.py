import unittest
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
