"""30番：中心値/未算定/裁量レンジと既存比較入口の合成受入。"""
import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from probability_presentation import describe, describe_comparison, describe_production, main, validate
from cycle04_operations import validate_ticket_comparison
import test_cycle04_acceptance as fixtures


def item(method='UNCALIBRATED',value=.22,**extra):
    return {'type':'WIN','horses':[1],'probability_method':method,'probability':value,**extra}


class ProbabilityPresentationTests(unittest.TestCase):
    def test_center_and_all_basis_labels(self):
        for method,label in [('UNCALIBRATED','未校正'),('DISCRETIONARY','裁量評価'),('CALIBRATED','校正済みの区分')]:
            v=item(method,calibration_ref='calibration/test' if method=='CALIBRATED' else None)
            d=describe(v);self.assertEqual(d['中心値'],'22%');self.assertEqual(d['根拠区分'],label)
            self.assertFalse(d['校正証跡の認証'])

    def test_missing_and_zero_are_distinct(self):
        self.assertEqual(describe(item('MISSING',None))['中心値'],'未算定')
        self.assertEqual(describe(item(value=0))['中心値'],'0%')

    def test_missing_cannot_have_numeric_center_range_or_lower(self):
        for v in (item('MISSING',0),item('MISSING',None,probability_range=[0,0]),
                  item('MISSING',None,calibrated_lower_bound=0)):
            with self.assertRaises(ValueError):validate(v)

    def test_missing_method_is_not_inferred_from_number(self):
        for method in (None,'UNKNOWN','裁量'):
            with self.assertRaises(ValueError):validate(item(method))

    def test_finite_probability_and_boolean_rejection(self):
        for value in (None,True,False,-.01,1.01,float('nan'),float('inf'),'0.2'):
            with self.subTest(value=value),self.assertRaises(ValueError):validate(item(value=value))
        for value in (0,1):validate(item(value=value))

    def test_discretionary_range_is_not_statistical_lower_bound(self):
        v=item('DISCRETIONARY',probability_range=[.18,.27]);before=copy.deepcopy(v)
        d=describe(v);self.assertEqual(d['不確実性レンジ'],'18%〜27%')
        self.assertIn('統計下限ではない',d['レンジの扱い']);self.assertEqual(d['校正済み下限'],'未算定')
        self.assertEqual(v,before)

    def test_uncalibrated_range_is_not_statistical_lower_bound(self):
        d=describe(item(probability_range=[.18,.27]));self.assertIn('未校正',d['レンジの扱い'])
        self.assertEqual(d['校正済み下限'],'未算定')

    def test_uncalibrated_and_discretionary_lower_are_rejected(self):
        for method in ('UNCALIBRATED','DISCRETIONARY'):
            with self.assertRaises(ValueError):validate(item(method,calibrated_lower_bound=.18))

    def test_calibrated_requires_reference_and_separate_lower(self):
        with self.assertRaises(ValueError):validate(item('CALIBRATED'))
        d=describe(item('CALIBRATED',calibration_ref={'artifact_path':'test.json'},probability_range=[.18,.27]))
        self.assertEqual(d['校正済み下限'],'未算定');self.assertFalse(d['校正証跡の認証'])
        d=describe(item('CALIBRATED',calibration_ref='test',calibrated_lower_bound=.17))
        self.assertEqual(d['校正済み下限'],'17%')

    def test_invalid_calibrated_lower_is_rejected(self):
        for lower in (-.1,.23,True,float('nan'),float('inf')):
            with self.assertRaises(ValueError):validate(item('CALIBRATED',calibration_ref='test',calibrated_lower_bound=lower))

    def test_invalid_or_reversed_range_is_rejected(self):
        for bounds in ([.25,.2],[.23,.27],[.1,.2],[-.1,.3],[0,1.1],[True,.3],[float('nan'),.3],[.1],'.1,.3'):
            with self.assertRaises(ValueError):validate(item(probability_range=bounds))

    def test_cli_readonly_and_japanese_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'probability.json';p.write_text(json.dumps(item('MISSING',None)))
            before=p.read_bytes();out=io.StringIO()
            with redirect_stdout(out):self.assertEqual(main([str(p)]),0)
            self.assertIn('中心値：未算定',out.getvalue());self.assertEqual(p.read_bytes(),before)
            p.write_text(json.dumps(item('UNCALIBRATED',calibrated_lower_bound=.1)));out=io.StringIO()
            with redirect_stdout(out):self.assertEqual(main([str(p)]),1)
            self.assertIn('確認失敗',out.getvalue())

    def test_existing_comparison_entry_and_display_keep_input_unchanged(self):
        rows=fixtures.Cycle04Acceptance().comparison();rows[0].update(status='COMPARED',tickets=[item(value=0)])
        before=copy.deepcopy(rows);d=describe_comparison(rows,horses={1,2,3},frames={})
        self.assertEqual(d[0]['対象券'][0]['確率']['中心値'],'0%');self.assertEqual(rows,before)
        rows[0]['tickets'][0]['probability_range']=[.1,.2]
        with self.assertRaises(ValueError):validate_ticket_comparison(rows,horses={1,2,3},frames={})


    def test_production_centers_preserved_without_invented_calibration(self):
        p={'probabilities':[{'horse_no':1,'win_probability':0,'top2_probability':.2,'top3_probability':.3}]}
        before=copy.deepcopy(p);out=describe_production(p)
        self.assertEqual(out[0]['勝率中心'],'0%');self.assertEqual(out[0]['連対率中心'],'20%')
        self.assertIn('記録なし',out[0]['根拠区分']);self.assertEqual(p,before)
        p['probabilities'][0]['win_probability']=None
        with self.assertRaises(ValueError):describe_production(p)

    def test_production_display_cli_keeps_snapshot_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            from test_next_prediction_compliance import next_gate
            p=Path(folder)/'gate.json';p.write_text(json.dumps(next_gate()))
            before=p.read_bytes();out=io.StringIO()
            with redirect_stdout(out):self.assertEqual(main([str(p)]),0)
            self.assertIn('勝率中心',out.getvalue());self.assertEqual(p.read_bytes(),before)


if __name__=='__main__':unittest.main()
