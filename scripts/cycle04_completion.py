#!/usr/bin/env python3
"""第4の工程別完了・固定集計・人間の理由付き終了審査を読取専用で照合する。"""
import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from check_prediction_compliance import iso
from cycle04_operations import require, safe_path
from task_completion import prediction_completion, recommendation_completion

DATES = ('2026-10-17', '2026-10-18', '2026-10-24', '2026-10-25')
DAY_DIRECTORY = 'docs/validation/records/cycle_04/'
SUMMARY_DIRECTORY = 'docs/validation/reports/cycle_04/'
PROMOTION = 'NOT_APPROVED'


def verify_frozen_cycle(root, ref, *, allowed_prefix):
    """ローカルhashだけでなく指定Git commitから同一bytesを読み戻す。"""
    require(isinstance(ref, dict) and set(ref) == {'artifact_path', 'sha256', 'git_commit'},
            '保存先・SHA256・Git commitの固定参照が必要です')
    path = ref['artifact_path']
    require(isinstance(path, str) and path.startswith(allowed_prefix) and
            path.endswith('.json') and re.fullmatch(r'[0-9a-f]{64}', ref['sha256']) and
            re.fullmatch(r'[0-9a-f]{40}', ref['git_commit']), '固定参照の範囲またはhashが不正です')
    local = safe_path(Path(root), path).read_bytes()
    require(hashlib.sha256(local).hexdigest() == ref['sha256'], '固定参照のローカルhashが不一致です')
    try:
        proc = subprocess.run(['git', 'show', ref['git_commit'] + ':' + path],
                              cwd=root, capture_output=True, check=False)
    except OSError as exc:
        raise ValueError('Git読戻しを実行できません') from exc
    require(proc.returncode == 0 and proc.stdout == local, '指定Git commitからの読戻しが不一致または未保存です')
    return json.loads(local)


def _issue(issues, date, race, code, reason):
    issues.append({'race_date_jst': date, 'race_id': race, 'code': code, 'reason': reason})


def _prediction_check(root, date, row, entry, *, latest):
    """個別検査を再実行する。古い初回gateはvalidatorの固定履歴照合を使う。"""
    ref = entry['prediction_ref']
    intent = entry.get('intent_ref') or row.get('operations', {}).get('intent_ref')
    intent_path = intent.get('artifact_path', '') if isinstance(intent, dict) else ''
    intent_id = Path(intent_path).stem if intent_path else None
    ident = ref.get('artifact_id')
    if not ident or not intent_id or not ref.get('sha256'):
        return ['個別の事前宣言/FIX時hash参照が不足']
    status = prediction_completion(root, date, ident, intent_id=intent_id,
                                   fixed_content_sha256=ref['sha256'],
                                   artifact_path=ref['artifact_path'])
    required = ('artifact', 'receipt', 'content_match', 'individual_check')
    if latest:
        required += ('execution_gate',)
    return [key for key in required if status['checks'][key]['result'] is not True]


def _recommendation_check(root, row):
    path = row.get('recommendation_gate_path')
    if not path:
        return ['推奨gate未保存']
    try:
        gate = json.loads(safe_path(root, path).read_text(encoding='utf-8'))
        ref = gate['evidence_ref']
        report = recommendation_completion(root, ref['artifact_path'], path,
                                           fixed_content_sha256=gate['content_sha256'])
        return [key for key in ('artifact', 'receipt', 'content_match', 'individual_check',
                                'execution_gate') if report['checks'][key]['result'] is not True]
    except (ValueError, OSError, KeyError, TypeError, AttributeError) as exc:
        return [str(exc)]


