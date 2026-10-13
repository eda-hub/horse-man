"""公式JV-Link/O1〜O6を観測価格へ正規化。投票API・利用キーの操作はしない。"""
import base64
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse

from cycle04_operations import require
from check_prediction_compliance import iso

MAX_BYTES = 131072
LENGTHS = {'O1':962, 'O2':2042, 'O3':2654, 'O4':4031, 'O5':12293, 'O6':83285}
# SDKの1開始位置を0開始へ変換した読取レイアウト。元仕様はdocsの固定参照。
LAYOUT = {'WIN':('O1',43,28,8,2,4,False),
          'PLACE':('O1',267,28,12,2,4,True),
          'BRACKET_QUINELLA':('O1',603,36,9,2,5,False),
          'QUINELLA':('O2',40,153,13,4,6,False),
          'WIDE':('O3',40,153,17,4,5,True),
          'EXACTA':('O4',40,306,13,4,6,False),
          'TRIO':('O5',40,816,15,6,6,False),
          'TRIFECTA':('O6',40,4896,17,6,7,False)}
SPEC = {'O1':'0B31','O2':'0B32','O3':'0B33','O4':'0B34','O5':'0B35','O6':'0B36'}
VENUES = {'TOK':'05','KYO':'08','NII':'04','NAK':'06','HAN':'09',
          'CHU':'07','SAP':'01','HAK':'02','FUK':'03','KOK':'10'}


def key_for(request):
    parts = request['race_id'].split('-')
    require(len(parts) == 3 and parts[1] in VENUES and re.fullmatch(r'0[1-9]|1[0-2]', parts[2]),
            'JRA race identity required')
    require(parts[0] == request['race_date_jst'].replace('-',''), 'JRA race date mismatch')
    return parts[0]+VENUES[parts[1]]+parts[2]


def routes_for(request, alternate_first=False):
    kind = request['ticket']['type']
    require(kind in LAYOUT, 'JV-Link ticket type unsupported')
    key = key_for(request); specific = SPEC[LAYOUT[kind][0]]
    specs = [specific,'0B30'] if alternate_first else ['0B30',specific]
    return [{'provider':'JV_LINK','source_url':'jvlink://JVDTLab.JVLink/'+spec+'/'+key,
             'max_attempts':1} for spec in specs]


def address(url, request=None):
    p = urlparse(url)
    parts = p.path.strip('/').split('/')
    require(p.scheme == 'jvlink' and p.hostname == 'jvdtlab.jvlink' and
            p.username is None and p.password is None and not p.query and not p.fragment
            and len(parts) == 2 and parts[0] in {'0B30', *SPEC.values()}
            and re.fullmatch(r'\d{12}', parts[1]), 'invalid official JV-Link source')
    if request is not None:
        require(parts[1] == key_for(request) and parts[0] in
                {'0B30',SPEC[LAYOUT[request['ticket']['type']][0]]}, 'JV-Link source/request mismatch')
    return parts


