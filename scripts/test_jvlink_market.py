"""公式レコード形・SDK呼出し契約の合成受入。Windows実接続の成功とは数えない。"""
import copy
import json
import os
import itertools
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import jvlink_market as jv
import market_acquisition as acquisition
from check_prediction_compliance import ComplianceError
from test_market_acquisition import Clock, request
from test_recommendation import DATE, RACE


# 公式SDKの位置に固定した独立fixture。実装LAYOUT/LENGTHSを参照しない。
SDK_FIXTURES = {
    'WIN':('O1',962,43,8,2,4,False),
    'PLACE':('O1',962,267,12,2,4,True),
    'BRACKET_QUINELLA':('O1',962,603,9,2,5,False),
    'QUINELLA':('O2',2042,40,13,4,6,False),
    'WIDE':('O3',2654,40,17,4,5,True),
    'EXACTA':('O4',4031,40,13,4,6,False),
    'TRIO':('O5',12293,40,15,6,6,False),
    'TRIFECTA':('O6',83285,40,17,6,7,False)}


def fixture_position(kind, numbers):
    spec,length,base,stride,key_size,width,ranged=SDK_FIXTURES[kind]
    if kind in {'WIN','PLACE'}:
        index=numbers[0]-1
    elif kind=='BRACKET_QUINELLA':
        index=list(itertools.combinations_with_replacement(range(1,9),2)).index(tuple(numbers))
    elif kind in {'EXACTA','TRIFECTA'}:
        index=list(itertools.permutations(range(1,19),len(numbers))).index(tuple(numbers))
    else:
        index=list(itertools.combinations(range(1,19),len(numbers))).index(tuple(numbers))
    return base+index*stride


def record(kind='QUINELLA', numbers=None, date=DATE, code=None, price=125):
    spec,length,base,stride,key_size,width,ranged=SDK_FIXTURES[kind]
    raw = bytearray(b' ' * length); raw[-2:] = b'\r\n'
    raw[:3] = (spec+'1').encode(); raw[3:11] = date.replace('-','').encode()
    raw[11:27] = (date.replace('-','')+'05'+'04'+'01'+'01').encode()
    raw[27:35] = (date[5:7]+date[8:10]+'0859').encode()
    raw[39:42] = b'777'
    if numbers is None: numbers = [2] if kind in {'WIN','PLACE'} else ([2,5,6] if kind in {'TRIO','TRIFECTA'} else [2,5])
    offset=fixture_position(kind,numbers)
    field = ''.join(str(v) if kind == 'BRACKET_QUINELLA' else f'{v:02d}' for v in numbers)
    raw[offset:offset+key_size] = field.encode()
    raw[offset+key_size:offset+key_size+width] = f'{price:0{width}d}'.encode()
    if ranged: raw[offset+key_size+width:offset+key_size+2*width] = f'{price+50:0{width}d}'.encode()
    return bytes(raw)


def native_request(kind='QUINELLA', date=DATE, alternate=False):
    req = request(); req['mode'] = 'FORWARD'
    req['race_date_jst'] = date; req['race_id'] = date.replace('-','')+'-TOK-01'
    for field in ['data_cutoff','deadline_at_jst','scheduled_post_time_jst']:
        req[field] = req[field].replace(DATE,date)
    values = [2] if kind in {'WIN','PLACE'} else ([2,5,6] if kind in {'TRIO','TRIFECTA'} else [2,5])
    req['ticket'] = {'type':kind,'frames' if kind=='BRACKET_QUINELLA' else 'horses':values}
    req['routes'] = jv.routes_for(req,alternate)
    return req


