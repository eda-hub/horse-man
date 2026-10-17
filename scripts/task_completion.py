"""個別予想・推奨の証跡を独立検査する。過去証跡の作成・認証昇格は行わない。"""

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from check_prediction_compliance import (ComplianceError, evidence, forward_shadow_evidence,
                                         iso, receipt_records, validate_gate)
from persistence_status import describe_persistence, render_persistence


ERRORS = (ComplianceError, OSError, ValueError, TypeError, KeyError, AttributeError)
LABELS = {'artifact': '本体', 'receipt': '保存証跡', 'content_match': 'FIX時の内容との一致',
          'individual_check': '個別完了確認', 'execution_gate': '実行ゲート',
          'shadow': '適用Shadow', 'audit': '全体監査（個別完了の代用不可）'}


def target_name(kind, date, races):
    if not isinstance(races, list):
        races = []
    venues = {'TOK': '東京', 'TOKYO': '東京', 'KYO': '京都', 'KYOTO': '京都',
              'NAK': '中山', 'NAKAYAMA': '中山', 'HAN': '阪神', 'HANSHIN': '阪神',
              'CHU': '中京', 'CHUKYO': '中京', 'SAPPORO': '札幌', 'HAKODATE': '函館',
              'FUKUSHIMA': '福島', 'NIIGATA': '新潟', 'KOKURA': '小倉'}
    names = []
    for race in races:
        match = re.search(r'-([A-Z]+)-(\d{2})$', race) if isinstance(race, str) else None
        if match and match[1] in venues:
            names.append(f'{venues[match[1]]}{int(match[2])}R')
    scope = '・'.join(names) if len(names) == len(races) and names else f'{len(races)}レース' if races else '対象レース未確認'
    return f'{date} {scope}の{kind}'


def relative(root, path):
    p = Path(path)
    if p.is_absolute() or '..' in p.parts or not (root / p).resolve().is_relative_to(root.resolve()):
        raise ComplianceError('completion artifact must be under repository root')
    return root / p


def checked(checks, name, operation):
    try:
        value = operation()
        if value is None:
            raise ComplianceError('verification produced no result')
        source = value.get('path', value.get('recommendation_id', '照合済み')) if isinstance(value, dict) else value
        checks[name] = {'result': True, 'source': str(source)}
        return value
    except ERRORS as exc:
        checks[name] = {'result': False, 'error': str(exc)}
        return None


def same_content(raw, fixed_hash):
    if not re.fullmatch('[0-9a-f]{64}', fixed_hash or ''):
        raise ComplianceError('exact FIX content hash required')
    if hashlib.sha256(raw).hexdigest() != fixed_hash:
        raise ComplianceError('FIX/readback content hash mismatch')
    return fixed_hash


def shadow_result(root, gates):
    if not gates:
        raise ComplianceError('Shadow applicability cannot be established without execution gates')
    found = False
    missing = []
    for gate in gates:
        items = gate.get('shadow_items')
        if not isinstance(items, list):
            missing.append('explicit Shadow scope required')
            continue
        for item in items:
            item_id = item.get('item_id', 'unknown') if isinstance(item, dict) else 'unknown'
            label = 'completion/shadow/' + str(item_id)
            if not isinstance(item, dict):
                missing.append(label + ': invalid item')
                continue
            eligibility = item.get('kpi_eligibility')
            if eligibility == 'NOT_APPLICABLE':
                continue
            found = True
            try:
                if eligibility not in {'ELIGIBLE', 'INELIGIBLE'}:
                    raise ComplianceError('applicable Shadow is pending or unperformed')
                state = str(item.get('state', ''))
                if state.startswith(('PENDING', 'NOT_STARTED', 'UNAVAILABLE', 'BLOCKED')):
                    raise ComplianceError('applicable Shadow is not complete')
                if eligibility == 'ELIGIBLE' and gate.get('schema_version') == 'prediction-compliance-v2':
                    forward_shadow_evidence(root, item.get('evidence_ref'), label,
                                            iso(gate['scheduled_post_time_jst'], label+'/post'),
                                            race_id=gate['race_id'], data_cutoff=gate['data_cutoff'])
                else:
                    evidence(root, item.get('evidence_ref'), label,
                             eligibility == 'ELIGIBLE',
                             iso(gate['scheduled_post_time_jst'], label+'/post'))
            except ERRORS as exc:
                missing.append(label + ': ' + str(exc))
    if missing:
        raise ComplianceError('Shadow items missing/invalid: ' + '; '.join(missing))
    return 'VERIFIED' if found else 'NOT_APPLICABLE'


