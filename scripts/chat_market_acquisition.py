#!/usr/bin/env python3
"""チャット閲覧の最小本文を保存・再照合。通信、端末接続、投票は行わない。"""
import argparse
import copy
import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urlparse

from check_prediction_compliance import iso
from cycle04_operations import require, fingerprint, safe_path, validate_market_payload
from market_acquisition import ticket_key

TRANSPORT = 'market-chat-acquisition-v1'
CAPTURE = 'chat-page-retrieval-v1'
JST = timezone(timedelta(hours=9))
VENUES = {'TOK': ('東京', '05'), 'KYO': ('京都', '08'), 'NII': ('新潟', '04'),
          'NAK': ('中山', '06'), 'HAN': ('阪神', '09'), 'CHU': ('中京', '07'),
          'SAP': ('札幌', '01'), 'HAK': ('函館', '02'), 'FUK': ('福島', '03'), 'KOK': ('小倉', '10')}
PAGES = {'WIN':'tfw', 'PLACE':'tfw', 'BRACKET_QUINELLA':'tfw', 'QUINELLA':'ur',
         'WIDE':'wide', 'EXACTA':'ut', 'TRIO':'sf', 'TRIFECTA':'st'}
ERRORS = {'ACCESS_DENIED':'公開本文へのアクセスを拒否された', 'UNAVAILABLE':'公開本文を取得できない',
          'SEARCH_SNIPPET':'検索抜粋は観測価格の証跡に使えない',
          'TIME_UNKNOWN':'掲載更新時刻を確認できない', 'INVALID_PAGE':'対象券・時刻・本文形式を照合できない',
          'FINAL_PRICE':'最終・確定価格は発走前観測に使えない',
          'UNSUPPORTED_SOURCE':'この取得元の本文正規化は未受入',
          'DEADLINE_EXCEEDED':'締切を超えたため価格を採用しない'}


def source(url):
    p = urlparse(url)
    require(p.scheme == 'https' and p.username is None and p.password is None and
            p.port is None and not p.fragment, '公開HTTPS出所が必要')
    if p.hostname == 'sports.yahoo.co.jp':
        m = re.fullmatch(r'/keiba/race/odds/(tfw|ur|wide|ut|sf|st)/(\d{10})', p.path)
        require(m and p.query in {'', 'ninki=0', 'ninki=1'},
                '公開オッズの出所形式が不正')
        return 'SPORTS_NAVI', m.group(1), m.group(2)
    require(p.hostname in {'www.jra.go.jp','jra.go.jp','jra.jp','www.jra.jp','own.jra.jp'} and
            p.path.startswith('/JRADB/'), '登録済みの公開オッズ出所が必要')
    require(not p.query, '未受入の公式クエリは使用しない')
    return 'JRA', None, None


def request_times(request):
    require(isinstance(request, dict) and request.get('schema_version') == 'chat-market-request-v1',
            'チャット取得要求が必要')
    require(request.get('mode') in {'FORWARD','REPLAY','SYNTHETIC'}, '取得modeが必要')
    date = request.get('race_date_jst'); parts = request.get('race_id','').split('-')
    require(isinstance(date,str) and len(parts) == 3 and parts[0] == date.replace('-','') and
            parts[1] in VENUES and re.fullmatch(r'0[1-9]|1[0-2]',parts[2]), '開催IDが不正')
    ticket_key(request.get('ticket'))
    deadline = iso(request.get('deadline_at_jst'),'締切')
    cutoff = iso(request.get('data_cutoff'),'cutoff'); post = iso(request.get('scheduled_post_time_jst'),'発走')
    require(deadline <= cutoff < post and post.astimezone(JST).date().isoformat() == date,
            '締切/cutoff/発走が不整合')
    urls = request.get('source_urls')
    require(isinstance(urls,list) and 1 <= len(urls) <= 2 and len(set(urls)) == len(urls),
            '取得元は重複なしで最大2つ')
    providers = [source(u)[0] for u in urls]
    require(len(set(providers)) == len(providers), '同じ提供元を独立した代替へ数えない')
    return deadline, cutoff, post


