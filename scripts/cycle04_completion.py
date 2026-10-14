#!/usr/bin/env python3
"""第4の工程別完了・固定集計・人間の理由付き終了審査を読取専用で照合する。"""
import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from check_prediction_compliance import iso
from cycle04_operations import require, safe_path, verified_artifact, fingerprint
from check_prediction_compliance import validate_gate
from task_completion import prediction_completion, recommendation_completion

from check_cycle04 import DATES
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
    """初回を含む固定履歴ごとに、当時の宣言→FIX→本体の独立証跡を再照合する。"""
    phase = entry.get('phase', 'UNKNOWN')
    label = phase + 'の固定履歴'
    race = row.get('race_id')
    gate_path = safe_path(root, entry.get('prediction_gate_path'))
    require(fingerprint(gate_path.read_bytes()) == entry.get('prediction_gate_sha256'),
            label + '：固定gateのhash不一致')
    gate = validate_gate(root, gate_path)
    race = gate['race_id']
    post = row['scheduled_post_time_jst']
    require(gate['race_date_jst'] == date and
            gate['scheduled_post_time_jst'] == post and
            gate['production']['baseline_forecast_id'] == entry.get('baseline_forecast_id'),
            label + '：レース・日付・発走・基準予想の不一致')

    # row.operations は最新FINALで上書きされる。旧履歴の欠落をここから補完しない。
    refs = [entry.get(k) for k in ('prediction_ref', 'intent_ref', 'fix_ref')]
    require(all(isinstance(ref, dict) for ref in refs),
            label + '：履歴固有のprediction_ref/intent_ref/fix_refが不足')
    pred_ref, intent_ref, fix_ref = refs
    gate_ref = gate['production'].get('evidence_ref')
    require(isinstance(gate_ref, dict) and
            all(pred_ref.get(k) == gate_ref.get(k) for k in
                ('artifact_id', 'artifact_path', 'sha256')),
            label + '：固定gateと予想本体の同一性不一致')
    snapshot, body_receipt = verified_artifact(root, pred_ref, post,
                                               expected_id=gate_ref['artifact_id'])
    intent, intent_receipt = verified_artifact(root, intent_ref, post)
    fix, fix_receipt = verified_artifact(root, fix_ref, post)

    require(fix.get('schema_version') == 'prediction-fix-manifest-v1' and
            fix.get('snapshot_id') == snapshot.get('snapshot_id') and
            fix.get('artifact_path') == pred_ref['artifact_path'] and
            fix.get('fixed_content_sha256') == pred_ref['sha256'] and
            fix.get('fixed_at_jst') == snapshot.get('fixed_at_jst') and
            fix.get('intent_ref') == intent_ref,
            label + '：当時の独立FIX原本・予想・宣言の一致不足')
    require(intent.get('schema_version') == 'prediction-persistence-intent-v1' and
            intent.get('snapshot_id') == snapshot.get('snapshot_id') and
            intent.get('required_race_ids') == [race] and
            intent.get('artifact_path') == pred_ref['artifact_path'] and
            intent.get('working_branch') == 'prediction/' + date and
            iso(intent.get('deadline_jst'), label + '/宣言期限') == iso(post, label + '/発走'),
            label + '：当時の事前宣言・対象scopeの一致不足')
    require(iso(intent_receipt['receipt_verified_at_jst'], label + '/宣言読戻し') <=
            iso(snapshot.get('fixed_at_jst'), label + '/予想FIX') <=
            iso(fix_receipt['persist_verified_at_jst'], label + '/FIX保存') <=
            iso(fix_receipt['receipt_verified_at_jst'], label + '/FIX読戻し') <=
            iso(body_receipt['persist_verified_at_jst'], label + '/本体保存'),
            label + '：当時の宣言・FIX・本体の保存順が不正')

    intent_path = intent_ref['artifact_path']
    intent_id = Path(intent_path).stem
    ident = pred_ref['artifact_id']
    require(intent_path == f'docs/validation/persistence-intents/{date}/{intent_id}.json',
            label + '：宣言の固定保存先が不正')
    status = prediction_completion(root, date, ident, intent_id=intent_id,
                                   fixed_content_sha256=pred_ref['sha256'],
                                   artifact_path=pred_ref['artifact_path'])
    required = ('artifact', 'receipt', 'content_match', 'individual_check')
    if latest:
        required += ('execution_gate',)
    return [key for key in required if status['checks'].get(key, {}).get('result') is not True]


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
    input_gaps, shadow_gaps, market_gaps, owner_gaps, races = [], [], [], [], []
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
            if race in day['kpis']['market']['pending_ids'] or race in day['kpis']['market']['ineligible_ids']:
                market_gaps.append({'race_date_jst': date, 'race_id': race,
                                    'reason': day['kpis']['market']['reasons'].get(race, '任意市場不足')})
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
              'shadow_gaps': shadow_gaps, 'market_gaps': market_gaps,
              'review_owner_gaps': owner_gaps,
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
        'day_refs', 'summary_ref', 'performance_promotion',
        'input_gaps', 'shadow_gaps', 'market_gaps', 'review_owner_gaps'},
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
            doc['documented_issues'] == expected['issues'] and
            all(doc[key] == expected[key] for key in
                ('input_gaps', 'shadow_gaps', 'market_gaps', 'review_owner_gaps')),
            '対象/工程・入力・Shadow・任意市場・回顧Owner不足の選択的除外または不一致')
    verify_summary_refs(root, days, {'day_refs': doc['day_refs'], 'summary_ref': doc['summary_ref']})
    return doc