def finish(target, checks, audit_succeeded):
    if audit_succeeded is not None and type(audit_succeeded) is not bool:
        raise ValueError('監査結果は真偽値、未実施はnullで指定してください')
    checks['audit'] = {'result': audit_succeeded, 'required': False}
    for name in LABELS:
        checks.setdefault(name, {'result': None})
    required = [name for name in LABELS if name != 'audit']
    complete = all(checks[name]['result'] is True or
                   checks[name]['result'] == 'NOT_APPLICABLE' for name in required)
    persistence = None
    if checks['artifact']['result'] is True:
        match = checks['content_match']['result']
        readback = False if match is False else True if checks['receipt']['result'] is True else None
        persistence = describe_persistence(target, write_attempted=True, write_succeeded=True,
                                           readback_matches=readback,
                                           verification_succeeded=checks['individual_check']['result']
                                           if readback is True else None)
    return {'schema_version': 'individual-completion-status-v1', 'target': target,
            'checked_at_jst': datetime.now(timezone(timedelta(hours=9))).isoformat(),
            'complete': complete, 'checks': checks, 'persistence': persistence,
            'missing': [name for name in required if checks[name]['result'] is not True and
                        checks[name]['result'] != 'NOT_APPLICABLE'],
            'eligibility_promoted': False, 'evidence_created': False}


def render_completion(report):
    text = [f"対象：{report['target']}",
            '個別対象の必須工程は完了しました。' if report['complete']
            else '個別対象の完了確認には不足があります。']
    for name, label in LABELS.items():
        value = report['checks'][name]['result']
        state = '対象外' if value == 'NOT_APPLICABLE' else '成功' if value is True else '失敗・不足' if value is False else '未実施'
        text.append(f'{label}：{state}')
    if report['persistence']:
        text.append(render_persistence(report['persistence']))
    if report['missing']:
        text.append('原因：' + '、'.join(LABELS[name] for name in report['missing']) + 'が未確認または不一致です。')
        text.append('次の確認：不足した対象の原本・内容hash・保存証跡・個別検証結果を照合してください。')
    else:
        text.append('次の確認：この結果と参照した証跡を記録してください。')
    return '\n'.join(text)


def prediction_completion(root, date, snapshot_id, *, intent_id=None, fixed_content_sha256=None,
                          artifact_path=None, audit_succeeded=None):
    from verify_prediction_persistence import resolve_snapshot, verify, check_intent
    root = Path(root)
    checks = {}
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', date or ''):
        raise ValueError('レース日付を年月日で指定してください')
    if artifact_path:
        relative(root, artifact_path)
    snapshot = checked(checks, 'artifact', lambda: resolve_snapshot(root, date, snapshot_id, artifact_path))
    # 本体とreceiptを別項目にし、同一artifact・実際の時刻を既存検証で確認する。
    checked(checks, 'receipt', lambda: verify(root, date, snapshot_id,
                                             expected_artifact_path=artifact_path))
    if fixed_content_sha256 and snapshot:
        checked(checks, 'content_match', lambda: same_content(snapshot['hash_bytes'], fixed_content_sha256))
    if intent_id and fixed_content_sha256:
        def individual():
            if not re.fullmatch(r'[a-zA-Z0-9_-]+', intent_id):
                raise ComplianceError('invalid intent ID')
            path = root / 'docs/validation/persistence-intents' / date / (intent_id + '.json')
            intent = json.loads(path.read_text(encoding='utf-8'))
            if intent.get('snapshot_id') != snapshot_id:
                raise ComplianceError('individual intent/snapshot mismatch')
            check_intent(root, path)
            saved = resolve_snapshot(root, date, snapshot_id, intent.get('artifact_path'))
            same_content(saved['hash_bytes'], fixed_content_sha256)
            return path
        checked(checks, 'individual_check', individual)
    gates = []
    def execution():
        if not snapshot or not snapshot.get('race_ids'):
            raise ComplianceError('explicit individual race scope required')
        for race in snapshot['race_ids']:
            path = relative(root, f'docs/validation/execution-gates/{date}/{race}.json')
            # Shadowのみ不正なgateでも個別不足を表示するため、
            # 原本を診断用に保持する。正式なgate適格認証はvalidate_gateだけで行う。
            raw_gate = json.loads(path.read_text(encoding='utf-8'))
            ref = raw_gate.get('production', {}).get('evidence_ref', {})
            if (raw_gate.get('race_date_jst') != date or raw_gate.get('race_id') != race or
                    ref.get('artifact_id') != snapshot_id or
                    ref.get('artifact_path') != snapshot['artifact_path']):
                raise ComplianceError('execution gate refers to a different prediction')
            gates.append(raw_gate)
            validate_gate(root, path)
        return 'VERIFIED'
    checked(checks, 'execution_gate', execution)
    if gates:
        result = checked(checks, 'shadow', lambda: shadow_result(root, gates))
        if result == 'NOT_APPLICABLE':
            checks['shadow']['result'] = 'NOT_APPLICABLE'
    races = snapshot.get('race_ids', []) if snapshot else []
    return finish(target_name('予想', date, races), checks, audit_succeeded)


