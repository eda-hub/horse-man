#!/usr/bin/env python3
"""公式結果を保存本文・固定予想/推奨と再照合する読取専用入口。"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from chat_result_conversion import normalize_result
from check_prediction_compliance import iso, validate_gate
from cycle04_operations import require, safe_path, fingerprint, verified_artifact, validate_official_result
from recommendation import verify as verify_recommendation, settle


def fixed_json(root, ref):
    require(isinstance(ref, dict) and set(ref) == {'artifact_path','sha256'}, 'explicit frozen path/hash required')
    raw = safe_path(root, ref['artifact_path']).read_bytes()
    require(fingerprint(raw) == ref['sha256'], 'frozen artifact hash mismatch')
    data = json.loads(raw)
    require(isinstance(data,dict), 'fixed JSON object required')
    return data


def reconcile(bundle, conversion, result, *, gate=None, recommendation=None, as_of=None):
    rebuilt = normalize_result(bundle, conversion['annotation'])
    require(rebuilt == conversion, 'saved result conversion differs from source reconstruction')
    require(result == rebuilt['result'], 'official result differs from quoted source')
    req = bundle['request']
    now = iso(as_of,'audit time') if as_of else datetime.now(timezone.utc)
    require(iso(result['retrieved_at_jst'],'result retrieval') <= now, 'future result cannot be reviewed')
    if gate is not None:
        for key in ('race_id','race_date_jst','scheduled_post_time_jst'):
            require(gate.get(key) == req[key], 'fixed prediction/result identity mismatch')
        validate_official_result(result, race=gate['race_id'], date=gate['race_date_jst'],
                                 post=gate['scheduled_post_time_jst'], horses=gate['production']['ranking'])
    outcome = {'status':'NOT_APPLICABLE','tickets':[]} if recommendation is None else settle(recommendation,result)
    return {'schema_version':'chat-result-reconciliation-v1','race_id':req['race_id'],
            'race_date_jst':req['race_date_jst'],'result':result,'mode':rebuilt['mode'],
            'text_values_matched':True,'prediction_state':'FIXED' if gate else 'UNFINALIZED_OR_ABSENT',
            'recommendation_result':outcome,'read_only':True,'formal_kpi_certified':False,
            'origin_authenticity_certified':False,'payout_required':False}


def audit_saved(root, refs, as_of=None):
    require(isinstance(refs,dict) and set(refs) == {'capture','conversion','result','prediction_gate','prediction_original','recommendation_gate'},
            'all fixed references, including absent gates, required')
    bundle = fixed_json(root,refs['capture']); conversion = fixed_json(root,refs['conversion'])
    result = fixed_json(root,refs['result'])
    gate = rec = None
    if refs['prediction_gate'] is not None:
        fixed = fixed_json(root,refs['prediction_gate'])
        gate = validate_gate(root,safe_path(root,refs['prediction_gate']['artifact_path']))
        require(gate == fixed, 'prediction gate changed during audit')
        original = refs['prediction_original']
        require(isinstance(original,dict), 'independent frozen prediction original reference required')
        gate_ref = gate['production']['evidence_ref']
        for key in ('artifact_id','artifact_path','receipt_path','receipt_id'):
            require(original.get(key)==gate_ref.get(key), 'prediction original reference differs from fixed gate')
        prediction,_ = verified_artifact(root,original,gate['scheduled_post_time_jst'])
        for key in ('ranking','probabilities'):
            require(prediction.get(key) == gate['production'][key], 'fixed prediction original differs')
    require(gate is not None or refs['prediction_original'] is None, 'original cannot be detached from its gate')
    if refs['recommendation_gate'] is not None:
        fixed_json(root,refs['recommendation_gate'])
        rec = verify_recommendation(root,safe_path(root,refs['recommendation_gate']['artifact_path']))
        require(refs['prediction_gate'] is not None, 'recommendation requires its fixed prediction')
        require(rec.get('data_cutoff') == gate.get('data_cutoff'), 'recommendation cutoff mismatch')
    report = reconcile(bundle,conversion,result,gate=gate,recommendation=rec,as_of=as_of)
    report['fixed_refs'] = refs
    return report



FORMAL_RESULT_SCHEMA = 'cycle04-result-reconciliation-manifest-v1'


def formal_now():
    """正式算入の検査時刻。外部CLIの任意時刻を信用しない。"""
    return datetime.now(timezone.utc)


def validate_formal_result(root, row, *, race, date, result_ref, manifest_ref):
    """日別writer・日別checker・summary・回顧資料に共通する正式結果適格性。

    別保存のmanifestをhash確認し、保存本文から変換し直す。
    診断reportのformal_kpi_certifiedは書き換えない。
    """
    now = formal_now()
    require(isinstance(row, dict) and isinstance(result_ref, dict),
            'formal result and race entry required')
    manifest = fixed_json(root, manifest_ref)
    require(set(manifest) == {'schema_version', 'refs'} and
            manifest['schema_version'] == FORMAL_RESULT_SCHEMA,
            'independent formal result reconciliation manifest required')
    refs = manifest['refs']
    require(isinstance(refs, dict) and refs.get('result') == result_ref,
            'formal result reference differs from frozen reconciliation manifest')
    history = row.get('prediction_history', [])
    gate_path = row.get('prediction_gate_path')
    if gate_path:
        require(isinstance(history, list) and history and
                history[-1].get('prediction_gate_path') == gate_path,
                'latest fixed prediction history required for result')
        expected_gate = {'artifact_path': gate_path,
                         'sha256': history[-1]['prediction_gate_sha256']}
        require(refs.get('prediction_gate') == expected_gate and
                refs.get('prediction_original') == history[-1]['prediction_ref'] and
                refs['prediction_original'] == row.get('operations', {}).get('prediction_ref'),
                'formal result references another prediction')
    else:
        require(refs.get('prediction_gate') is None and
                refs.get('prediction_original') is None,
                'unfinalized result cannot attach a different prediction')
    rec_path = row.get('recommendation_gate_path')
    if rec_path:
        expected_rec = {'artifact_path': rec_path,
                        'sha256': fingerprint(safe_path(root, rec_path).read_bytes())}
        require(refs.get('recommendation_gate') == expected_rec,
                'formal result references another recommendation')
    else:
        require(refs.get('recommendation_gate') is None,
                'result references a detached recommendation')
    report = audit_saved(root, refs, as_of=now.isoformat())
    bundle = fixed_json(root, refs['capture'])
    req = bundle['request']
    require(req['purpose'] == 'RESULT' and req['race_id'] == race and
            req['race_date_jst'] == date and
            iso(req['scheduled_post_time_jst'], 'result post') ==
            iso(row.get('scheduled_post_time_jst'), 'registered post'),
            'formal result race/date/scheduled post mismatch')
    require(report['race_id'] == race and report['race_date_jst'] == date and
            report['mode'] == 'FORWARD',
            'only quoted FORWARD result can enter formal review')
    require(iso(bundle['recorded_at'], 'capture recording') <= now,
            'future source capture cannot enter formal review')
    require(row.get('mode') == 'FORWARD', 'replayed day cannot become formal result')
    # 検査成功の診断フラグを正式認証フラグへ書き換えない。
    require(report['formal_kpi_certified'] is False,
            'read-only reconciliation must not self-certify formal KPI')
    return report


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('manifest',type=Path)
    p.add_argument('--root',type=Path,default=Path('.'));p.add_argument('--as-of')
    args=p.parse_args(argv)
    try:
        print(json.dumps(audit_saved(args.root,json.loads(args.manifest.read_text()),args.as_of),
                         ensure_ascii=False,indent=2));return 0
    except (ValueError,TypeError,KeyError,OSError) as exc:
        print('公式結果再照合保留：'+str(exc));return 1


if __name__=='__main__':raise SystemExit(main())
