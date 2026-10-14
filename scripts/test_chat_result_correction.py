import copy
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from chat_fact_capture import normalize
from chat_result_conversion import normalize_result
from chat_result_correction import correction, append_history
from cycle04_operations import fingerprint
from test_chat_result_conversion import fixture
import test_chat_fact_capture as facts


class Correction(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        old,a=fixture()
        req=copy.deepcopy(old['request']);cap=copy.deepcopy(old['captures'][0])
        cap['text']=cap['text'].replace('1着 1番','@').replace('4着 4番','1着 4番').replace('@','4着 1番')+'\n公式結果訂正'
        cap.update(read_started_at_jst=facts.DATE+'T10:08:00+09:00',read_finished_at_jst=facts.DATE+'T10:09:00+09:00')
        new=normalize(req,[cap],datetime.fromisoformat(facts.DATE+'T10:10:00+09:00'))
        newer=copy.deepcopy(a)
        for row in newer['rows']:
            if row['horse_no']==1:row['finish_position']=4
            if row['horse_no']==4:row['finish_position']=1
            line=('競走中止' if row['status']=='NON_FINISH' else '取消' if row['status']=='SCRATCHED' else str(row['finish_position'])+'着')+' '+str(row['horse_no'])+'番'
            start=cap['text'].index(line);row['quotation'].update(start=start,end=start+len(line),quote=line)
        def write(name,data):
            raw=json.dumps(data,ensure_ascii=False).encode();(self.root/name).write_bytes(raw)
            return {'artifact_path':name,'sha256':fingerprint(raw)}
        def refs(prefix,b,ann):
            conversion=normalize_result(b,ann)
            return {'capture':write(prefix+'capture.json',b),'conversion':write(prefix+'conversion.json',conversion),
                    'result':write(prefix+'result.json',conversion['result']),'prediction_gate':None,'prediction_original':None,'recommendation_gate':None}
        start=cap['text'].index('公式結果訂正')
        self.request={'correction_id':'synthetic-correction','old_refs':refs('old',old,a),'new_refs':refs('new',new,newer),
                      'old_review_ref':write('review.json',{'schema_version':'historical-review','analysis':'fixed'}),
                      'old_kpi_ref':write('kpi.json',{'schema_version':'historical-kpi','roi':None}),
                      'previous_correction_ref':None,'reason':'合成訂正の検査','owner':'50_review',
                      'correction_quotation':{'capture_id':'c1','start':start,'end':start+len('公式結果訂正'),'quote':'公式結果訂正'}}
        self.now=facts.DATE+'T11:00:00+09:00'

    def test_append_preserves_originals_and_requires_owner(self):
        before={p.name:p.read_bytes() for p in self.root.iterdir()}
        record=correction(self.root,self.request,self.now);ref=append_history(self.root,record)
        self.assertEqual(record['difference']['finish_groups']['old'],[[1,2],[3],[4]])
        self.assertEqual(record['difference']['finish_groups']['new'],[[2,4],[3],[1]])
        self.assertEqual(record['kpi_adoption'],'NOT_APPLIED')
        self.assertEqual(before,{p.name:p.read_bytes() for p in self.root.iterdir() if p.is_file()})
        with self.assertRaises(FileExistsError):append_history(self.root,record)
        self.assertTrue((self.root/ref['artifact_path']).exists())

    def test_absent_notice_mutated_history_and_wrong_prediction_rejected(self):
        for field in ('notice','review','prediction','prior'):
            req=copy.deepcopy(self.request)
            if field=='notice':req['correction_quotation']['quote']='訂正なし'
            if field=='review':req['old_review_ref']['sha256']='0'*64
            if field=='prediction':req['new_refs']['prediction_gate']={'artifact_path':'other','sha256':'0'*64}
            if field=='prior':req['previous_correction_ref']=req['old_kpi_ref']
            with self.assertRaises((ValueError,OSError,KeyError)):correction(self.root,req,self.now)

    def test_unaltered_or_reversed_result_not_a_correction(self):
        req=copy.deepcopy(self.request);req['new_refs']=req['old_refs']
        with self.assertRaises(ValueError):correction(self.root,req,self.now)
        req=copy.deepcopy(self.request);req['new_refs'],req['old_refs']=req['old_refs'],req['new_refs']
        with self.assertRaises(ValueError):correction(self.root,req,self.now)


if __name__=='__main__':unittest.main()