def recommendation_completion(root, artifact_path, gate_path, *, fixed_content_sha256=None,
                              audit_succeeded=None):
    from recommendation import validate_snapshot, read_json, verify
    root = Path(root)
    artifact, path = relative(root, artifact_path), relative(root, gate_path)
    checks = {}
    rec = checked(checks, 'artifact', lambda: validate_snapshot(root, read_json(artifact)))
    if fixed_content_sha256 and artifact.is_file():
        checked(checks, 'content_match', lambda: same_content(artifact.read_bytes(), fixed_content_sha256))
    def receipt():
        if not rec:
            raise ComplianceError('recommendation body unavailable')
        receipts = root / 'docs/validation/persistence-receipts' / (rec['race_date_jst'] + '.md')
        # The initial R01 is still preserved. Only the single verified
        # readback receipt (R02) is eligible as an individual completion.
        # This check is independent of the recommendation gate: an absent gate
        # must not hide a successfully preserved body and receipt.
        records = receipt_records(receipts)
        matches = [x for x in records if
                   x.get('artifact_id') == rec['recommendation_id'] and
                   x.get('artifact_path') == artifact_path and
                   x.get('receipt_persist_status') == 'RECEIPT_VERIFIED']
        if len(matches) != 1:
            raise ComplianceError('verified recommendation receipt must be unique')
        item = matches[0]
        previous_id = item.get('previous_receipt_ref')
        if previous_id:
            previous = [x for x in records if x.get('receipt_id') == previous_id]
            if len(previous) != 1:
                raise ComplianceError('recommendation receipt predecessor missing/duplicated')
            prior = previous[0]
            if (previous_id == item['receipt_id'] or
                    prior.get('artifact_id') != item['artifact_id'] or
                    prior.get('artifact_path') != item['artifact_path'] or
                    prior.get('content_sha256') != item.get('content_sha256') or
                    prior.get('scheduled_post_time_jst') != item.get('scheduled_post_time_jst') or
                    prior.get('persist_verified_at_jst') != item.get('persist_verified_at_jst') or
                    prior.get('artifact_persist_status') != 'PERSIST_VERIFIED' or
                    prior.get('receipt_persist_status') not in
                    {'RECEIPT_READBACK_PENDING', 'RECEIPT_VERIFIED'}):
                raise ComplianceError('recommendation receipt predecessor conflicts')
        if (item.get('artifact_persist_status') != 'PERSIST_VERIFIED' or
                item.get('receipt_persist_status') != 'RECEIPT_VERIFIED' or
                item.get('timing_eligibility') != 'PRE_RACE_ELIGIBLE' or
                item.get('content_sha256') != hashlib.sha256(artifact.read_bytes()).hexdigest() or
                item.get('scheduled_post_time_jst') != rec['scheduled_post_time_jst']):
            raise ComplianceError('recommendation receipt/hash mismatch')
        if not (iso(rec['fixed_at_jst'], 'fixed') <= iso(item.get('persist_verified_at_jst'), 'saved') <=
                iso(item.get('receipt_verified_at_jst'), 'readback') < iso(rec['scheduled_post_time_jst'], 'post')):
            raise ComplianceError('recommendation receipt timestamps invalid')
        return item['receipt_id']
    checked(checks, 'receipt', receipt)
    def execution():
        value = verify(root, path)
        gate = read_json(path)
        if gate['evidence_ref']['artifact_path'] != artifact_path or not rec or value != rec:
            raise ComplianceError('gate refers to a different recommendation')
        return path
    checked(checks, 'execution_gate', execution)
    if fixed_content_sha256:
        def individual():
            same_content(artifact.read_bytes(), fixed_content_sha256)
            return execution()
        checked(checks, 'individual_check', individual)
    # 推奨の現行独立契約にShadowはない。Prediction側のShadow/KPIを転用しない。
    checks['shadow'] = {'result': 'NOT_APPLICABLE', 'source': 'recommendation-snapshot-v1'}
    target = target_name('推奨', rec['race_date_jst'], [rec['race_id']]) if rec else '指定ファイルの推奨'
    return finish(target, checks, audit_succeeded)
