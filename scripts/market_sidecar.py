#!/usr/bin/env python3
"""任意市場の保存済み分析を日本語で表示する。価格取得や予想の再作成はしない。"""
import argparse
import json
from pathlib import Path

from cycle04_operations import validate_market_payload


def describe(payload):
    state = validate_market_payload(payload, payload.get('data_cutoff'))
    market = payload['market']
    labels = {'NOT_ATTEMPTED': '価格取得は未試行',
              'FAILED': '価格取得に失敗',
              'DEADLINE_STOPPED': '締切により価格取得を停止',
              'ACQUIRED': '価格取得済み'}
    decisions = {'NOT_EVALUATED': '期待値は未評価',
                 'POSITIVE_EV': '正の期待値を確認',
                 'INSUFFICIENT_EV': '期待値が不足'}
    history = market.get('acquisition')
    return {'取得状態': labels[state], '判断': decisions[market['decision']],
            '理由': market['reason'], '出所': market.get('source_ref'),
            '取得時刻': market.get('acquired_at_jst'),
            '試行履歴': history['attempts'] if history is not None else None,
            '履歴状態': '試行履歴保存済み' if history is not None else '旧形式の試行履歴は未確認'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('path', type=Path)
    args = parser.parse_args(argv)
    try:
        report = describe(json.loads(args.path.read_text(encoding='utf-8')))
        for name in ('取得状態', '判断', '理由', '出所', '取得時刻', '履歴状態'):
            print(f'{name}：{report[name] if report[name] is not None else "未取得"}')
        for attempt in report['試行履歴'] or []:
            result = '取得成功' if attempt['result'] == 'ACQUIRED' else '取得失敗'
            print(f'試行{attempt["attempt_no"]}：{attempt["source_ref"]} / '
                  f'{attempt["started_at_jst"]}〜{attempt["finished_at_jst"]} / '
                  f'{result} / {attempt["reason"]}')
        return 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print('任意市場の保存記録に不整合があります：' + str(exc))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
