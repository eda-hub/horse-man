import copy
import json
import tempfile
import unittest
from pathlib import Path
from chat_improvement_handoff import handoff, STATES
from cycle04_operations import fingerprint


class ImprovementHandoff(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        raw=json.dumps({'schema_version':'chat-review-package-v1','read_only':True,
                        'races':[{'race_id':'synthetic-race','input_gap_reason':'未取得'}]}).encode()
        (self.root/'review.json').write_bytes(raw)
        self.request={'review_package_ref':{'artifact_path':'review.json','sha256':fingerprint(raw)},
                      'calibration_input_ref':None,'candidates':[]}
        self.candidate={'candidate_id':'synthetic-candidate','title':'不足を次開催で確認','status':'DEFERRED','owner':'50_review',
                        'rationale':'実測不足','evidence':[{'source':'REVIEW_PACKAGE','pointer':'/races/0/input_gap_reason','claim':'入力不足'}],
                        'missing':['前向き実測'],'protected_good_parts':['固定予想の保存契約'],'next_test':'同条件の実依頼で不足を確認'}

    def test_nonobject_fixed_json_is_held_with_a_validation_reason(self):
        for value in ([],None,True):
            raw=json.dumps(value).encode();(self.root/'review.json').write_bytes(raw)
            req=copy.deepcopy(self.request);req['review_package_ref']['sha256']=fingerprint(raw)
            with self.assertRaisesRegex(ValueError,'fixed JSON object'):handoff(self.root,req)

    def test_all_dispositions_preserve_owner_evidence_next_test_without_writes(self):
        before=(self.root/'review.json').read_bytes()
        for state in STATES:
            c=copy.deepcopy(self.candidate);c['status']=state;self.request['candidates']=[c]
            out=handoff(self.root,self.request)
            self.assertEqual(out['candidates'][0]['resolved_evidence'][0]['value'],'未取得')
            self.assertFalse(out['candidates'][0]['automatic_adoption'])
            self.assertFalse(out['manual_updated']);self.assertFalse(out['database_updated'])
        self.assertEqual(before,(self.root/'review.json').read_bytes())
        self.assertEqual(len(list(self.root.iterdir())),1)

    def test_duplicate_missing_owner_bad_pointer_and_auto_apply_rejected(self):
        for field in ('duplicate','owner','pointer','direct','source'):
            req=copy.deepcopy(self.request);c=copy.deepcopy(self.candidate);req['candidates']=[c]
            if field=='duplicate':req['candidates']*=2
            if field=='owner':c['owner']=''
            if field=='pointer':c['evidence'][0]['pointer']='/races/1'
            if field=='direct':c['manual_patch']='auto'
            if field=='source':c['evidence'][0]['source']='CALIBRATION_INPUT'
            with self.assertRaises(ValueError):handoff(self.root,req)

    def test_owner_gaps_and_review_metrics_are_not_lost(self):
        document=json.loads((self.root/'review.json').read_text())
        document['cycle_completion']={'review_owner_gaps':[{'race_id':'synthetic-race',
            'missing_fields':['protected_good_parts']}]}
        document['independent_review_metrics']={'unmarked_by_fixed_phase':{'INITIAL':{
            'coverage':{'target_ids':['synthetic-race'],'eligible_count':0,'value':None}}}}
        raw=json.dumps(document,ensure_ascii=False).encode()
        (self.root/'review.json').write_bytes(raw)
        self.request['review_package_ref']['sha256']=fingerprint(raw)
        result=handoff(self.root,self.request)
        self.assertEqual(result['review_owner_gaps'][0]['race_id'],'synthetic-race')
        self.assertIsNone(result['independent_review_metrics']['unmarked_by_fixed_phase']['INITIAL']['coverage']['value'])
        self.assertFalse(result['manual_updated'])

    def test_substituted_package_and_unknown_disposition_rejected(self):
        req=copy.deepcopy(self.request);req['review_package_ref']['sha256']='0'*64
        with self.assertRaises(ValueError):handoff(self.root,req)
        req=copy.deepcopy(self.request);c=copy.deepcopy(self.candidate);c['status']='ADOPTED';req['candidates']=[c]
        with self.assertRaises(ValueError):handoff(self.root,req)


if __name__=='__main__':unittest.main()
