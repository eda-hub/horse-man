#!/usr/bin/env python3
"""確認済み公式本文の注釈から全頭結果を独立正規化する。"""
import argparse
import copy
import json
import re
from pathlib import Path

from chat_fact_capture import verify
from check_prediction_compliance import iso
from cycle04_operations import require, validate_official_result


def result_quote(bundle, ref):
    require(isinstance(ref, dict), 'explicit result quotation required')
    rows = [c for c in bundle['captures'] if c['capture_id'] == ref.get('capture_id')]
    require(len(rows) == 1, 'unique result capture reference required')
    c = rows[0]
    require(c['provider'] == 'OFFICIAL' and c['retrieval_kind'] in {'PAGE_TEXT','SYNTHETIC_PAGE_TEXT'},
            'official result page text required')
    req = bundle['request']
    require(iso(c['read_started_at_jst'], 'result read start') >=
            iso(req['scheduled_post_time_jst'], 'post') and
            iso(c['read_finished_at_jst'], 'result read finish') <= iso(req['data_cutoff'], 'cutoff'),
            'result text outside post-race acquisition window')
    start, end = ref.get('start'), ref.get('end')
    require(type(start) is int and type(end) is int and 0 <= start < end <= len(c['text'])
            and c['text'][start:end] == ref.get('quote'), 'result quotation mismatch')
    return c


def quoted_row(text):
    """Saved JRA pipe-row fields, never image/link indices, identify the horse."""
    line = re.sub(r'^L\d+:\s*', '', text.strip())
    cells = [c.strip() for c in line.split('|')]
    if len(cells) < 5:
        return None
    require(re.fullmatch(r'[1-8]', cells[1]) is not None or
            re.fullmatch(r'【\d+†Image: 枠[1-8][^】]*】', cells[1]) is not None,
            'result frame column invalid')
    require(re.fullmatch(r'[1-9]\d*', cells[2]) is not None, 'result horse-number column invalid')
    rank = cells[0]
    if re.fullmatch(r'[1-9]\d*', rank):
        return int(cells[2]), 'FINISHED', int(rank)
    if rank in {'取消', '除外'}:
        return int(cells[2]), 'SCRATCHED', None
    if rank in {'中止', '競走中止', '失格'}:
        return int(cells[2]), 'NON_FINISH', None
    require(False, 'unconfirmed official table row')