def parse_page(text, url, request, retrieved):
    """実際のスポーツナビ本文形式を再解析。値・時刻の自己申告では通さない。"""
    provider, page, racecode = source(url)
    require(provider == 'SPORTS_NAVI', 'UNSUPPORTED_SOURCE')
    kind, numbers = ticket_key(request['ticket'])
    require(page == PAGES[kind], 'INVALID_PAGE')
    parts = request['race_id'].split('-'); venue, code = VENUES[parts[1]]
    require(racecode[:2] == parts[0][2:4] and racecode[2:4] == code and racecode[-2:] == parts[2], 'INVALID_PAGE')
    dates = set(re.findall(r'(\d{4})年(\d{1,2})月(\d{1,2})日',text))
    require(len(dates) == 1, 'INVALID_PAGE')
    y,m,d = next(iter(dates)); date = f'{int(y):04d}-{int(m):02d}-{int(d):02d}'
    require(date == request['race_date_jst'] and re.search(rf'(?m)^\s*{int(parts[2])}R\s*$',text) and
            re.search(rf'{int(racecode[4:6])}回{venue}{int(racecode[6:8])}日',text), 'INVALID_PAGE')
    posts = re.findall(r'(\d{1,2}):(\d{2})発走',text)
    require(len(posts) == 1, 'INVALID_PAGE')
    post = iso(date+f'T{int(posts[0][0]):02d}:{posts[0][1]}:00+09:00','本文発走')
    require(post == iso(request['scheduled_post_time_jst'],'発走'), 'INVALID_PAGE')
    stamps = re.findall(r'(\d{4})/(\d{1,2})/(\d{1,2})\s+(\d{1,2}):(\d{2})\s*更新',text)
    require(len(stamps) == 1, 'TIME_UNKNOWN')
    y,m,d,h,minute = map(int,stamps[0]); observed = datetime(y,m,d,h,minute,tzinfo=JST)
    require(observed.date().isoformat() == date and observed <= retrieved, 'INVALID_PAGE')
    phases = re.findall(r'(?m)^\s*(中間オッズ|確定オッズ|最終オッズ)\s*$',text)
    require(len(phases) == 1, 'INVALID_PAGE')
    forward = request['mode'] in {'FORWARD','SYNTHETIC'}
    require(not forward or phases[0] == '中間オッズ', 'FINAL_PRICE')
    require(not forward or observed <= iso(request['deadline_at_jst'],'締切') and
            observed <= iso(request['data_cutoff'],'cutoff'), 'INVALID_PAGE')
    lines = [l.strip().strip('|').strip() for l in text.splitlines() if l.strip()]
    cells = []; context = None; bracket = False
    for i,line in enumerate(lines):
        if line.startswith('### 枠連'): bracket = True; context = None; continue
        if line.startswith('### 単勝'): bracket = False; context = None; continue
        if re.fullmatch(r'\d+(?:[－-]\d+)?',line) and i+1 < len(lines) and lines[i+1] == '---':
            context = tuple(map(int,re.split('[－-]',line)))
        if '|' not in line: continue
        row = [c.strip() for c in line.split('|')]
        if kind in {'WIN','PLACE'}:
            if len(row) == 5 and row[0].isdigit() and row[1].isdigit() and int(row[1]) == numbers[0]:
                cells.append(row[3 if kind == 'WIN' else 4])
        elif kind == 'TRIFECTA':
            if len(row) == 2 and re.fullmatch(r'\d+\s*-\s*\d+\s*-\s*\d+',row[0]) and tuple(map(int,re.split(r'\s*-\s*',row[0]))) == numbers:
                cells.append(row[1])
        elif len(row) == 2 and row[0].isdigit() and context:
            if kind == 'BRACKET_QUINELLA' and not bracket: continue
            event = (*context,int(row[0]))
            if (event if kind == 'EXACTA' else tuple(sorted(event))) == numbers:
                cells.append(row[1])
    require(len(cells) == 1, 'INVALID_PAGE')
    ranges = re.fullmatch(r'(\d+(?:\.\d+)?)(?:\s*-\s*(\d+(?:\.\d+)?))?',cells[0])
    require(ranges is not None, 'INVALID_PAGE')
    low = float(ranges.group(1)); high = float(ranges.group(2) or ranges.group(1))
    require(low > 0 and low <= high and (ranges.group(2) is not None) == (kind in {'PLACE','WIDE'}), 'INVALID_PAGE')
    cap = 999.9 if kind in {'WIN','PLACE'} else 9999.9 if kind == 'BRACKET_QUINELLA' else 999999.9 if kind == 'TRIFECTA' else 99999.9
    require(high < cap, 'INVALID_PAGE')
    return {'odds':low, 'observed_at_jst':observed.isoformat(),
            'price_details':{'provider':provider,'basis':'OBSERVED_RANGE_LOWER' if kind in {'PLACE','WIDE'} else 'OBSERVED_EXACT',
                             'lower':low,'upper':high,'publication_phase':phases[0]}}


