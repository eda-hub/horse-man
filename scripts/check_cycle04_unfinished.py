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


def preserved_candidate(source, kind):
    """原文の候補をそのまま抽出。曖昧な自由文や推定で補正しない。"""
    if kind == 'EARLIER_CHAT_CANDIDATE_PRESERVATION':
        # 京都8R: - **ワイド 3 アンムート－6 カレンハウ、1点**。
        pattern = (r'^-\s*\*\*ワイド\s+([1-9]\d*)\s+[^\n－]+'
                   r'－([1-9]\d*)\s+[^\n、]+、([1-9]\d*)点\*\*。')
    elif kind == 'AFTER_POST_CHAT_CANDIDATE_PRESERVATION':
        # 京都10R: - チャットでの参考購入候補: ワイド 6－7、1点。
        pattern = (r'^-\s*チャットでの参考購入候補:\s*ワイド\s+'
                   r'([1-9]\d*)－([1-9]\d*)、([1-9]\d*)点。')
    else:
        raise UnfinishedIndexError('未対応の参考候補出所形式: ' + str(kind))
    matches = re.findall(pattern, source, re.M)
    require(len(matches) == 1, '原文に参考買い目の一意な記載がない')
    a, b, points = (int(x) for x in matches[0])
    require(a != b and points == 1, '原文の参考買い目の重複・点数不正')
    return {'type': 'WIDE', 'horse_numbers': [a, b], 'points': points}


def verify_unsealed_decision(root, item, row):
    race = row['race_id']
    source_path = item.get('source_path')
    require(item.get('status', '').startswith('UNSEALED_') and
            item.get('selected_for_valuation') is False and
            isinstance(item.get('unmet'), list) and item['unmet'],
            race + ': 未封印判断を正式推奨へ昇格してはならない')
    source = evidence_file(root, source_path)
    require(re.fullmatch(r'[0-9a-f]{64}', item.get('source_sha256', '')) and
            hashlib.sha256(source.read_bytes()).hexdigest() == item['source_sha256'],
            race + ': 原文SHA-256が不一致')
    kind = item.get('source_kind')
    candidates = {
        'EARLIER_CHAT_CANDIDATE_PRESERVATION':
            ('UNSEALED_RECOMMENDATION_CANDIDATE', 'UNSEALED_PRE_RACE_CANDIDATE'),
        'AFTER_POST_CHAT_CANDIDATE_PRESERVATION':
            ('UNSEALED_LATE_PRESERVATION_CANDIDATE', 'UNSEALED_LATE_PRESERVATION_CANDIDATE'),
        'NON_CANONICAL_NO_RECOMMENDATION_SNAPSHOT':
            ('UNSEALED_NO_RECOMMENDATION', 'UNSEALED_NO_RECOMMENDATION'),
    }
    require(kind in candidates and
            item['status'] == candidates[kind][0] and
            row['recommendation']['status'] == candidates[kind][1],
            race + ': 出所と未封印種別が不一致')
    claimed = item.get('recorded_candidate')
    require(isinstance(claimed, dict) and
            claimed.get('official_recommendation') is False,
            race + ': 未封印参考買い目を正式推奨として扱っている')
    if kind == 'NON_CANONICAL_NO_RECOMMENDATION_SNAPSHOT':
        payload = load(source)
        require(payload.get('race_id') == race and
                payload.get('status') == 'NO_RECOMMENDATION' and
                payload.get('formal_recommendation_status') == 'UNSEALED_LOCAL_FALLBACK_ONLY' and
                item.get('reason') == payload.get('reason') and
                payload.get('purchase_executed') is False,
                race + ': 見送り判断と原文が不一致')
        studies = payload.get('candidates_for_study')
        require(isinstance(studies, list) and len(studies) == 1 and
                studies[0].get('official_recommendation') is False,
                race + ': 見送り時の参考候補が不正')
        expected = {'type': studies[0].get('type'),
                    'horse_numbers': studies[0].get('horse_numbers'),
                    'points': studies[0].get('unique_points'),
                    'official_recommendation': False}
    else:
        expected = preserved_candidate(source.read_text(encoding='utf-8'), kind)
        expected['official_recommendation'] = False
    require(claimed == expected,
            race + ': 転記した券種・馬番・点数が原文と不一致')