def normalize_result(bundle, annotation):
    bundle = verify(bundle); req = bundle['request']
    require(req['purpose'] == 'RESULT', 'post-race result request required')
    require(isinstance(annotation, dict) and
            set(annotation) == {'rows','confirmation','place_basis','race_identity'}, 'explicit result annotations required')
    confirmed = result_quote(bundle, annotation['confirmation'])
    require(not any(word in annotation['confirmation']['quote'] for word in ('未確定','暫定','訂正待ち')) and
            any(word in annotation['confirmation']['quote'] for word in ('確定','払戻金')),
            'result confirmation quotation missing')
    identity=result_quote(bundle,annotation['race_identity'])
    heading=annotation['race_identity']['quote']
    match=re.fullmatch(r'(?:'+re.escape(req['race_date_jst'])+'|'+req['race_date_jst'].replace('-','')+
                       r')-(TOK|TOKYO|KYO|KYOTO|NII|NIIGATA)-(\d{2})',req['race_id'])
    require(match is not None,'unsupported race identity requires explicit parser review')
    venue={'TOK':'東京','TOKYO':'東京','KYO':'京都','KYOTO':'京都','NII':'新潟','NIIGATA':'新潟'}[match[1]]
    y,m,d=map(int,req['race_date_jst'].split('-'))
    require(re.search(str(y)+r'年\s*0?'+str(m)+r'月\s*0?'+str(d)+r'日',heading) is not None
            and venue in heading,'official result heading date/venue mismatch')
    numbers={int(n) for n in re.findall(r'(?<!\d)(\d+)\s*(?:レース|R\b)',heading)}
    require(numbers=={int(match[2])},'official result heading race number mismatch')
    post=iso(req['scheduled_post_time_jst'],'post')
    require(re.search(r'(?<!\d)0?'+str(post.hour)+r'(?:時\s*0?'+str(post.minute)+r'分|:'+f'{post.minute:02d}'+r')(?!\d)',heading) is not None,
            'official result heading scheduled post mismatch')
    require(identity['capture_id']==confirmed['capture_id'],'confirmation must belong to the identified result page')
    rows = annotation['rows']
    require(isinstance(rows, list) and len(rows) == len(req['horse_numbers']) and
            {r.get('horse_no') for r in rows} == set(req['horse_numbers']),
            'complete official result horse scope required')
    positions, scratch, non_finish = {}, [], []
    sources = [confirmed,identity]
    for row in rows:
        require(isinstance(row, dict) and
                set(row) == {'horse_no','status','finish_position','quotation'},
                'result row fields invalid; horse names/icons are not copied into the result')
        source = result_quote(bundle, row['quotation']); sources.append(source)
        require(source['capture_id']==identity['capture_id'],'rows must belong to the identified official result page')
        text = row['quotation']['quote']; horse = row['horse_no']
        require('\n' not in text.strip() and '\r' not in text.strip(), 'one quoted result row required')
        state, position = row['status'], row['finish_position']
        table = quoted_row(text) if '|' in text else None
        if table is not None:
            require(table == (horse, state, position), 'official table row differs from annotation')
            prefix = source['text'][:row['quotation']['start']]
            require(re.search(r'着順\s*\|.*馬', prefix) is not None and
                    re.search(r'番\s*\|\s*馬名', prefix) is not None,
                    'official result table header missing')
        else:
            marked = {int(h) for h in re.findall(r'(?<!\d)(\d+)番', text)}
            require(marked == {horse}, 'result quotation mixes horse identities')
        if state == 'FINISHED':
            require(type(position) is int and position > 0 and
                    (table is not None or re.search(r'(?<!\d)'+str(position)+r'着', text)), 'finish position quotation mismatch')
            positions.setdefault(position, []).append(horse)
        elif state == 'SCRATCHED':
            require(position is None and any(w in text for w in ('取消','除外')), 'scratch quotation mismatch')
            scratch.append(horse)
        elif state == 'NON_FINISH':
            require(position is None and (table is not None or any(w in text for w in ('競走中止','失格'))), 'non-finish quotation mismatch')
            non_finish.append(horse)
        else:
            require(False, 'unconfirmed result row state')
    groups, expected = [], 1
    for position in sorted(positions):
        require(position == expected, 'official finish positions have a gap/inconsistent tie')
        group = sorted(positions[position]); groups.append(group); expected += len(group)
    basis = annotation['place_basis']
    require(isinstance(basis, dict) and set(basis) == {'kind','value','quotation'}, 'place basis required')
    sources.append(result_quote(bundle, basis['quotation']))
    value, text = basis['value'], basis['quotation']['quote']
    if basis['kind'] == 'OFFICIAL_PLACE_PLACES':
        require(type(value) is int and value in (2,3) and '複勝' in text and
                str(value)+'着' in text, 'explicit official place coverage required')
        places = value
    elif basis['kind'] == 'OFFICIAL_SALES_START_COUNT':
        counts = {int(n) for n in re.findall(r'(?<!\d)(\d+)頭', text)}
        require(type(value) is int and value >= 5 and '発売開始' in text and counts == {value},
                'verified sales-start field size required; current starters are not a substitute')
        places = 2 if value <= 7 else 3
    else:
        require(False, 'place coverage basis unknown')
    require(len({s['origin_group'] for s in sources}) == 1, 'preserve source conflicts separately')
    finished_at = max((s['read_finished_at_jst'] for s in sources), key=lambda t: iso(t,'result retrieved'))
    result = {'race_id':req['race_id'], 'race_date_jst':req['race_date_jst'], 'status':'OFFICIAL',
              'source_url':confirmed['source_url'],'retrieved_at_jst':finished_at,
              'finish_groups':groups,'scratched_horses':sorted(scratch),
              'non_finishers':sorted(non_finish),'place_places':places}
    validate_official_result(result,race=req['race_id'],date=req['race_date_jst'],
                            post=req['scheduled_post_time_jst'],horses=req['horse_numbers'])
    modes = {s['mode'] for s in sources}
    mode = 'SYNTHETIC' if 'SYNTHETIC' in modes else 'REPLAY' if 'REPLAY' in modes else 'FORWARD'
    return {'schema_version':'chat-result-conversion-v1','result':result,
            'annotation':copy.deepcopy(annotation),'mode':mode,
            'publication_time_unknown':any(s.get('source_updated_at_jst') is None for s in sources),
            'formal_kpi_certified':False,'origin_authenticity_certified':False,
            'raw_http_bytes_verified':False}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--capture',type=Path,required=True)
    p.add_argument('--annotations',type=Path,required=True)
    args=p.parse_args(argv)
    try:
        print(json.dumps(normalize_result(json.loads(args.capture.read_text()),
                                         json.loads(args.annotations.read_text())),ensure_ascii=False,indent=2))
        return 0
    except (ValueError,OSError,KeyError,TypeError) as exc:
        print('公式結果の本文変換不合格：'+str(exc));return 1


if __name__=='__main__':raise SystemExit(main())