def capture_result(capture, request):
    require(isinstance(capture,dict) and capture.get('schema_version') == CAPTURE and
            set(capture) <= {'schema_version','source_url','started_at_jst','retrieved_at_jst',
                             'retrieval_kind','tool_reference','error_code','excerpt'}, '取得記録の形式が不正')
    require(capture.get('source_url') in request['source_urls'], '未設定の取得元')
    start = iso(capture.get('started_at_jst'),'開始'); finish = iso(capture.get('retrieved_at_jst'),'閲覧')
    require(start <= finish, '閲覧時刻が逆行')
    kind = capture.get('retrieval_kind')
    require(kind in {'PAGE_TEXT','SYNTHETIC_PAGE_TEXT','SEARCH_SNIPPET','ERROR'}, '取得種別が不正')
    require(isinstance(capture.get('tool_reference'),str) and capture['tool_reference'].strip(), 'ツール出所参照が必要')
    text = capture.get('excerpt')
    require(text is None or isinstance(text,str) and len(text.encode()) <= 8192, '対象の最小本文は8KiBまで')
    error = capture.get('error_code')
    require(error in {None,'ACCESS_DENIED','UNAVAILABLE'}, 'アクセス失敗コードが不正')
    if kind == 'ERROR': require(error is not None and text is None, '失敗記録は価格本文を持たない'); return None,error
    require(error is None and text is not None and text.strip(), '本文取得記録が必要')
    if kind == 'SEARCH_SNIPPET': return None,'SEARCH_SNIPPET'
    require(request['mode'] == 'SYNTHETIC' if kind == 'SYNTHETIC_PAGE_TEXT' else request['mode'] != 'SYNTHETIC',
            '合成本文と実閲覧modeが不一致')
    try:
        return parse_page(text,capture['source_url'],request,finish),None
    except (ValueError,KeyError,TypeError) as exc:
        return None,str(exc) if str(exc) in ERRORS else 'INVALID_PAGE'