# Immutable reference pins for the four *existing* October 17 errors. These
# do not certify any missing recommendation or silence recommendation.py --audit.
HISTORICAL_RECOMMENDATION_DEBTS = {
    "NONCANONICAL_NIIGATA_11": (
        "2026-10-17-NIIGATA-11", "UNSEALED_NO_RECOMMENDATION",
        "docs/validation/recommendations/2026-10-17/20261017-NIIGATA-11-REC-S01.json",
        "c28e1749d05b17f69f3c60fbb1a456b6d1ce95916bb9a2aa1a6069ca56afb813",
        "unregistered recommendation snapshot: docs/validation/recommendations/2026-10-17/20261017-NIIGATA-11-REC-S01.json",
    ),
    "DECLARED_TOKYO_09_NOT_SAVED": (
        "2026-10-17-TOKYO-09", "NOT_PERSISTED",
        "docs/validation/persistence-intents/2026-10-17/tokyo-09-final.json",
        "46e23e5b362f1a45cb4d353c91c2e47510a7243c408a1d10d7e6c83452075f14",
        "docs/validation/persistence-intents/2026-10-17/tokyo-09-final.json: declared recommendation intent missing or duplicated",
    ),
    "NIIGATA_11_RECOMMENDATION_GATE_MISSING": (
        "2026-10-17-NIIGATA-11", "UNSEALED_NO_RECOMMENDATION",
        "docs/validation/execution-gates/2026-10-17/2026-10-17-NIIGATA-11.json",
        "47b24050fee0b75d40d5fa0575b45625b59705b2a9c2cdea4434f2f4699354ae",
        "missing recommendation gate for docs/validation/execution-gates/2026-10-17/2026-10-17-NIIGATA-11.json",
    ),
    "KYOTO_08_RECOMMENDATION_GATE_MISSING": (
        "2026-10-17-KYOTO-08", "UNSEALED_PRE_RACE_CANDIDATE",
        "docs/validation/execution-gates/2026-10-17/2026-10-17-KYOTO-08.json",
        "08f00061134e8b3ce12438b37dbe220601a57f32dafe8e8f7b63b3b0096cda16",
        "missing recommendation gate for docs/validation/execution-gates/2026-10-17/2026-10-17-KYOTO-08.json",
    ),
}


def verify_historical_recommendation_debts(root, date, day_index):
    """Only verifies archived deficits and their provenance; does not waive them."""
    location = f'docs/validation/reconciliations/{date}-recommendation-historical-debts.json'
    require(day_index.get('recommendation_historical_debt_path') == location,
            '歴史的推奨の欠落台帳に接続されていない')
    record = load(evidence_file(root, location))
    require(record.get('schema_version') ==
            'recommendation-historical-debt-exclusions-v1' and
            record.get('race_date_jst') == date and
            record.get('mode') == 'CI_ONLY_HISTORICAL_DEBT_ACCEPTANCE' and
            record.get('count_expected') == 4 and
            record.get('formal_kpi_eligibility') == 'INELIGIBLE' and
            record.get('official_day_scope') == 'UNREGISTERED',
            '既存の正式推奨不足を認証済みとして扱うことは禁止')
    items = record.get('items')
    require(isinstance(items, list) and len(items) == 4 and
            {item.get('code') for item in items} ==
            set(HISTORICAL_RECOMMENDATION_DEBTS),
            '既知の推奨不足は4項目のみ')
    known_races = {row['race_id']: row for row in day_index['races']}
    for entry in items:
        code = entry['code']
        rid, state, source_path, source_hash, error = HISTORICAL_RECOMMENDATION_DEBTS[code]
        require(entry.get('race_id') == rid and
                entry.get('recommendation_state') == state and
                entry.get('source_path') == source_path and
                entry.get('source_sha256') == source_hash and
                entry.get('expected_error') == error and
                isinstance(entry.get('note'), str) and bool(entry['note']),
                '推奨不足の出所または指摘内容を変更してはいけない: ' + code)
        require(known_races[rid]['recommendation']['status'] == state,
                '推奨の未完了状態を正式認証へ昇格できない: ' + code)
        actual = hashlib.sha256(evidence_file(root, source_path).read_bytes()).hexdigest()
        require(actual == source_hash, '推奨不足の原本SHA-256不一致: ' + code)
    require(all(known_races[r]['recommendation']['status'] !=
                'PRE_RACE_RECOMMENDATION_NOT_CERTIFIED'
                for r in ('2026-10-17-KYOTO-08',
                          '2026-10-17-TOKYO-09',
                          '2026-10-17-NIIGATA-11')),
            '未封印推奨を事後に正式ゲートへ接続してはならない')
    require(not (root / 'docs/validation/recommendation-gates/2026-10-17/'
                 '2026-10-17-KYOTO-08.json').exists() and
            not (root / 'docs/validation/recommendation-gates/2026-10-17/'
                 '2026-10-17-NIIGATA-11.json').exists(),
            '存在しなかった過去の独立推奨ゲートを後付けしてはならない')
    return len(items)


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
                          'UNSEALED_LATE_PRESERVATION_CANDIDATE',
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
                require(state in {'UNSEALED_PRE_RACE_CANDIDATE',
                                  'UNSEALED_LATE_PRESERVATION_CANDIDATE'},
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
    indexed = {row['race_id']: row for row in races}
    require(len({item.get('race_id') for item in decisions}) == len(decisions),
            '未封印判断のレースが重複')
    for item in decisions:
        verify_unsealed_decision(root, item, indexed[item['race_id']])
    historical_debt_count = verify_historical_recommendation_debts(root, date, doc)
    return {
        'schema_version': 'cycle04-unfinished-day-audit-v1',
        'race_date_jst': date,
        'verified_race_count': len(races),
        'prediction_states': counts,
        'recommendation_states': recommendation_counts,
        'official_ledger_created': False,
        'formal_kpi_certified': False,
        'historical_recommendation_debts_unresolved': historical_debt_count,
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
