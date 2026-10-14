"""チャット取得の合成回帰。実価格・実開催・性能の成功証跡ではない。"""
import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime
from pathlib import Path

import chat_market_acquisition as chat
import market_acquisition as acquisition
from market_sidecar import describe, main as describe_main
import test_market_sidecar as fixtures
import cycle04_workflow as workflow
from test_recommendation import DATE, RACE, POST


def request(kind='WIN', numbers=None, mode='SYNTHETIC', date=DATE):
    numbers = numbers or ([1] if kind in {'WIN','PLACE'} else [1,2,3] if kind in {'TRIO','TRIFECTA'} else [1,2])
    return {'schema_version':'chat-market-request-v1','mode':mode,
            'race_date_jst':date,'race_id':date.replace('-','')+'-TOK-01',
            'scheduled_post_time_jst':date+POST[10:],
            'deadline_at_jst':date+'T10:00:00+09:00','data_cutoff':date+'T10:01:00+09:00',
            'ticket':{'type':kind,'frames' if kind=='BRACKET_QUINELLA' else 'horses':numbers},
            'source_urls':['https://sports.yahoo.co.jp/keiba/race/odds/'+chat.PAGES[kind]+'/2605040601?ninki=0']}


def excerpt(req, phase='中間オッズ', price=None):
    kind=req['ticket']['type']; values=req['ticket'].get('horses',req['ticket'].get('frames'))
    date=req['race_date_jst']; y,m,d=map(int,date.split('-'))
    header=f'{y}年{m}月{d}日\n1R\n4回東京6日\n'+req['scheduled_post_time_jst'][11:16]+'発走\n'+phase+'\n'
    price=price or ('3.0 - 4.0' if kind in {'PLACE','WIDE'} else '12.5')
    if kind in {'WIN','PLACE'}:
        rows='### 単勝・複勝\n枠番 | 馬番 | 馬名 | 単勝 | 複勝\n1 | '+str(values[0])+' | 合成馬 | '+(price if kind=='WIN' else '12.5')+' | '+(price if kind=='PLACE' else '3.0 - 4.0')+'\n'
    elif kind=='TRIFECTA': rows='馬番 | オッズ\n'+' - '.join(map(str,values))+' | '+price+'\n'
    else:
        rows=('### 枠連\n' if kind=='BRACKET_QUINELLA' else '')+'－'.join(map(str,values[:-1]))+'\n---\n'+str(values[-1])+' | '+price+'\n'
    return header+rows+f'{y}/{m:02d}/{d:02d} 09:55 更新\n'


def capture(req, **changes):
    value={'schema_version':chat.CAPTURE,'source_url':req['source_urls'][-1],
           'started_at_jst':req['race_date_jst']+'T09:58:00+09:00',
           'retrieved_at_jst':req['race_date_jst']+'T09:59:00+09:00',
           'retrieval_kind':'SYNTHETIC_PAGE_TEXT' if req['mode']=='SYNTHETIC' else 'PAGE_TEXT',
           'tool_reference':'SYNTHETIC_FIXTURE_NOT_WEB_RESULT','excerpt':excerpt(req)}
    value.update(changes);return value


class ChatAcquisitionTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);self.root=Path(tmp.name)

    def collect(self, req=None, captures=None, folder='market/run'):
        req=req or request();captures=captures if captures is not None else [capture(req)]
        p,raws=chat.collect(req,captures,folder)
        acquisition.save(self.root,folder,p,raws)
        acquisition.verify_responses(self.root,p,require_forward=False)
        return p

    def test_all_eight_ticket_formats_roundtrip_and_range(self):
        for kind in chat.PAGES:
            with self.subTest(kind=kind):
                p=self.collect(request(kind),folder='market/'+kind)
                self.assertEqual(p['market']['status'],'ACQUIRED')
                self.assertEqual(p['market']['odds'],3.0 if kind in {'PLACE','WIDE'} else 12.5)
                self.assertEqual(p['market']['price_details']['upper'],4.0 if kind in {'PLACE','WIDE'} else 12.5)
                self.assertIsNone(p['market']['expected_value'])

    def test_actual_replay_excerpts_match_all_eight_ticket_formats(self):
        f=json.loads((Path(__file__).resolve().parents[1]/'docs/validation/market-chat-research/2026-10-13/replay-pages.json').read_text())
        cases=[('WIN',0,[1],5.9),('PLACE',0,[1],1.4),('BRACKET_QUINELLA',0,[1,2],4.5),
               ('QUINELLA',1,[1,2],4.8),('WIDE',2,[1,2],1.9),('EXACTA',3,[1,2],14.8),
               ('TRIO',4,[1,2,3],15.5),('TRIFECTA',5,[1,2,3],94.0)]
        for kind,index,numbers,price in cases:
            with self.subTest(kind=kind):
                req=request(kind,numbers,mode='REPLAY',date=f['race_date_jst'])
                req.update(race_id=f['race_id'],scheduled_post_time_jst=f['scheduled_post_time_jst'])
                c=f['pages'][index];req['source_urls']=[c['source_url']]
                p=self.collect(req,[c],folder='replay/'+kind)
                self.assertEqual(p['market']['odds'],price)
                self.assertEqual(p['market']['price_details']['publication_phase'],'確定オッズ')
                with self.assertRaises(ValueError):chat.verify(self.root,p)

    def test_unknown_time_is_failure_without_price(self):
        req=request();c=capture(req);c['excerpt']=c['excerpt'].split('2026/')[0]
        p=self.collect(req,[c]);self.assertEqual(p['market']['reason'],chat.ERRORS['TIME_UNKNOWN'])
        self.assertIsNone(p['market']['odds'])

    def test_final_and_confirmed_are_rejected_forward(self):
        for phase in ('確定オッズ','最終オッズ'):
            req=request(mode='FORWARD');p=self.collect(req,[capture(req,excerpt=excerpt(req,phase))],folder='market/'+phase)
            self.assertEqual(p['market']['reason'],chat.ERRORS['FINAL_PRICE'])

    def test_replay_can_parse_final_but_cannot_register_formally(self):
        req=request(mode='REPLAY');p=self.collect(req,[capture(req,excerpt=excerpt(req,'確定オッズ'))])
        self.assertEqual(p['market']['status'],'ACQUIRED')
        with self.assertRaisesRegex(ValueError,'正式市場'):chat.verify(self.root,p)

    def test_search_snippet_is_never_evidence(self):
        req=request();p=self.collect(req,[capture(req,retrieval_kind='SEARCH_SNIPPET')])
        self.assertEqual(p['market']['reason'],chat.ERRORS['SEARCH_SNIPPET'])

    def test_access_denied_is_japanese_failure(self):
        req=request();p=self.collect(req,[capture(req,retrieval_kind='ERROR',error_code='ACCESS_DENIED',excerpt=None)])
        self.assertEqual(describe(p)['取得状態'],'価格取得に失敗')
        self.assertIn('拒否',p['market']['reason']);self.assertEqual(p['market']['decision'],'NOT_EVALUATED')

    def test_late_response_keeps_actual_finish_and_no_price(self):
        req=request();p=self.collect(req,[capture(req,retrieved_at_jst=DATE+'T10:02:00+09:00')])
        self.assertEqual(describe(p)['取得状態'],'締切により価格取得を停止')
        self.assertEqual(p['market']['acquisition']['attempts'][0]['finished_at_jst'],DATE+'T10:02:00+09:00')
        self.assertIsNone(p['market']['odds'])

    def test_unattempted_has_no_fabricated_history(self):
        p=self.collect(captures=[]);self.assertEqual(p['market']['status'],'NOT_ATTEMPTED')
        self.assertEqual(p['market']['acquisition']['attempts'],[])

    def test_source_credentials_other_hosts_and_queries_rejected(self):
        for url in ('http://sports.yahoo.co.jp/keiba/race/odds/tfw/2605040601',
                    'https://x:y@sports.yahoo.co.jp/keiba/race/odds/tfw/2605040601',
                    'https://sports.yahoo.co.jp.evil.invalid/keiba/race/odds/tfw/2605040601',
                    'https://sports.yahoo.co.jp/keiba/race/odds/tfw/2605040601?ninki=0&key=',
                    'https://sports.yahoo.co.jp/keiba/race/odds/tfw/2605040601#x'):
            with self.subTest(url=url),self.assertRaises(ValueError):chat.source(url)

    def test_race_date_venue_post_and_page_mismatch_are_failure(self):
        req=request()
        for old,new in [('2026年10月17日','2026年10月18日'),('東京','京都'),('1R','2R'),
                        (req['scheduled_post_time_jst'][11:16]+'発走','23:59発走')]:
            p,_=chat.collect(req,[capture(req,excerpt=excerpt(req).replace(old,new))],'test')
            self.assertEqual(p['market']['reason'],chat.ERRORS['INVALID_PAGE'])
        req['source_urls']=[req['source_urls'][0].replace('/tfw/','/ur/')]
        p,_=chat.collect(req,[capture(req)],'test');self.assertEqual(p['market']['status'],'FAILED')

    def test_duplicate_and_missing_ticket_rows_are_failure(self):
        req=request();c=capture(req)
        for text in (c['excerpt'].replace('1 | 1 |','1 | 2 |'),c['excerpt'].replace('2026/','1 | 1 | 合成馬 | 12.5 | 3.0 - 4.0\n2026/')):
            p,_=chat.collect(req,[capture(req,excerpt=text)],'test');self.assertEqual(p['market']['status'],'FAILED')

    def test_reversed_order_is_not_reinterpreted(self):
        req=request('EXACTA',[2,1]);p,_=chat.collect(req,[capture(req,excerpt=excerpt(request('EXACTA',[1,2])))],'test')
        self.assertEqual(p['market']['status'],'FAILED')
        req=request('TRIFECTA',[3,2,1]);p=self.collect(req);self.assertEqual(p['ticket']['horses'],[3,2,1])

    def test_same_frame_is_preserved(self):
        p=self.collect(request('BRACKET_QUINELLA',[5,5]));self.assertEqual(p['ticket']['frames'],[5,5])

    def test_future_or_multiple_update_stamps_are_failure(self):
        req=request();text=excerpt(req)
        for value in (text.replace('09:55 更新','10:01 更新'),text+'2026/10/17 09:55 更新\n'):
            p,_=chat.collect(req,[capture(req,excerpt=value)],'test');self.assertEqual(p['market']['status'],'FAILED')

    def test_missing_cancelled_invalid_ranges_and_capped_prices_are_failure(self):
        for kind,value in [('WIN','****'),('WIN','0'),('WIN','999.9'),('PLACE','4.0 - 3.0'),
                           ('PLACE','3.0'),('WIN','3.0 - 4.0'),('TRIFECTA','999999.9')]:
            req=request(kind);p,_=chat.collect(req,[capture(req,excerpt=excerpt(req,price=value))],'test')
            self.assertEqual(p['market']['status'],'FAILED')

    def test_trifecta_below_own_cap_is_accepted(self):
        req=request('TRIFECTA');p=self.collect(req,[capture(req,excerpt=excerpt(req,price='100000.0'))])
        self.assertEqual(p['market']['odds'],100000.0)

    def test_two_primary_failures_then_alternate_success(self):
        req=request();req['source_urls'].insert(0,'https://www.jra.go.jp/JRADB/accessO.html')
        a=capture(req,source_url=req['source_urls'][0],retrieval_kind='ERROR',error_code='UNAVAILABLE',excerpt=None,
                  started_at_jst=DATE+'T09:56:00+09:00',retrieved_at_jst=DATE+'T09:56:30+09:00')
        b=copy.deepcopy(a);b.update(started_at_jst=DATE+'T09:57:00+09:00',retrieved_at_jst=DATE+'T09:57:30+09:00')
        p=self.collect(req,[a,b,capture(req)])
        self.assertEqual([x['result'] for x in p['market']['acquisition']['attempts']],['FAILED','FAILED','ACQUIRED'])

    def test_retry_limit_and_after_success_are_rejected(self):
        req=request();a=capture(req,retrieval_kind='ERROR',error_code='UNAVAILABLE',excerpt=None)
        a['started_at_jst']=a['retrieved_at_jst']
        with self.assertRaises(ValueError):chat.collect(req,[a,a,a],'test')
        with self.assertRaises(ValueError):chat.collect(req,[capture(req),a],'test')

    def test_modified_capture_bytes_and_price_are_rejected(self):
        p=self.collect();ref=p['market']['acquisition']['attempts'][0]['capture_ref'];path=self.root/ref['artifact_path']
        original=path.read_bytes();path.write_bytes(original+b' ')
        with self.assertRaisesRegex(ValueError,'hash/size'):chat.verify(self.root,p,require_forward=False)
        path.write_bytes(original);p['market']['odds']=99
        with self.assertRaisesRegex(ValueError,'再計算'):chat.verify(self.root,p,require_forward=False)

    def test_changed_request_and_synthetic_formal_registration_rejected(self):
        p=self.collect()
        with self.assertRaisesRegex(ValueError,'正式市場'):chat.verify(self.root,p)
        p['ticket']['horses']=[2]
        with self.assertRaises(ValueError):chat.verify(self.root,p,require_forward=False)

    def test_http_status_fabrication_and_path_traversal_rejected(self):
        p=self.collect();p['market']['acquisition']['attempts'][0]['http_status']=200
        with self.assertRaisesRegex(ValueError,'HTTP原応答'):chat.verify(self.root,p,require_forward=False)
        with self.assertRaises(ValueError):chat.collect(request(),[],'../escape')

    def test_synthetic_and_real_capture_modes_cannot_mix(self):
        req=request();c=capture(req,retrieval_kind='PAGE_TEXT')
        with self.assertRaises(ValueError):chat.collect(req,[c],'test')

    def test_cli_japanese_display_keeps_original_bytes(self):
        p=self.collect();path=self.root/'market/run/analysis.json';before=path.read_bytes();out=io.StringIO()
        with redirect_stdout(out):self.assertEqual(describe_main([str(path)]),0)
        self.assertIn('価格取得済み',out.getvalue());self.assertIn('期待値は未評価',out.getvalue())
        self.assertEqual(path.read_bytes(),before)