def evaluate_days(root, days, *, frozen_refs=None, closure_ref=None):
    """全依頼scopeを落とさず工程不足と独立KPIの状態を返す。書込み・自動承認はしない。"""
    by_date = {}
    for day in days:
        date = day['race_date_jst']
        require(date in DATES and date not in by_date, '第4の日付の重複または対象外')
        by_date[date] = day
    missing = [d for d in DATES if d not in by_date]
    issues = []
    for date in missing:
        _issue(issues, date, None, 'DAY_NOT_REGISTERED', '依頼scope未登録。予定件数は補完しません')
    input_gaps, shadow_gaps, owner_gaps, races = [], [], [], []
    for date, day in sorted(by_date.items()):
        for race in day['initial_scope']:
            races.append({'race_date_jst': date, 'race_id': race})
            row = day['races'][race]
            history = row.get('prediction_history', [])
            first = [h for h in history if h.get('phase') == 'INITIAL']
            if not first:
                _issue(issues, date, race, 'INITIAL_MISSING', '初回Prediction未実施')
            else:
                for index, entry in enumerate(history):
                    try:
                        missing_checks = _prediction_check(root, date, row, entry, latest=index == len(history)-1)
                    except (ValueError, OSError, TypeError, KeyError, AttributeError) as exc:
                        missing_checks = [str(exc)]
                    if missing_checks:
                        _issue(issues, date, race, 'PREDICTION_CHECK_PENDING',
                               entry.get('phase', 'UNKNOWN') + 'の独立保存/個別完了未確認：' + ', '.join(missing_checks))
            if race in day['selected_scope']:
                if race not in day['final_scope']:
                    _issue(issues, date, race, 'FINAL_MISSING', '選定済み・最終工程未実施：' +
                           day['unfinished_reasons'].get(race, '理由未確認'))
                else:
                    if not any(h.get('phase') == 'FINAL' for h in history):
                        _issue(issues, date, race, 'FINAL_HISTORY_MISSING', '最終Predictionの固定履歴不足')
                    if row.get('recommendation_state') == 'PENDING':
                        _issue(issues, date, race, 'RECOMMENDATION_PENDING', '未完了の推奨PENDING')
                    issues_rec = _recommendation_check(root, row)
                    if issues_rec:
                        _issue(issues, date, race, 'RECOMMENDATION_CHECK_PENDING',
                               '最終推奨の独立保存/個別完了未確認：' + ', '.join(issues_rec))
            if race not in day['reviewed_scope']:
                _issue(issues, date, race, 'REVIEW_MISSING', '公式結果照合・回顧が未完了')
            else:
                if not row.get('result_ref') or not row.get('review'):
                    _issue(issues, date, race, 'RESULT_REVIEW_MISSING', '公式結果または回顧の固定参照不足')
                analysis = row.get('review') or {}
                if not analysis.get('protected_good_parts'):
                    owner_gaps.append({'race_date_jst': date, 'race_id': race,
                                       'reason': '回顧Ownerの保護対象が未記録'})
            state = day['kpis']['production']
            if race in state['pending_ids'] or race in state['ineligible_ids']:
                _issue(issues, date, race, 'PREDICTION_NOT_ELIGIBLE',
                       'Prediction適格性：' + state['reasons'][race])
            if race in day['final_scope']:
                state = day['kpis']['recommendation']
                if race in state['pending_ids']:
                    _issue(issues, date, race, 'RECOMMENDATION_KPI_PENDING',
                           '推奨の保留：' + state['reasons'][race])
                # 適切なNO_RECOMMENDATION/明示的印のみはINELIGIBLEでも正常な最終状態。
            if row.get('input_complete') is False:
                input_gaps.append({'race_date_jst': date, 'race_id': race,
                                   'reason': row.get('input_gap_reason') or '入力不足'})
            if race in day['kpis']['shadow']['pending_ids'] or race in day['kpis']['shadow']['ineligible_ids']:
                shadow_gaps.append({'race_date_jst': date, 'race_id': race,
                                    'reason': day['kpis']['shadow']['reasons'].get(race, '該当Shadow不足')})
    stage_complete = not issues and bool(races)
    result = {'schema_version': 'cycle04-completion-status-v1',
              'recorded_dates': sorted(by_date), 'missing_dates': missing,
              'initial_scope': races, 'issues': issues, 'unresolved_count': len(issues),
              'stage_complete': stage_complete, 'input_gaps': input_gaps,
              'shadow_gaps': shadow_gaps, 'review_owner_gaps': owner_gaps,
              'input_complete': not input_gaps, 'shadow_comparison_complete': not shadow_gaps,
              'normal_cycle_complete': False, 'state': '未開始' if not by_date else '進行中/未完了',
              'performance_promotion': PROMOTION, 'closure_ref': None,
              'summary_git_readback_verified': False, 'automatic_approval': False}
    if frozen_refs is not None:
        verify_summary_refs(root, days, frozen_refs)
        result['summary_git_readback_verified'] = True
        if stage_complete:
            result['normal_cycle_complete'] = True
            result['state'] = '正常一巡完了'
    elif stage_complete:
        result['state'] = '終了審査待ち'
    if closure_ref is not None:
        require(not result['normal_cycle_complete'], '正常一巡に理由付き終了を重ねない')
        review = verify_closure(root, closure_ref, days, expected=result)
        result['state'] = '理由付き終了'
        result['closure_ref'] = closure_ref
        result['summary_git_readback_verified'] = True
        result['reviewer'] = review['reviewer']
        result['owner'] = review['owner']
    return result


