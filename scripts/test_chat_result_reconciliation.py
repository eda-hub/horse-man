import copy
import json
import tempfile
import unittest
from pathlib import Path
from chat_result_conversion import normalize_result
from chat_result_reconciliation import reconcile, fixed_json, audit_saved
from cycle04_operations import fingerprint
from test_chat_result_conversion import fixture
import test_chat_fact_capture as facts


class Reconciliation(unittest.TestCase):
    def parts(self):
        b,a=fixture();c=normalize_result(b,a)
        return b,c,copy.deepcopy(c['result'])

    def test_all_horses_without_prediction_or_recommendation_are_retained(self):
        b,c,r=self.parts();out=reconcile(b,c,r,as_of=facts.DATE+'T11:00:00+09:00')
        self.assertTrue(out['text_values_matched'])
        self.assertEqual(out['prediction_state'],'UNFINALIZED_OR_ABSENT')
        self.assertEqual(out['recommendation_result']['status'],'NOT_APPLICABLE')
        self.assertFalse(out['formal_kpi_certified'])

    def test_tie_ticket_hits_without_payout_and_scratched_invalid(self):
        b,c,r=self.parts()
        rec={'status':'RECOMMENDED','race_id':r['race_id'],'race_date_jst':r['race_date_jst'],
             'scheduled_post_time_jst':b['request']['scheduled_post_time_jst'],
             'tickets':[{'type':'WIN','horses':[2]},{'type':'PLACE','horses':[6]}]}
        out=reconcile(b,c,r,recommendation=rec,as_of=facts.DATE+'T11:00:00+09:00')
        self.assertEqual([t['result'] for t in out['recommendation_result']['tickets']],['HIT','INVALID'])

    def test_source_or_result_mutation_future_and_other_race_rejected(self):
        for change in ('result','conversion','source','future','race'):
            b,c,r=self.parts();gate=None;now=facts.DATE+'T11:00:00+09:00'
            if change=='result':r['finish_groups']=[[1],[2],[3],[4]]
            if change=='conversion':c['annotation']['rows'][0]['horse_no']=99
            if change=='source':b['captures'][0]['text']+='改変'
            if change=='future':now=facts.DATE+'T10:00:00+09:00'
            if change=='race':gate={'race_id':'wrong'}
            with self.assertRaises(ValueError):reconcile(b,c,r,gate=gate,as_of=now)

    def test_saved_hash_is_independent_and_audit_is_read_only(self):
        b,c,r=self.parts()
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);refs={}
            for key,data in [('capture',b),('conversion',c),('result',r)]:
                raw=json.dumps(data,ensure_ascii=False).encode();(root/(key+'.json')).write_bytes(raw)
                refs[key]={'artifact_path':key+'.json','sha256':fingerprint(raw)}
            refs.update(prediction_gate=None,prediction_original=None,recommendation_gate=None)
            before={p.name:p.read_bytes() for p in root.iterdir()}
            audit_saved(root,refs,facts.DATE+'T11:00:00+09:00')
            self.assertEqual(before,{p.name:p.read_bytes() for p in root.iterdir()})
            (root/'result.json').write_text('{}')
            with self.assertRaises(ValueError):fixed_json(root,refs['result'])


if __name__=='__main__':unittest.main()