class ChatWriterTests(unittest.TestCase):
    setUp=fixtures.MarketPersistence.setUp
    register=fixtures.MarketPersistence.register
    select=fixtures.MarketPersistence.select
    final=fixtures.MarketPersistence.final
    save_market=fixtures.MarketPersistence.save_market

    def test_success_failure_deadline_keep_prediction_and_recommendation(self):
        self.final();day,_=workflow.read_day(self.root,DATE)
        kpis=copy.deepcopy({k:day['kpis'][k] for k in ('production','recommendation')})
        paths=[day['races'][RACE]['operations']['prediction_ref']['artifact_path'],day['races'][RACE]['recommendation_gate_path']]
        before={p:(self.root/p).read_bytes() for p in paths}
        req=request(mode='FORWARD');self.assertEqual(req['race_id'],RACE)
        cases=[capture(req),capture(req,retrieval_kind='ERROR',error_code='ACCESS_DENIED',excerpt=None),
               capture(req,retrieved_at_jst=DATE+'T10:00:00+09:00')]
        for n,c in enumerate(cases):
            p,raws=chat.collect(req,[c],'chat/'+str(n));acquisition.save(self.root,'chat/'+str(n),p,raws)
            self.save_market(p,'chat'+str(n));after,_=workflow.read_day(self.root,DATE)
            self.assertEqual({k:after['kpis'][k] for k in kpis},kpis)
        self.assertEqual({p:(self.root/p).read_bytes() for p in paths},before)

    def test_missing_receipt_replay_and_tampering_cannot_register(self):
        self.final();req=request(mode='FORWARD');p,raws=chat.collect(req,[capture(req)],'chat/run')
        acquisition.save(self.root,'chat/run',p,raws)
        path=self.root/workflow.DIRECTORY/(DATE+'.json');before=path.read_bytes()
        with self.assertRaises(ValueError):workflow.record_market(self.root,DATE,{'race_id':RACE,'market_ref':{'artifact_path':'chat/run/analysis.json'}})
        p['market']['odds']=77
        with self.assertRaises(ValueError):self.save_market(p,'changed')
        self.assertEqual(path.read_bytes(),before)


if __name__=='__main__':unittest.main()
