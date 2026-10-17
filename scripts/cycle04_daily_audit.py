#!/usr/bin/env python3
"""依頼集合だけの段階別監査。待機と発走期限超過・結果確認後不足を分離する。"""
import json
from datetime import datetime, timezone
from pathlib import Path

from check_prediction_compliance import iso
from cycle04_schedule_change import effective_post
from cycle04_completion import _prediction_check, _recommendation_check
from cycle04_review_metrics import review_status
from cycle04_operations import require, safe_path, fingerprint, validate_official_result, validate_formal_result


def audit_days(root, days, *, now=None):
    now = now or datetime.now(timezone.utc)
    require(now.tzinfo is not None, '監査時計にtimezoneが必要')
    rows = []
    def emit(date, race, stage, state, reason):
        rows.append(dict(race_date_jst=date, race_id=race, stage=stage, state=state, reason=reason))
    for day in days:
        date = day['race_date_jst']
        for race in day['initial_scope']:
            row = day['races'][race]
            post = effective_post(root, row, race, date, at=now.isoformat(), now=now)
            history = row.get('prediction_history', [])
            for stage in ('INITIAL', 'FINAL'):
                if stage == 'FINAL' and race not in day['selected_scope']:
                    continue
                entries = [(i, h) for i, h in enumerate(history) if h.get('phase') == stage]
                missing = []
                if not entries:
                    missing.append('予想固定履歴がありません')
                else:
                    for i, h in entries:
                        missing.extend(_prediction_check(root, date, row, h, latest=i == len(history)-1))
                if stage == 'FINAL':
                    if race not in day['final_scope']:
                        missing.append('選定済みFINAL未完了')
                    missing.extend(_recommendation_check(root, row))
                    if row.get('recommendation_state') == 'PENDING':
                        missing.append('推奨PENDING')
                emit(date, race, stage, ('OVERDUE' if now >= post else 'WAITING') if missing else 'COMPLETE',
                     ' / '.join(missing) if missing else '固定・保存・個別照合済み')
            ref = row.get('result_ref') or row.get('result_ready_ref')
            if ref:
                raw = safe_path(root, ref.get('artifact_path')).read_bytes()
                require(fingerprint(raw) == ref.get('sha256'), '監査結果原票hash不一致')
                result = json.loads(raw)
                retrieved = iso(result.get('retrieved_at_jst'), '結果確認時刻')
                require(retrieved <= now, '未来の結果確認時刻')
                result_post = effective_post(root,row,race,date,at=retrieved.isoformat(),now=now)
                validate_official_result(result, race=race, date=date, post=result_post.isoformat(), horses=None)
                validate_formal_result(root,row,race=race,date=date,result_ref=ref,
                    manifest_ref=row.get('result_reconciliation_ref') or row.get('result_ready_reconciliation_ref'))
                status = review_status(row.get('review'))
                complete = race in day['reviewed_scope'] and status['state'] == 'COMPLETE' and not status['missing']
                emit(date, race, 'REVIEW', 'COMPLETE' if complete else 'OVERDUE',
                     '公式結果確認後の回顧照合' if complete else '公式結果確認済み・回顧未完了')
            else:
                emit(date, race, 'REVIEW', 'WAITING_RESULT', '公式結果未確認。発走時刻だけで確定と推測しません')
    # 宣言だけが存在し日別登録がない依頼も検出する。未来未依頼の予定日は作らない。
    from check_cycle04 import DATES
    registered = {d['race_date_jst']: d for d in days}
    for date in DATES:
        for path in sorted((Path(root)/'docs/validation/persistence-intents'/date).glob('*.json')):
            intent = json.loads(path.read_text())
            if intent.get('schema_version') != 'prediction-persistence-intent-v1':
                continue
            # 不足を別契約で固定した10/17事後照合はこの監査の前向き対象外。
            stored = Path(root)/'docs/validation/records/cycle_04'/(date+'.json')
            if stored.is_file() and json.loads(stored.read_text()).get('registration_origin') == 'POSTRACE_RECONCILIATION':
                continue
            scope = registered.get(date, {}).get('initial_scope', [])
            for race in intent.get('required_race_ids', []):
                from cycle04_migration import normalize_race
                race = normalize_race(race, date)
                if race not in scope:
                    emit(date, race, 'REGISTRATION', 'OVERDUE', '依頼宣言に対応する日別scope未登録')
    overdue = [r for r in rows if r['state'] == 'OVERDUE']
    return {'schema_version': 'cycle04-daily-audit-v1', 'checked_at': now.isoformat(),
            'rows': rows, 'overdue_count': len(overdue),
            'state': 'INCOMPLETE' if overdue else ('WAITING' if any(r['state'].startswith('WAITING') for r in rows) else 'COMPLETE')}