def normalize(raw, request, acquired_at):
    from market_acquisition import ticket_key
    kind, numbers = ticket_key(request['ticket'])
    rec_id, offset, count, stride, key_size, width, ranged = LAYOUT[kind]
    desired = ''.join(str(n) if kind == 'BRACKET_QUINELLA' else f'{n:02d}' for n in numbers)
    expected_key = key_for(request)
    matches = []
    for record in raw.splitlines(keepends=True):
        require(len(record) >= 2, 'invalid JV record')
        code = record[:2].decode('ascii')
        require(code in LENGTHS and len(record) == LENGTHS[code] and record.endswith(b'\r\n'),
                'JV record type/length/terminator mismatch')
        if code != rec_id: continue
        require(record[11:21].decode('ascii')+record[25:27].decode('ascii') == expected_key,
                'JV record race mismatch')
        require(record[2:3] == b'1', 'final/cancelled/deleted JV odds are not forward observations')
        stamp = record[27:35].decode('ascii')
        require(stamp.isdigit() and stamp != '00000000', 'JV observed time missing')
        year = int(request['race_date_jst'][:4])
        observed = datetime(year,int(stamp[:2]),int(stamp[2:4]),int(stamp[4:6]),int(stamp[6:8]),
                            tzinfo=timezone(timedelta(hours=9)))
        require(observed <= acquired_at and observed <= iso(request['deadline_at_jst'],'JV deadline')
                and observed <= iso(request['data_cutoff'],'JV cutoff'), 'future JV observation')
        flag = 39+({'WIN':0,'PLACE':1,'BRACKET_QUINELLA':2}.get(kind,0))
        require(record[flag:flag+1] == b'7', 'JV ticket is not on sale')
        rows = [record[offset+i*stride:offset+(i+1)*stride] for i in range(count)]
        found = [r for r in rows if r[:key_size].decode('ascii') == desired]
        require(len(found) == 1, 'JV combination missing/duplicated')
        row = found[0]
        cells = [row[key_size:key_size+width]]
        if ranged: cells.append(row[key_size+width:key_size+2*width])
        require(all(c.isdigit() and int(c)>0 and c != b'9'*width and
                    c != (b'0'+b'9'*(width-1)) for c in cells),
                'JV odds unavailable/cancelled/capped; exact observation not inferred')
        lower, upper = int(cells[0])/10, int(cells[-1])/10
        require(lower <= upper, 'JV odds range reversed')
        result = {'schema_version':'market-price-response-v1','race_id':request['race_id'],
                  'ticket':request['ticket'],'observed_at_jst':observed.isoformat(),'odds':lower,
                  'price_details':{'provider':'JRA_VAN','record_type':rec_id,
                                   'basis':'OBSERVED_RANGE_LOWER' if ranged else 'OBSERVED_EXACT',
                                   'lower':lower,'upper':upper}}
        matches.append(result)
    require(len(matches) == 1, 'exactly one matching JV odds record required')
    return matches[0]


def read_api(api, url):
    spec, key = address(url)
    chunks = []
    try:
        code = api.JVInit('UNKNOWN')
        if code != 0: return code, None, None, 'JV_ERROR'
        code = api.JVRTOpen(spec,key)
        if code != 0: return code, None, None, 'JV_ERROR'
        for _ in range(128):
            code, data, filename = api.JVGets(bytearray(MAX_BYTES+1),MAX_BYTES+1,bytearray())
            if code == -1: continue
            if code == 0: return 0,b''.join(chunks),True,None
            if code < 0: return code,b''.join(chunks) or None,True,'JV_ERROR'
            raw = bytes(data)
            require(len(raw) >= code, 'truncated JV buffer')
            chunks.append(raw[:code])
            if sum(map(len,chunks)) > MAX_BYTES:
                return 0,b''.join(chunks)[:MAX_BYTES+1],False,'INCOMPLETE_RESPONSE'
        return None,b''.join(chunks) or None,True,'JV_READ_LIMIT'
    finally:
        api.JVClose()


def worker(url):
    if os.name != 'nt': return None,None,None,'JV_UNAVAILABLE'
    try:
        import pythoncom
        import win32com.client
    except ImportError:
        return None,None,None,'JV_UNAVAILABLE'
    pythoncom.CoInitialize()
    try:
        api = win32com.client.Dispatch('JVDTLab.JVLink')
        return read_api(api,url)
    except Exception:
        return None,None,None,'JV_UNAVAILABLE'
    finally:
        pythoncom.CoUninitialize()


def fetch(url, timeout):
    address(url)
    if os.name != 'nt': return None,None,None,'JV_UNAVAILABLE'
    try:
        proc = subprocess.run([sys.executable,__file__,'--worker',url],
                              capture_output=True,timeout=timeout,check=True)
        data = json.loads(proc.stdout)
        raw = base64.b64decode(data['raw']) if data['raw'] is not None else None
        return data['code'],raw,data['complete'],data['error']
    except subprocess.TimeoutExpired:
        return None,None,None,'TRANSPORT_ERROR'
    except (ValueError, OSError, subprocess.CalledProcessError):
        return None,None,None,'JV_UNAVAILABLE'


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--worker':
        code, raw, complete, error = worker(sys.argv[2])
        print(json.dumps({'code':code,'raw':base64.b64encode(raw).decode() if raw is not None else None,
                          'complete':complete,'error':error}))
    else:
        print('取得はmarket_acquisition.py --jvlinkで実行してください。Windows・pywin32・JV-Linkが必要です。')
        sys.exit(1)
