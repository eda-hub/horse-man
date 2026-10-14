#!/usr/bin/env python3
"""初回/最終の固定Shadow履歴と、最新レース単位KPIの共通判定。"""
import copy
import hashlib

from check_prediction_compliance import validate_gate
from cycle04_operations import require, safe_path

STATES = {'ELIGIBLE', 'INELIGIBLE', 'PENDING', 'NOT_APPLICABLE'}
APPLICABILITY = {'APPLICABLE', 'NOT_APPLICABLE', 'UNKNOWN'}


def previous_items(history, root):
    if not history:
        return set()
    gate = validate_gate(root, safe_path(root, history[-1]['prediction_gate_path']))
    return {item['item_id'] for item in gate.get('shadow_items', [])}


def assess(gate, applicability, prior_ids=()):
    """適用なしは空リストから推論しない。消えた項目にも最終判断を要求する。"""
    require(isinstance(applicability, dict), 'explicit shadow applicability required')
    status = applicability.get('status')
    reason = applicability.get('reason')
    require(status in APPLICABILITY and isinstance(reason, str) and reason.strip(),
            'shadow applicability status/reason required')
    items = gate.get('shadow_items', [])
    ids = [item['item_id'] for item in items]
    require(len(ids) == len(set(ids)), 'duplicate shadow item id')
    require(applicability.get('item_ids') == ids, 'shadow applicability item_ids mismatch')
    require((status == 'APPLICABLE') == bool(items),
            'shadow applicability must explicitly distinguish applicable items')
    dispositions = applicability.get('previous_item_dispositions', {})
    require(isinstance(dispositions, dict), 'shadow previous-item dispositions must be object')
    removed = set(prior_ids) - set(ids)
    require(set(dispositions) == removed, 'removed shadow items need explicit dispositions')
    for item_id, disposition in dispositions.items():
        require(isinstance(disposition, dict) and
                disposition.get('status') in {'NOT_APPLICABLE', 'UNKNOWN', 'INELIGIBLE'} and
                isinstance(disposition.get('reason'), str) and disposition['reason'].strip(),
                'removed shadow item disposition/reason missing')
        if status == 'NOT_APPLICABLE':
            require(disposition['status'] == 'NOT_APPLICABLE',
                    'final shadow not applicable cannot hide unresolved prior item')
    if status == 'UNKNOWN' and removed:
        require(any(d['status'] != 'NOT_APPLICABLE' for d in dispositions.values()),
                'unknown shadow cannot silently dismiss all prior items')
    if status == 'NOT_APPLICABLE':
        require(gate['kpi_eligibility']['shadow'] != 'ELIGIBLE',
                'not applicable shadow cannot have an eligible gate')
        state = 'NOT_APPLICABLE'
    elif status == 'UNKNOWN':
        require(gate['kpi_eligibility']['shadow'] != 'ELIGIBLE',
                'unverified shadow applicability cannot be eligible')
        state = 'PENDING'
    else:
        values = [item.get('kpi_eligibility', 'NOT_APPLICABLE') for item in items]
        require(all(value in STATES for value in values), 'shadow item state invalid')
        if any(value in {'PENDING', 'NOT_APPLICABLE'} for value in values):
            state = 'PENDING'
        elif any(value == 'INELIGIBLE' for value in values):
            state = 'INELIGIBLE'
        else:
            state = 'ELIGIBLE'
        if state == 'ELIGIBLE':
            require(gate['kpi_eligibility']['shadow'] == 'ELIGIBLE',
                    'eligible shadow must match gate')
    return state


def snapshot(root, gate, identity, applicability, prior_ids=()):
    state = assess(gate, applicability, prior_ids)
    return {'phase': identity['phase'],
            'prediction_gate_path': identity['prediction_gate_path'],
            'prediction_gate_sha256': identity['prediction_gate_sha256'],
            'baseline_forecast_id': identity['baseline_forecast_id'],
            'data_cutoff': gate['data_cutoff'],
            'applicability': copy.deepcopy(applicability),
            'kpi_state': state,
            'items': [{key: copy.deepcopy(item[key]) for key in
                       ('item_id', 'state', 'kpi_eligibility', 'evidence_ref')
                       if key in item} for item in gate['shadow_items']]}


def verify_history(root, row, race, date, history):
    entries = row.get('shadow_history', [])
    require(isinstance(entries, list), 'shadow history list required')
    require(len(entries) <= len(history), 'shadow history length exceeds prediction history')
    if not entries:
        return None  # 旧台帳の欠落を後から適格な比較履歴として捏造しない
    offset = len(history) - len(entries)
    for index, recorded in enumerate(entries):
        ident = history[offset + index]
        require(recorded.get('phase') == ident['phase'] and
                recorded.get('prediction_gate_path') == ident['prediction_gate_path'] and
                recorded.get('prediction_gate_sha256') == ident['prediction_gate_sha256'] and
                recorded.get('baseline_forecast_id') == ident['baseline_forecast_id'],
                'shadow history identity/hash mismatch')
        gate_path = safe_path(root, ident['prediction_gate_path'])
        require(hashlib.sha256(gate_path.read_bytes()).hexdigest() ==
                recorded['prediction_gate_sha256'], 'shadow history gate hash mismatch')
        gate = validate_gate(root, gate_path)
        require(gate['race_id'] == race and gate['race_date_jst'] == date,
                'shadow history race mismatch')
        prior = previous_items(history[:offset + index], root)
        expected = snapshot(root, gate, ident, recorded.get('applicability'), prior)
        require(recorded == expected, 'shadow history evidence/state mismatch')
    require(entries[-1]['prediction_gate_path'] == row.get('prediction_gate_path') and
            history[-1]['prediction_gate_path'] == entries[-1]['prediction_gate_path'],
            'latest shadow/prediction history mismatch')
    return entries[-1]
