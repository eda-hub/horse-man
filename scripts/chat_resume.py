#!/usr/bin/env python3
"""保存済み原本から次の未完了確認を読取表示する。再試行は実行しない。"""
import argparse
import copy
import json
from datetime import datetime, timezone
from pathlib import Path

from check_prediction_compliance import iso, receipt_records
from cycle04_operations import require, safe_path, verified_artifact
from cycle04_workflow import read_day
from task_completion import prediction_completion, recommendation_completion

LABELS = {'artifact':'本体の保存', 'receipt':'同一artifactのreceipt',
          'content_match':'FIX時hashとの一致', 'individual_check':'対象の個別完了',
          'execution_gate':'対象の実行ゲート', 'shadow':'適用Shadowの保存'}


def inspect(root, req, now=None):
    require(isinstance(req, dict) and req.get('schema_version') == 'chat-resume-request-v1',
            'explicit resume request required')
    req = copy.deepcopy(req)
    require(req.get('phase') in {'INITIAL','FINAL'}, 'resume phase required')
    post = iso(req.get('scheduled_post_time_jst'), 'post')
    require(post.date().isoformat() == req.get('date'), 'resume date/post mismatch')
    current = now or datetime.now(timezone.utc)
    require(current.tzinfo is not None, 'resume time timezone required')
    digest = req.get('fixed_content_sha256')
    if req.get('fix_ref'):
        fix, receipt = verified_artifact(root, req['fix_ref'], req['scheduled_post_time_jst'])
        require(fix.get('schema_version') == 'prediction-fix-manifest-v1' and
                fix.get('snapshot_id') == req.get('snapshot_id'), 'FIX reference belongs to another snapshot')
        require(iso(receipt['receipt_verified_at_jst'], 'FIX readback') <= current, 'FIX receipt is in the future')
        if digest is not None: require(digest == fix['fixed_content_sha256'], 'declared FIX hash mismatch')
        digest = fix['fixed_content_sha256']
    # Never derive the expected FIX hash from today's body bytes.
    prediction = prediction_completion(root, req['date'], req.get('snapshot_id'),
                    intent_id=req.get('intent_id'), fixed_content_sha256=digest,
                    artifact_path=req.get('artifact_path'))
    recommendation = None
    if req['phase'] == 'FINAL' and req.get('recommendation_artifact_path') and req.get('recommendation_gate_path'):
        recommendation = recommendation_completion(root, req['recommendation_artifact_path'],
                    req['recommendation_gate_path'], fixed_content_sha256=req.get('recommendation_fix_hash'))
    temporal_evidence_unverified = False
    receipt_file = root/'docs/validation/persistence-receipts'/(req['date']+'.md')
    if receipt_file.is_file():
        for item in receipt_records(receipt_file):
            if (item.get('artifact_id') == req.get('snapshot_id') or
                    (req['phase'] == 'FINAL' and req.get('recommendation_artifact_path') and
                     item.get('artifact_path') == req['recommendation_artifact_path'])):
                timestamp = item.get('receipt_verified_at_jst')
                temporal_evidence_unverified |= not timestamp or iso(timestamp, 'saved receipt time') > current
    ledger_registered, ledger_reason = False, '日別台帳への同一固定参照を未確認'
    gate_path = req.get('prediction_gate_path')
    if gate_path and safe_path(root, gate_path).is_file():
        gate = json.loads(safe_path(root, gate_path).read_text())
        require(gate.get('scheduled_post_time_jst') == req['scheduled_post_time_jst'], 'resume post differs from gate')
        try:
            day, _ = read_day(root, req['date'])
            row = day['races'][gate['race_id']]
            ledger_registered = (row.get('prediction_gate_path') == gate_path and
                row.get('operations',{}).get('prediction_ref',{}).get('artifact_id') == req.get('snapshot_id') and
                (req['phase'] == 'INITIAL' or gate['race_id'] in day['final_scope']))
            ledger_reason = '保存済み台帳で同一参照を確認' if ledger_registered else ledger_reason
        except (ValueError, OSError, KeyError, TypeError):
            pass
    if temporal_evidence_unverified:
        next_check = '保存証跡の実際の時刻（未来・時刻不明は現時点の完了へ使えません）'
    elif not prediction['complete']:
        next_check = '予想：' + LABELS[prediction['missing'][0]]
    elif req['phase'] == 'FINAL' and not (recommendation and recommendation['complete']):
        next_check = '推奨：' + (LABELS[recommendation['missing'][0]] if recommendation else '独立した本体とgateの確認')
    elif not ledger_registered:
        next_check = '日別台帳と固定参照の照合'
    else:
        next_check = 'Git保存先の読戻しと必要な開始確認'
    return {'schema_version':'chat-resume-status-v1','prediction':prediction,'recommendation':recommendation,
            'fixed_references':req,'ledger_registered':ledger_registered,'ledger_reason':ledger_reason,
            'deadline_reached':current >= post,'next_check':next_check,'read_only':True,
            'temporal_evidence_unverified':temporal_evidence_unverified,
            'prediction_complete_at_current_time':prediction['complete'] and not temporal_evidence_unverified,
            'automatic_retry':False,'git_persistence_verified':False,'formal_kpi_certified':False}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    p.add_argument('--request',type=Path,required=True)
    p.add_argument('--json',action='store_true')
    args=p.parse_args(argv)
    try:
        report=inspect(args.root,json.loads(args.request.read_text()))
        if args.json: print(json.dumps(report,ensure_ascii=False,indent=2))
        else:
            print('次の確認：'+report['next_check'])
            print('期限状態：'+('発走後。発走前の再保存はできません' if report['deadline_reached'] else '発走前'))
            print(report['ledger_reason']+'。書込み・再試行は実行していません。')
        return 0
    except (ValueError,OSError,KeyError,TypeError) as exc:
        print('再開点の確認不合格：'+str(exc));return 1


if __name__=='__main__':raise SystemExit(main())