def collect(request, captures, directory):
    deadline,cutoff,post = request_times(request)
    require(isinstance(captures,list) and len(captures) <= 4, '試行上限は4')
    require(isinstance(directory,str) and not Path(directory).is_absolute() and '..' not in Path(directory).parts,
            '相対保存先が必要')
    request = copy.deepcopy(request)
    history = {'schema_version':'market-acquisition-v1','transport_schema':TRANSPORT,'request':request,
               'attempts':[],'deadline_at_jst':None if request['mode']=='REPLAY' else request['deadline_at_jst'],
               'stopped_at_jst':None}
    market = {'status':'NOT_ATTEMPTED','decision':'NOT_EVALUATED','reason':'任意市場の閲覧は未試行',
              'odds':None,'expected_value':None,'attempted_at_jst':None,'acquired_at_jst':None,
              'source_ref':None,'acquisition':history}
    raws = {}; counts = {}; last = None; index = 0
    for capture in captures:
        require(market['status'] != 'ACQUIRED' and history['stopped_at_jst'] is None, '成功/締切後の試行を拒否')
        data,error = capture_result(capture,request)
        start=iso(capture['started_at_jst'],'開始'); finish=iso(capture['retrieved_at_jst'],'閲覧')
        require((request['mode']=='REPLAY' or start < deadline) and (last is None or last <= start), '締切後/重複した試行')
        url=capture['source_url']; current=request['source_urls'].index(url)
        require(current >= index, '代替後の主経路再試行を拒否'); index=current
        counts[url]=counts.get(url,0)+1; require(counts[url] <= 2,'取得元の試行上限超過')
        raw=(json.dumps(capture,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode()
        sha=fingerprint(raw); path=(Path(directory)/'captures'/(sha+'.json')).as_posix(); raws[path]=raw
        if request['mode']!='REPLAY' and finish >= deadline:
            data=None;error='DEADLINE_EXCEEDED';history['stopped_at_jst']=capture['retrieved_at_jst']
        a={'attempt_no':len(history['attempts'])+1,'source_ref':url,
           'started_at_jst':capture['started_at_jst'],'finished_at_jst':capture['retrieved_at_jst'],
           'result':'ACQUIRED' if data else 'FAILED','reason':'本文と掲載時刻を照合済み' if data else ERRORS[error],
           'observed_at_jst':data['observed_at_jst'] if data else None,
           'error_code':error,'http_status':None,'raw_http_response':False,
           'capture_ref':{'artifact_path':path,'sha256':sha,'bytes':len(raw),'kind':'CHAT_RETRIEVED_EXCERPT'}}
        history['attempts'].append(a); last=finish
        market['attempted_at_jst']=history['attempts'][0]['started_at_jst']
        if data:
            market.update(status='ACQUIRED',reason='本文の価格を照合済み・期待値は未評価',odds=data['odds'],
                          price_details=data['price_details'],acquired_at_jst=capture['retrieved_at_jst'],source_ref=url)
        else:
            market.update(status='DEADLINE_STOPPED' if history['stopped_at_jst'] else 'FAILED',reason=ERRORS[error])
    payload={'schema_version':'market-analysis-v2','mode':request['mode'],'race_id':request['race_id'],
             'race_date_jst':request['race_date_jst'],'ticket':request['ticket'],
             'data_cutoff':max(cutoff,last or cutoff).isoformat(),'market':market}
    validate_market_payload(payload,payload['data_cutoff'])
    return payload,raws


def verify(root,payload,*,require_forward=True):
    history=payload['market']['acquisition'];request=history['request'];request_times(request)
    require(not require_forward or request['mode'] == payload.get('mode') == 'FORWARD', '合成/REPLAYは正式市場へ登録しない')
    captures=[];directory=None
    for a in history['attempts']:
        require(a.get('http_status') is None and a.get('raw_http_response') is False and 'response_ref' not in a,
                'チャット本文はHTTP原応答ではない')
        ref=a.get('capture_ref');require(isinstance(ref,dict) and ref.get('kind')=='CHAT_RETRIEVED_EXCERPT','本文参照が必要')
        path=safe_path(root,ref.get('artifact_path'));raw=path.read_bytes()
        require(fingerprint(raw)==ref.get('sha256') and len(raw)==ref.get('bytes'),'本文hash/size不一致')
        relative=Path(ref['artifact_path']);require(relative.parent.name=='captures','本文保存位置が不正')
        folder=relative.parent.parent.as_posix()
        require(directory is None or directory==folder,'本文runが混在');directory=folder
        captures.append(json.loads(raw))
    rebuilt,raws=collect(request,captures,directory or 'unused')
    require(rebuilt==payload,'保存本文から再計算した価格/履歴/要求と不一致')


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--request',type=Path,required=True);p.add_argument('--captures',type=Path,required=True)
    p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);p.add_argument('--evidence-dir',required=True)
    a=p.parse_args(argv)
    try:
        request=json.loads(a.request.read_text(encoding='utf-8'));captures=json.loads(a.captures.read_text(encoding='utf-8'))
        now=datetime.now(JST)
        require(all(iso(c.get('retrieved_at_jst'),'実閲覧') <= now for c in captures),'未来の実閲覧時刻を拒否')
        require(request.get('mode')!='FORWARD' or now < iso(request.get('scheduled_post_time_jst'),'発走'), '発走後のFORWARD保存を拒否')
        payload,raws=collect(request,captures,a.evidence_dir)
        from market_acquisition import save
        path=save(a.root,a.evidence_dir,payload,raws)
        print(payload['market']['reason']+'。チャット本文・分析の保存読戻し：'+str(path))
        print('価格確認が未完了でも予想・価格不要推奨は完結できます。独立receiptと日次登録は別途必要です。')
        return 0 if payload['market']['status']=='ACQUIRED' else 1
    except (ValueError,OSError,KeyError,TypeError) as exc:
        print('チャット取得記録を保存できません：'+str(exc));return 1


if __name__=='__main__': raise SystemExit(main())
