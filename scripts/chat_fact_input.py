#!/usr/bin/env python3
"""確認済み本文の注釈を既存全頭入力へ変換する。値の推測はしない。"""
import argparse
import copy
import json
from pathlib import Path

from chat_fact_capture import verify
from check_prediction_compliance import iso
from cycle04_operations import require, validate_inputs


def quote(bundle, ref):
    require(isinstance(ref, dict), 'explicit source quotation required')
    rows = [c for c in bundle['captures'] if c['capture_id'] == ref.get('capture_id')]
    require(len(rows) == 1 and rows[0]['usable_as_observed_fact'], 'usable capture reference required')
    c = rows[0]; start, end = ref.get('start'), ref.get('end')
    require(type(start) is int and type(end) is int and 0 <= start < end <= len(c['text']),
            'quotation offsets out of range')
    require(isinstance(ref.get('quote'), str) and c['text'][start:end] == ref['quote'],
            'quotation differs from saved text')
    return c


def convert(bundle, annotations, readback_at):
    bundle = verify(bundle); req = bundle['request']
    require(req['purpose'] == 'INPUT', 'input acquisition request required')
    require(isinstance(annotations, dict) and set(annotations) == {'body_weight', 'recent_five_runs'},
            'both all-horse input fields required')
    readback = iso(readback_at, 'input readback')
    require(readback <= iso(req['data_cutoff'], 'cutoff'), 'input readback after cutoff')
    data = {'schema_version': 'race-input-coverage-v1', 'race_id': req['race_id'],
            'data_cutoff': req['data_cutoff'], 'horse_numbers': copy.deepcopy(req['horse_numbers'])}
    bindings = []
    for field in ('body_weight', 'recent_five_runs'):
        rows = annotations[field]
        require(isinstance(rows, list) and len(rows) == len(req['horse_numbers']) and
                {r.get('horse_no') for r in rows} == set(req['horse_numbers']),
                'annotation all-horse scope mismatch')
        output = []
        for index, original in enumerate(rows):
            require(isinstance(original, dict), 'annotation object required')
            row = copy.deepcopy(original); references = row.pop('quotations', None)
            state = row.get('status')
            require(state in {'ACQUIRED', 'MISSING', 'NOT_APPLICABLE'}, 'explicit input state required')
            if state != 'MISSING':
                require(isinstance(references, list) and references, 'acquired/debut quotations required')
                sources = [quote(bundle, ref) for ref in references]
                # The supplying origin remains explicit. Additional sources must not
                # silently replace the primary provider/time metadata.
                c = sources[0]
                require(all(s['origin_group'] == c['origin_group'] for s in sources),
                        'one row must use one upstream origin; preserve conflicts separately')
                for ref in references:
                    bindings.append({'field': field, 'horse_no': row['horse_no'],
                                     'row_index': index, 'quotation': copy.deepcopy(ref)})
                row.update(source_ref=c['source_url'], provider=c['provider'],
                           observed_at_jst=c['source_updated_at_jst'],
                           acquired_at_jst=c['read_finished_at_jst'], readback_at_jst=readback_at)
                require(iso(c['read_finished_at_jst'], 'retrieval') <= readback,
                        'readback before retrieval')
            else:
                require(not references and row.get('value') is None, 'missing input cannot claim extracted value')
            output.append(row)
        data[field] = output
    validation = validate_inputs(data, race_id=req['race_id'], horses=req['horse_numbers'],
                                 cutoff=req['data_cutoff'], post=req['scheduled_post_time_jst'])
    return {'schema_version': 'chat-input-conversion-v1', 'input': data, 'bindings': bindings,
            'coverage': validation, 'formal_kpi_certified': False,
            'semantic_extraction_verified': False,
            'note': '引用位置と構造を確認。値と引用の対応・独立artifact/receiptは別途検査。'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture', type=Path, required=True)
    parser.add_argument('--annotations', type=Path, required=True)
    parser.add_argument('--readback-at', required=True)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(convert(json.loads(args.capture.read_text()),
                                 json.loads(args.annotations.read_text()), args.readback_at),
                         ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print('全頭入力の変換不合格：' + str(exc))
        return 1


if __name__ == '__main__': raise SystemExit(main())
