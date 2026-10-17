"""回顧前固定・回顧採用・訂正の全結果原票を同じ検査で保全する。"""
import copy
import json
import re
from datetime import datetime, timezone

from cycle04_operations import require, safe_path, fingerprint, validate_formal_result
from check_prediction_compliance import iso


def pair(result, manifest):
    return {'result_ref': result, 'reconciliation_ref': manifest}


def checked_json(root, ref):
    require(isinstance(ref, dict) and set(ref) == {'artifact_path', 'sha256'} and
            isinstance(ref['artifact_path'], str) and
            isinstance(ref['sha256'], str) and re.fullmatch(r'[0-9a-f]{64}', ref['sha256']),
            '固定結果参照のpath/hashが不正')
    raw = safe_path(root, ref['artifact_path']).read_bytes()
    require(fingerprint(raw) == ref['sha256'], '固定結果原票hash不一致: ' + ref['artifact_path'])
    return json.loads(raw)


def verify_pair(root, row, race, date, binding):
    result = checked_json(root, binding['result_ref'])
    # 照合manifest自体のhashも確認。manifest内部のcapture/conversion等は正式照合で検査。
    if binding['reconciliation_ref'] is not None:
        checked_json(root, binding['reconciliation_ref'])
    validate_formal_result(root, row, race=race, date=date,
                          result_ref=binding['result_ref'], manifest_ref=binding['reconciliation_ref'])
    return result


def verify_result_bindings(root, row, race, date, *, now=None):
    ready = row.get('result_ready_ref')
    origin = row.get('result_origin_ref')
    current = row.get('result_ref')
    require(ready or not row.get('result_ready_reconciliation_ref'), '結果固定本体の欠落')
    require(origin or not row.get('result_origin_reconciliation_ref'), '結果原本の欠落')
    anchors = []
    for ref, name in ((ready, 'result_ready_reconciliation_ref'),
                      (origin, 'result_origin_reconciliation_ref')):
        if ref:
            anchors.append(pair(ref, row.get(name)))
    require(not anchors or all(p == anchors[0] for p in anchors), '結果原本と回顧前固定参照が不一致')
    chain = row.get('result_correction_history', [])
    require(isinstance(chain, list), '結果訂正履歴が不正')
    require(not chain or anchors, '結果訂正の固定原本がありません')
    active = anchors[0] if anchors else (pair(current, row.get('result_reconciliation_ref')) if current else None)
    if active is None:
        return None
    previous_time = iso(verify_pair(root, row, race, date, active)['retrieved_at_jst'], 'original result time')
    original = copy.deepcopy(active)
    used = {ref['artifact_path'] for ref in active.values() if ref}
    previous = None
    for revision, ref in enumerate(chain, 1):
        prefix = f'docs/validation/result-corrections/{date}/{race}/'
        require(isinstance(ref, dict) and isinstance(ref.get('artifact_path'), str) and
                ref['artifact_path'].startswith(prefix) and ref['artifact_path'].endswith('.json'),
                '結果訂正の固定pathが不正')
        doc = checked_json(root, ref)
        require(set(doc) == {'schema_version', 'race_id', 'race_date_jst', 'revision',
                            'previous_sha256', 'from', 'to', 'reason', 'recorded_at_jst'} and
                doc['schema_version'] == 'cycle04-result-correction-v1' and
                doc['race_id'] == race and doc['race_date_jst'] == date and
                type(doc['revision']) is int and doc['revision'] == revision and
                doc['previous_sha256'] == previous and doc['from'] == active and
                isinstance(doc['reason'], str) and doc['reason'].strip(), '結果訂正の連鎖・理由・対象が不一致')
        corrected = doc['to']
        require(isinstance(corrected, dict) and set(corrected) == {'result_ref', 'reconciliation_ref'} and
                all(isinstance(r, dict) for r in corrected.values()), '訂正結果・照合の固定参照が必要')
        paths = [r.get('artifact_path') for r in corrected.values()]
        require(len(set(paths)) == 2 and all(isinstance(p, str) and p not in used for p in paths),
                '訂正は新規pathに保存し、元結果・元manifestを上書きできません')
        result = verify_pair(root, row, race, date, corrected)
        recorded = iso(doc['recorded_at_jst'], 'result correction time')
        require(recorded >= previous_time and recorded >= iso(result['retrieved_at_jst'], 'corrected result time')
                and recorded <= (now or datetime.now(timezone.utc)), '結果訂正時刻の逆転・未来')
        previous_time = recorded
        used.update(paths)
        active = corrected
        previous = ref['sha256']
    if current:
        require(pair(current, row.get('result_reconciliation_ref')) == active,
                '回顧採用結果と回顧前固定/訂正履歴が不一致')
    else:
        require(not chain, '未採用の訂正を回顧完了として扱えません')
    return {'active': active, 'original': original}


def bind_review_result(root, row, race, date, result_ref, manifest_ref, correction_ref=None):
    """既存原本を先に検査し、新結果は固定した明示訂正だけで採用する。"""
    verified = verify_result_bindings(root, row, race, date)
    incoming = pair(result_ref, manifest_ref)
    if verified:
        original = verified['original']
        row.setdefault('result_origin_ref', copy.deepcopy(original['result_ref']))
        row.setdefault('result_origin_reconciliation_ref', copy.deepcopy(original['reconciliation_ref']))
        if incoming != verified['active']:
            require(correction_ref is not None, '固定済み結果の変更には明示的な結果訂正履歴が必要')
            staged = copy.deepcopy(row)
            staged.setdefault('result_correction_history', []).append(copy.deepcopy(correction_ref))
            staged['result_ref'] = copy.deepcopy(result_ref)
            staged['result_reconciliation_ref'] = copy.deepcopy(manifest_ref)
            verify_result_bindings(root, staged, race, date)
            row['result_correction_history'] = staged['result_correction_history']
            return True
        require(correction_ref is None, '同じ結果への不要・重複訂正')
    else:
        require(correction_ref is None, '元結果なしの訂正はできません')
        verify_pair(root, row, race, date, incoming)
        row['result_origin_ref'] = copy.deepcopy(result_ref)
        row['result_origin_reconciliation_ref'] = copy.deepcopy(manifest_ref)
    return False