class NativeTests(unittest.TestCase):
    def setUp(self):
        self.req = native_request(); self.clock = Clock()
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup); self.root = Path(tmp.name)

    def capture(self, req=None, values=None):
        req = req or self.req; values = values or [(0,record(req['ticket']['type']),True,None)]
        return acquisition.collect(req,'evidence/run',fetch=lambda url,timeout:values.pop(0),
                                   now=self.clock.now,sleep=self.clock.sleep)

    def test_all_eight_ticket_types_and_observed_range(self):
        for kind in SDK_FIXTURES:
            req = native_request(kind)
            data = jv.normalize(record(kind),req,self.clock.now())
            self.assertEqual(data['odds'],12.5)
            self.assertEqual(data['price_details']['upper'],17.5 if kind in {'PLACE','WIDE'} else 12.5)

    def test_same_frame_and_ordered_ticket_preserved(self):
        req = native_request('BRACKET_QUINELLA'); req['ticket']['frames'] = [2,2]
        jv.normalize(record('BRACKET_QUINELLA',[2,2]),req,self.clock.now())
        req = native_request('EXACTA'); req['ticket']['horses'] = [5,2]
        with self.assertRaises(ComplianceError):
            jv.normalize(record('EXACTA',[2,5]),req,self.clock.now())

    def test_wrong_date_venue_race_and_record_length_rejected(self):
        for offset, data in [(11,b'20251017'),(19,b'08'),(25,b'02')]:
            raw = bytearray(record()); raw[offset:offset+len(data)] = data
            with self.assertRaises(ComplianceError): jv.normalize(bytes(raw),self.req,self.clock.now())
        with self.assertRaises(ComplianceError): jv.normalize(record()[:-1],self.req,self.clock.now())

    def test_final_cancelled_deleted_missing_and_future_time_rejected(self):
        for offset, value in [(2,b'3'),(2,b'4'),(2,b'9'),(2,b'0'),(27,b'00000000'),(27,b'10171000')]:
            raw = bytearray(record()); raw[offset:offset+len(value)] = value
            with self.assertRaises(ComplianceError): jv.normalize(bytes(raw),self.req,self.clock.now())

    def test_unavailable_price_and_sale_flag_rejected(self):
        for value in [b'000000',b'------',b'******',b'      ',b'999999',b'099999']:
            raw = bytearray(record()); pos=fixture_position('QUINELLA',[2,5]); raw[pos+4:pos+10] = value
            with self.assertRaises(ComplianceError): jv.normalize(bytes(raw),self.req,self.clock.now())
        raw = bytearray(record()); raw[39:40] = b'0'
        with self.assertRaises(ComplianceError): jv.normalize(bytes(raw),self.req,self.clock.now())

    def test_duplicate_combination_and_reversed_range_rejected(self):
        raw = bytearray(record()); pos=fixture_position('QUINELLA',[2,5]); raw[pos+13:pos+26] = raw[pos:pos+13]
        with self.assertRaises(ComplianceError): jv.normalize(bytes(raw),self.req,self.clock.now())
        raw = bytearray(record('WIDE')); pos=fixture_position('WIDE',[2,5]); raw[pos+9:pos+14] = b'00001'
        with self.assertRaises(ComplianceError): jv.normalize(bytes(raw),native_request('WIDE'),self.clock.now())

    def test_whole_and_specific_routes_are_frozen_and_manual_urls_unnecessary(self):
        self.assertEqual(jv.address(self.req['routes'][0]['source_url'],self.req)[0],'0B30')
        self.assertEqual(jv.address(self.req['routes'][1]['source_url'],self.req)[0],'0B32')
        req = copy.deepcopy(self.req); req['routes'][0]['source_url'] = 'jvlink://JVDTLab.JVLink/0B30/202610170801'
        with self.assertRaises(ComplianceError): acquisition.validate_request(req)

    def test_native_success_raw_readback_never_claims_http_status(self):
        p, raws = self.capture()
        acquisition.save(self.root,'evidence/run',p,raws)
        acquisition.verify_responses(self.root,p)
        a = p['market']['acquisition']['attempts'][0]
        self.assertIsNone(a['http_status']); self.assertEqual(a['jv_status'],0)
        self.assertEqual(p['market']['price_details']['basis'],'OBSERVED_EXACT')

    def test_native_error_falls_back_to_specific_data_without_fabricated_response(self):
        p, raws = self.capture(values=[(-301,None,None,'JV_ERROR'),(0,record(),True,None)])
        acquisition.save(self.root,'evidence/run',p,raws)
        self.assertIn('/0B32/',p['market']['source_ref'])
        self.assertIsNone(p['market']['acquisition']['attempts'][0]['response_ref'])

    def test_unavailable_native_environment_is_failure_not_live_evidence(self):
        p, raws = self.capture(values=[(None,None,None,'JV_UNAVAILABLE')]*2)
        acquisition.save(self.root,'evidence/run',p,raws)
        self.assertEqual(p['market']['status'],'FAILED')
        self.assertIsNone(p['market']['odds'])

    def test_native_error_with_partial_records_is_preserved(self):
        p, raws = self.capture(values=[(-203,record(),True,'JV_ERROR'),(0,record(),True,None)])
        acquisition.save(self.root,'evidence/run',p,raws)
        self.assertEqual(len(raws),1)
        self.assertEqual(len(p['market']['acquisition']['attempts']),2)

    def test_raw_price_details_tampering_is_rejected(self):
        p, raws = self.capture(); acquisition.save(self.root,'evidence/run',p,raws)
        p['market']['price_details']['upper'] = 999
        with self.assertRaisesRegex(ComplianceError,'price details'):
            acquisition.verify_responses(self.root,p)

    def test_native_synthetic_evidence_is_not_formal(self):
        self.req['mode'] = 'SYNTHETIC'; p, raws = self.capture()
        acquisition.save(self.root,'evidence/run',p,raws)
        with self.assertRaisesRegex(ComplianceError,'synthetic'):
            acquisition.verify_responses(self.root,p)

    def test_sdk_call_contract_read_switch_eof_and_close(self):
        class API:
            def __init__(self): self.closed=False; self.calls=[]; self.values=[(-1,b'',b''),(len(record()),record(),b'file'),(0,b'',b'')]
            def JVInit(self,sid): self.calls.append(('init',sid)); return 0
            def JVRTOpen(self,spec,key): self.calls.append(('open',spec,key)); return 0
            def JVGets(self,buff,size,name):
                if not isinstance(buff,bytearray) or not isinstance(name,bytearray): raise AssertionError('official SDK buffer type')
                return self.values.pop(0)
            def JVClose(self): self.closed=True
        api=API(); code,raw,complete,error = jv.read_api(api,self.req['routes'][0]['source_url'])
        self.assertEqual(raw,record()); self.assertEqual(code,0); self.assertTrue(api.closed)
        self.assertEqual(api.calls[0],('init','UNKNOWN'))
        self.assertEqual(api.calls[1],('open','0B30','202610170501'))

    def test_sdk_init_and_open_errors_close_without_reading(self):
        for init,opened in [(-301,0),(0,-111)]:
            class API:
                closed=False
                def JVInit(self,sid): return init
                def JVRTOpen(self,spec,key): return opened
                def JVClose(self): self.closed=True
            api=API(); code,raw,complete,error = jv.read_api(api,self.req['routes'][0]['source_url'])
            self.assertEqual(code,init or opened); self.assertIsNone(raw); self.assertTrue(api.closed)

    def test_subprocess_deadline_is_enforced_and_not_reported_as_price(self):
        import subprocess
        with patch('jvlink_market.os.name','nt'), patch('jvlink_market.subprocess.run',
                side_effect=subprocess.TimeoutExpired('worker',.1)):
            self.assertEqual(jv.fetch(self.req['routes'][0]['source_url'],.1),(None,None,None,'TRANSPORT_ERROR'))

    def test_windows_capture_paths_remain_git_portable(self):
        from pathlib import PureWindowsPath
        with patch('market_acquisition.Path',PureWindowsPath):
            p,raws=self.capture()
        self.assertTrue(all('\\' not in path and path.startswith('evidence/run/responses/') for path in raws))
        acquisition.save(self.root,'evidence/run',p,raws)
        acquisition.verify_responses(self.root,p)
