#!/usr/bin/env python3
"""既存券比較の確率を読取表示する。校正・確率生成・保存認証は行わない。"""
import argparse
import json
import math
from pathlib import Path

from check_prediction_compliance import ComplianceError

METHODS={'MISSING':'未算定','UNCALIBRATED':'未校正','DISCRETIONARY':'裁量評価','CALIBRATED':'校正済みの区分'}


def require(condition, message):
    if not condition:
        raise ComplianceError(message)


def number(value):
    return type(value) in (int,float) and math.isfinite(value) and 0 <= value <= 1


def validate(item):
    require(isinstance(item,dict), '確率項目が必要')
    method=item.get('probability_method');center=item.get('probability')
    require(method in METHODS, '明示的な確率根拠区分が必要')
    require((method=='MISSING' and center is None) or (method!='MISSING' and number(center)),
            '未算定はnull、算定済みの中心値は0〜1の有限数が必要')
    bounds=item.get('probability_range');lower=item.get('calibrated_lower_bound')
    require(method!='MISSING' or bounds is None and lower is None,
            '未算定にレンジや下限を付けない')
    if bounds is not None:
        require(isinstance(bounds,list) and len(bounds)==2 and all(number(x) for x in bounds)
                and bounds[0] <= center <= bounds[1], '不確実性レンジは中心値を含む0〜1の範囲が必要')
    require(method=='CALIBRATED' or lower is None, '未校正・裁量の値を校正済み下限としない')
    require(method!='CALIBRATED' or bool(item.get('calibration_ref')), '校正区分には既存契約の校正参照が必要')
    if lower is not None:
        require(number(lower) and lower <= center, '校正済み下限は0〜中心値の有限数が必要')
    return method


def percent(value):
    return '未算定' if value is None else format(value*100,'.12g')+'%'


def describe(item):
    method=validate(item);bounds=item.get('probability_range')
    return {'中心値':percent(item.get('probability')),'根拠区分':METHODS[method],
            '不確実性レンジ':'未算定' if bounds is None else '〜'.join(percent(x) for x in bounds),
            'レンジの扱い':'範囲未算定' if bounds is None else
                '裁量の不確実性範囲・統計下限ではない' if method=='DISCRETIONARY' else
                '未校正の不確実性範囲・統計下限ではない' if method=='UNCALIBRATED' else
                '不確実性範囲・レンジ下端を校正済み下限へ代用しない',
            '校正済み下限':percent(item.get('calibrated_lower_bound')),
            '校正参照':item.get('calibration_ref') if method=='CALIBRATED' else None,
            '校正証跡の認証':False}


def describe_comparison(rows, *, horses, frames):
    from cycle04_operations import validate_ticket_comparison
    validate_ticket_comparison(rows,horses=horses,frames=frames)
    labels={'COMPARED':'比較済み','MISSING':'情報不足','NOT_APPLICABLE':'非該当'}
    return [{'券種':r['type'],'比較状態':labels[r['status']],'理由':r['reason'],
             '対象券':[{'組合せ':t.get('frames',t.get('horses')),'確率':describe(t)} for t in r['tickets']]}
            for r in rows]


def describe_production(production):
    """旧来の全頭確率を表示。保存されていない校正区分は推測しない。"""
    from check_prediction_compliance import probability_item
    require(isinstance(production,dict) and isinstance(production.get('probabilities'),list)
            and bool(production['probabilities']), '保存済みProduction確率が必要')
    out=[];seen=set()
    for row in production['probabilities']:
        horse=probability_item(row,'確率表示')
        require(horse not in seen, '同一馬の確率を重複表示しない');seen.add(horse)
        fields=('win_probability','top2_probability','top3_probability')
        require(all(number(row[k]) for k in fields), '中心値は0〜1の有限数が必要')
        out.append({'馬番':horse,'勝率中心':percent(row[fields[0]]),
                    '連対率中心':percent(row[fields[1]]),'3着内率中心':percent(row[fields[2]]),
                    '根拠区分':'既存原本に校正区分の記録なし',
                    '不確実性レンジ':'既存原本に記録なし','校正証跡の認証':False})
    return out


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('path',type=Path,help='既存比較券の確率項目JSON')
    args=parser.parse_args(argv)
    try:
        data=json.loads(args.path.read_text(encoding='utf-8'))
        if isinstance(data,dict) and ('production' in data or 'probabilities' in data):
            rows=describe_production(data.get('production',data))
            print(json.dumps(rows,ensure_ascii=False,indent=2));return 0
        report=describe(data)
        for key,value in report.items():
            print(key+'：'+('未確認' if value is None else '未実施' if value is False else str(value)))
        return 0
    except (ValueError, OSError, TypeError, KeyError) as exc:
        print('確率表示の確認失敗：'+str(exc))
        return 1


if __name__=='__main__':raise SystemExit(main())
