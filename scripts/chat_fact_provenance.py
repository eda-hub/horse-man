#!/usr/bin/env python3
"""引用・全頭入力・保存原本/receiptの対応を読取照合する。"""
import argparse
import copy
import json
import re
from pathlib import Path

from chat_fact_capture import verify
from chat_fact_input import convert, quote
from check_prediction_compliance import iso
from cycle04_operations import require, verified_artifact


def scalar(value, text):
    require(type(value) in {int, float, str}, 'only explicit scalar facts can be extracted')
    if type(value) in {int, float}:
        require(re.search(r'(?<![\d.])' + re.escape(str(value)) + r'(?![\d.])', text),
                'numeric fact does not match quoted text')
    else:
        require(bool(value.strip()) and value in text, 'text fact does not match quoted text')


def resolve(value, pointer):
    require(isinstance(pointer, str) and (pointer == '' or pointer.startswith('/')),
            'relative value pointer required')
    for key in pointer.split('/')[1:]:
        key = key.replace('~1', '/').replace('~0', '~')
        value = value[int(key)] if isinstance(value, list) else value[key]
    return value


def consistency(bundle, conversion):
    bundle = verify(bundle); req = bundle['request']
    require(isinstance(conversion, dict) and conversion.get('schema_version') == 'chat-input-conversion-v1',
            'explicit input conversion required')
    data = conversion['input']; bindings = conversion.get('bindings')
    require(isinstance(bindings, list), 'conversion bindings required')
    annotations = {field: copy.deepcopy(data[field]) for field in ('body_weight', 'recent_five_runs')}
    readbacks = set()
    for field, rows in annotations.items():
        for index, row in enumerate(rows):
            refs = []
            for binding in bindings:
                if binding.get('field') == field and binding.get('row_index') == index:
                    require(binding.get('horse_no') == row['horse_no'], 'binding horse mismatch')
                    ref = binding.get('quotation'); quote(bundle, ref)
                    require('\n' not in ref['quote'].strip() and '\r' not in ref['quote'].strip(),
                            'one fact quotation must not join multiple horse rows')
                    marked_horses = {int(x) for x in re.findall(r'(?<!\d)(\d+)番', ref['quote'])}
                    require(not marked_horses or marked_horses == {row['horse_no']},
                            'quotation mixes different horse identities')
                    require(re.search(r'(?<!\d)' + str(row['horse_no']) + r'(?:番|\s)', ref['quote']),
                            'quoted horse identity missing')
                    refs.append(copy.deepcopy(ref))
            if row['status'] == 'MISSING':
                require(not refs, 'missing input cannot claim extracted facts')
            else:
                require(refs, 'fact quotations missing')
                pointers = {r.get('value_pointer', '') for r in refs}
                if row['status'] == 'NOT_APPLICABLE':
                    require(row.get('prior_start_count') == 0 and row.get('value') is None,
                            'debut evidence contradicts input')
                    require(any('初出走' in r['quote'] for r in refs), 'explicit debut quotation required')
                elif field == 'body_weight':
                    require('' in pointers, 'weight value quotation missing')
                    for ref in refs: scalar(row['value'], ref['quote'])
                else:
                    needed = set()
                    for n, run in enumerate(row['value']):
                        needed |= {f'/{n}/race_at_jst', f'/{n}/class'}
                        if run['opponent_level']['status'] == 'ACQUIRED':
                            needed.add(f'/{n}/opponent_level/value')
                    require(needed <= pointers, 'recent-run fact quotations incomplete')
                    for ref in refs:
                        pointer = ref.get('value_pointer', '')
                        scalar(resolve(row['value'], pointer), ref['quote'])
                        run = row['value'][int(pointer.split('/')[1])]
                        source = quote(bundle, ref)
                        require(run.get('source_ref') == source['source_url'],
                                'recent run source differs from its quotation')
                        if pointer.endswith('/opponent_level/value'):
                            opponent = run['opponent_level']
                            require(opponent.get('source_ref') == source['source_url'] and
                                    iso(opponent['observed_at_jst'], 'opponent observed') <=
                                    iso(source['source_updated_at_jst'], 'source observed'),
                                    'opponent evidence source/time mismatch')
                readbacks.add(row['readback_at_jst'])
                row['quotations'] = refs
    require(len(readbacks) <= 1, 'one input conversion must have one recorded readback time')
    generated = convert(bundle, annotations, next(iter(readbacks), req['data_cutoff']))
    require(generated == conversion, 'conversion source/coverage/binding mismatch')
    return {'extraction_consistency_verified': True, 'formal_kpi_certified': False,
            'origin_authenticity_certified': False,
            'input': copy.deepcopy(data), 'coverage': copy.deepcopy(conversion['coverage'])}


def verify_saved(root, capture_ref, conversion_ref, post):
    bundle, capture_receipt = verified_artifact(root, capture_ref, post)
    conversion, input_receipt = verified_artifact(root, conversion_ref, post)
    require(bundle['request']['scheduled_post_time_jst'] == post, 'capture post mismatch')
    req = bundle['request']; cutoff = iso(req['data_cutoff'], 'cutoff')
    require(iso(bundle['recorded_at'], 'capture recorded') <=
            iso(capture_receipt['persist_verified_at_jst'], 'capture persisted'),
            'capture receipt predates recorded content')
    require(iso(capture_receipt['receipt_verified_at_jst'], 'capture readback') <=
            iso(input_receipt['persist_verified_at_jst'], 'input persisted') <=
            iso(input_receipt['receipt_verified_at_jst'], 'input readback') <= cutoff,
            'input/capture independent receipt order or cutoff mismatch')
    report = consistency(bundle, conversion)
    for field in ('body_weight', 'recent_five_runs'):
        for row in report['input'][field]:
            if row['status'] != 'MISSING':
                require(iso(capture_receipt['receipt_verified_at_jst'], 'capture readback') <=
                        iso(row['readback_at_jst'], 'row readback') <=
                        iso(input_receipt['receipt_verified_at_jst'], 'input readback'),
                        'row readback not bounded by independent receipts')
    report.update(capture_ref=copy.deepcopy(capture_ref), conversion_ref=copy.deepcopy(conversion_ref),
                  independent_receipts_verified=True)
    return report


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument('--capture-ref', type=Path, required=True)
    p.add_argument('--conversion-ref', type=Path, required=True)
    p.add_argument('--post', required=True)
    args = p.parse_args(argv)
    try:
        print(json.dumps(verify_saved(args.root, json.loads(args.capture_ref.read_text()),
                                      json.loads(args.conversion_ref.read_text()), args.post),
                         ensure_ascii=False, indent=2)); return 0
    except (ValueError, OSError, KeyError, TypeError, IndexError) as exc:
        print('入力根拠の照合不合格：' + str(exc)); return 1


if __name__ == '__main__': raise SystemExit(main())
