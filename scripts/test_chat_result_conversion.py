import copy
import unittest
from datetime import datetime

import test_chat_fact_capture as facts
from chat_fact_capture import normalize
from chat_result_conversion import normalize_result, quoted_row
from pathlib import Path
import re


def fixture(mode='SYNTHETIC', domain='https://app.jra.jp/test'):
    req=facts.request()
    req.update(purpose='RESULT',data_cutoff=facts.DATE+'T10:30:00+09:00',horse_numbers=[1,2,3,4,5,6])
    lines=['確定結果','発売開始時 6頭','1着 1番','1着 2番','3着 3番','4着 4番',
           '競走中止 5番','取消 6番']
    c=facts.capture()
    c.update(text='\n'.join(lines),mode=mode,source_url=domain,
             retrieval_kind='SYNTHETIC_PAGE_TEXT' if mode=='SYNTHETIC' else 'PAGE_TEXT',
             source_updated_at_jst=None,read_started_at_jst=facts.DATE+'T10:05:00+09:00',
             read_finished_at_jst=facts.DATE+'T10:06:00+09:00')
    b=normalize(req,[c],datetime.fromisoformat(facts.DATE+'T10:07:00+09:00'))
    def ref(line):
        start=c['text'].index(line)
        return {'capture_id':'c1','start':start,'end':start+len(line),'quote':line}
    statuses=['FINISHED']*4+['NON_FINISH','SCRATCHED']
    rows=[{'horse_no':h,'status':statuses[h-1],'finish_position':p,'quotation':ref(line)}
          for h,p,line in zip([1,2,3,4,5,6],[1,1,3,4,None,None],lines[2:])]
    return b,{'rows':rows,'confirmation':ref(lines[0]),
              'place_basis':{'kind':'OFFICIAL_SALES_START_COUNT','value':6,'quotation':ref(lines[1])}}


class ResultConversion(unittest.TestCase):
    def test_saved_official_pipe_rows_ignore_frame_and_equipment_icons(self):
        path = Path(__file__).resolve().parent.parent / 'data/pedigree/reconciliations/2026-10-12-delta/results/kyoto-01/official-extract.txt'
        text = path.read_text(encoding='utf-8')
        rows = [quoted_row(line) for line in text.splitlines()
                if re.match(r'L\d+: \d+\s+\|', line)]
        self.assertEqual(len(rows), 15)
        self.assertEqual(rows[0], (14, 'FINISHED', 1))
        self.assertEqual(rows[3], (12, 'FINISHED', 4))
        self.assertEqual({r[0] for r in rows}, set(range(1,16)))

    def test_full_field_tie_scratch_nonfinish_and_unknown_publication_time(self):
        b,a=fixture();r=normalize_result(b,a)
        self.assertEqual(r['result']['finish_groups'],[[1,2],[3],[4]])
        self.assertEqual(r['result']['place_places'],2)
        self.assertTrue(r['publication_time_unknown']);self.assertEqual(r['mode'],'SYNTHETIC')
        self.assertFalse(r['formal_kpi_certified'])
        self.assertFalse(b['captures'][0]['usable_as_observed_fact'])

    def test_partial_duplicate_unconfirmed_and_icon_name_fields_rejected(self):
        for mutate in [lambda a:a['rows'].pop(),lambda a:a['rows'][1].update(horse_no=1),
                       lambda a:a['rows'][0].update(status='PENDING'),
                       lambda a:a['rows'][0].update(horse_name='ブリンカー サンプル')]:
            b,a=fixture();mutate(a)
            with self.assertRaises(ValueError):normalize_result(b,a)

    def test_place_basis_cannot_use_cancelled_current_field_or_missing_confirmation(self):
        b,a=fixture();a['place_basis']['kind']='CURRENT_STARTER_COUNT'
        with self.assertRaises(ValueError):normalize_result(b,a)
        b,a=fixture();a['place_basis']['value']=8
        with self.assertRaises(ValueError):normalize_result(b,a)
        b,a=fixture();a['confirmation']=a['rows'][0]['quotation']
        with self.assertRaises(ValueError):normalize_result(b,a)

    def test_result_before_start_wrong_quote_or_inconsistent_tie_rejected(self):
        b,a=fixture();a['rows'][0]['quotation']['quote']='changed'
        with self.assertRaises(ValueError):normalize_result(b,a)
        b,a=fixture();a['rows'][2]['finish_position']=2
        with self.assertRaises(ValueError):normalize_result(b,a)


if __name__=='__main__':unittest.main()
