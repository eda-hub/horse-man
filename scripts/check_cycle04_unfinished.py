#!/usr/bin/env python3
"""第4サイクル未完了日の証拠索引を読取専用で検査。正式日別台帳・KPIを生成しない。"""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path


class UnfinishedIndexError(ValueError):
    pass


def require(ok, message):
    if not ok:
        raise UnfinishedIndexError(message)


def evidence_file(root, relative_path):
    require(isinstance(relative_path, str) and relative_path.startswith('docs/validation/'),
            '証拠ファイルはdocs/validation配下を指定する')
    path = Path(relative_path)
    require(not path.is_absolute() and '..' not in path.parts,
            '証拠ファイルのパスが不正')
    full = (root / path).resolve()
    require(full.is_relative_to(root.resolve()) and full.is_file(),
            '証拠ファイルが見つからない: ' + relative_path)
    return full


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def check(root, manifest):
    root = Path(root).resolve()
    doc = load(evidence_file(root, manifest))
    date = doc.get('race_date_jst')
    require(doc.get('schema_version') == 'cycle04-unfinished-day-index-v1' and
            date and re.fullmatch(r'\d{4}-\d{2}-\d{2}', date),
            '未完了索引の版・日付が不正')
    require(doc.get('mode') == 'RETROSPECTIVE_REFERENCE_ONLY' and
            doc.get('formal_kpi_eligibility') == 'NEVER_INFER_FROM_THIS_INDEX' and
            doc.get('official_scope_status') == 'NOT_REGISTERED_BEFORE_RACE' and
            doc.get('daily_ledger_status') == 'NOT_CREATED' and
            doc.get('initial_predictions_status') == 'NOT_INDEPENDENTLY_FIXED',
            '事後索引を正式な日別台帳や前向き適格として流用することは禁止')
    expected_intent = f'docs/validation/persistence-intents/{date}/morning.json'
    require(doc.get('source_intent_path') == expected_intent, '初回宣言原本との紐づけ不一致')
    intent = load(evidence_file(root, expected_intent))
    require(intent.get('schema_version') == 'prediction-persistence-intent-v1' and
            intent.get('race_date_jst') == date, '初回宣言の形式・日付不一致')
    expected = intent.get('required_race_ids')
    races = doc.get('races')
    require(isinstance(expected, list) and len(set(expected)) == len(expected) and
            isinstance(races, list) and len(races) == len(expected) and
            [row.get('race_id') for row in races] == expected,
            '事後索引は当時宣言した全対象・順序と一致すること')
    evidence_file(root, doc.get('screening_path'))
    counts = {'PRE_RACE_BODY_ARCHIVED_NOT_CYCLE04_ACCEPTED': 0,
              'AFTER_POST_CHAT_PRESERVATION_ONLY': 0,
              'NOT_PERSISTED': 0}
    recommendation_counts = {}
    for row in races:
        race = row['race_id']
        pred = row.get('prediction')
        rec = row.get('recommendation')
        gaps = row.get('gaps')
        require(isinstance(pred, dict) and isinstance(rec, dict) and
                isinstance(gaps, list) and
                'FORMAL_OFFICIAL_SCOPE_NOT_REGISTERED_BEFORE_POST' in gaps and
                'CYCLE04_DAY_LEDGER_NOT_REGISTERED' in gaps and
                'INITIAL_PREDICTION_NOT_INDEPENDENTLY_FIXED' in gaps,
                race + ': 正式工程の欠落を隠してはいけない')
        status = pred.get('status')
        require(status in counts, race + ': 不明なPrediction状態')
        counts[status] += 1
        if status == 'PRE_RACE_BODY_ARCHIVED_NOT_CYCLE04_ACCEPTED':
            body = evidence_file(root, pred.get('path'))
            payload = load(body)
            require(payload.get('race_id') == race and payload.get('phase') == 'FINAL' and
                    payload.get('mode') == 'FORWARD', race + ': 予想原本ID不一致')
            fix = load(evidence_file(root, pred.get('fix_path')))
            require(fix.get('snapshot_id') == payload.get('snapshot_id') and
                    fix.get('artifact_path') == pred['path'] and
                    fix.get('fixed_content_sha256') ==
                    hashlib.sha256(body.read_bytes()).hexdigest(),
                    race + ': 予想原本/FIXのハッシュ不一致')
            gate = load(evidence_file(root, pred.get('gate_path')))
            require(gate.get('race_id') == race and
                    gate.get('kpi_eligibility', {}).get('production') != 'ELIGIBLE',
                    race + ': 事後索引から本番適格の宣言は禁止')
        elif status == 'AFTER_POST_CHAT_PRESERVATION_ONLY':
            require(pred.get('path', '').startswith('docs/validation/preservation/'),
                    race + ': 事後保全の保存場所不一致')
            evidence_file(root, pred.get('path'))
        else:
            require('path' not in pred, race + ': 未保存の原本参照は禁止')
        state = rec.get('status')
        require(state in {'NOT_PERSISTED', 'UNSEALED_PRE_RACE_CANDIDATE',
                          'UNSEALED_NO_RECOMMENDATION',
                          'PRE_RACE_RECOMMENDATION_NOT_CERTIFIED'},
                race + ': 不明な推奨状態')
        recommendation_counts[state] = recommendation_counts.get(state, 0) + 1
        if state != 'NOT_PERSISTED':
            rf = evidence_file(root, rec.get('path'))
            if rf.suffix == '.json':
                record = load(rf)
                require(record.get('race_id') == race, race + ': 推奨と対象レース不一致')
                if state == 'PRE_RACE_RECOMMENDATION_NOT_CERTIFIED':
                    require(record.get('schema_version') == 'recommendation-snapshot-v1' and
                            record.get('status') == 'RECOMMENDED',
                            race + ': 正式推奨の保存形式不一致')
                else:
                    require(state == 'UNSEALED_NO_RECOMMENDATION' and
                            record.get('status') == 'NO_RECOMMENDATION',
                            race + ': 未封印見送りの参照不一致')
            else:
                require(state == 'UNSEALED_PRE_RACE_CANDIDATE',
                        race + ': 非JSON推奨を正式原本へ接続しない')
        else:
            require('path' not in rec, race + ': 未作成推奨の参照は禁止')
    # The two unsealed decisions are review references, never formal v1
    # recommendations. Verify their original sources and classifications.
    unsealed_path = f'docs/validation/reconciliations/{date}-unsealed-recommendations.json'
    require(doc.get('unsealed_decision_path') == unsealed_path,
            '未封印判断ファイルの参照先が未登録')
    unsealed = load(evidence_file(root, unsealed_path))
    decisions = unsealed.get('decisions')
    expected_unsealed = {
        row['race_id']: row['recommendation']['path'] for row in races
        if row['recommendation']['status'].startswith('UNSEALED_')
    }
    require(unsealed.get('schema_version') == 'cycle04-unsealed-recommendation-reference-v1' and
            unsealed.get('race_date_jst') == date and
            unsealed.get('formal_forward_eligibility') == 'INELIGIBLE' and
            isinstance(decisions, list) and len(decisions) == len(expected_unsealed) and
            {item.get('race_id'): item.get('source_path') for item in decisions} == expected_unsealed,
            '未封印判断と全日索引の参照対応が不一致')
    for item in decisions:
        require(item.get('selected_for_valuation') is False and
                item.get('status', '').startswith('UNSEALED_') and
                isinstance(item.get('unmet'), list) and item['unmet'],
                '未封印判断を正式推奨へ昇格してはならない')
        evidence_file(root, item.get('source_path'))
    return {
        'schema_version': 'cycle04-unfinished-day-audit-v1',
        'race_date_jst': date,
        'verified_race_count': len(races),
        'prediction_states': counts,
        'recommendation_states': recommendation_counts,
        'official_ledger_created': False,
        'formal_kpi_certified': False,
        'suitable_for': '参照資料として回顧準備と不足管理のみ。正式集計の代替不可',
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('.'))
    parser.add_argument('--manifest', default='docs/validation/reconciliations/2026-10-17-day-index.json')
    args = parser.parse_args()
    try:
        result = check(args.root, args.manifest)
    except (UnfinishedIndexError, OSError, ValueError, KeyError, TypeError) as exc:
        print('UNFINISHED_DAY_INDEX_INVALID: ' + str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