def verify_summary_refs(root, days, refs):
    require(isinstance(refs, dict) and set(refs) == {'day_refs', 'summary_ref'},
            '日別・集計の固定参照が必要')
    listed = {day['race_date_jst']: day for day in days}
    require(len(listed) == len(days), '日別の重複')
    required = {DAY_DIRECTORY + d + '.json' for d in listed}
    day_refs = refs['day_refs']
    require(isinstance(day_refs, list) and len(day_refs) == len(required), '日別固定参照の件数が不一致')
    require({r.get('artifact_path') for r in day_refs if isinstance(r,dict)} == required,
            '固定日別参照が登録scopeと不一致')
    for ref in day_refs:
        day = verify_frozen_cycle(root, ref, allowed_prefix=DAY_DIRECTORY)
        require(day == listed[day['race_date_jst']] and
                ref['artifact_path'] == DAY_DIRECTORY + day['race_date_jst'] + '.json',
                '日別の固定参照と内容が不一致')
    fixed = verify_frozen_cycle(root, refs['summary_ref'], allowed_prefix=SUMMARY_DIRECTORY)
    from cycle04_workflow import summary
    require(fixed == summary(root), '集計の再計算結果とGit読戻しが不一致')
    return fixed


def verify_closure(root, closure_ref, days, *, expected=None):
    doc = verify_frozen_cycle(root, closure_ref, allowed_prefix=SUMMARY_DIRECTORY)
    require(isinstance(doc, dict) and set(doc) == {
        'schema_version', 'decision', 'reviewed_at_jst', 'reviewer', 'owner', 'reason',
        'protected_good_parts', 'next_validation', 'initial_scope', 'documented_issues',
        'day_refs', 'summary_ref', 'performance_promotion'},
        '理由付き終了審査の固定記録に必要項目がありません')
    require(doc['schema_version'] == 'cycle04-closure-review-v1' and
            doc['decision'] == 'REASONED_CLOSE' and doc['performance_promotion'] == PROMOTION,
            '人間の理由付き終了決定が必要です。性能昇格は別審査です')
    require(all(isinstance(doc[k], str) and doc[k].strip()
                for k in ('reviewer', 'owner', 'reason', 'next_validation')) and
            isinstance(doc['protected_good_parts'], list) and
            bool(doc['protected_good_parts']) and
            all(isinstance(x, str) and x.strip() for x in doc['protected_good_parts']),
            '審査者/Owner/理由/保護対象/次の検証の記録が不足')
    reviewed = iso(doc['reviewed_at_jst'], '審査記録時刻')
    require(reviewed <= datetime.now(timezone.utc), '未来の終了審査記録は認められません')
    expected = expected or evaluate_days(root, days)
    require(doc['initial_scope'] == expected['initial_scope'] and
            doc['documented_issues'] == expected['issues'], '対象/不足理由の選択的除外または不一致')
    verify_summary_refs(root, days, {'day_refs': doc['day_refs'], 'summary_ref': doc['summary_ref']})
    return doc
