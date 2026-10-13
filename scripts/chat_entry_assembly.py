#!/usr/bin/env python3
"""既存固定参照から台帳entryを読取組立て・事前検査する。"""
import argparse
import copy
import json
from pathlib import Path

from chat_fact_provenance import verify_saved
from check_prediction_compliance import iso, validate_gate
from cycle04_operations import require, safe_path, verified_artifact
from cycle04_workflow import record_prediction


def assemble(root, entry, capture_ref, conversion_ref):
    require(isinstance(entry, dict), 'explicit entry required')
    entry = copy.deepcopy(entry)
    gate = validate_gate(root, safe_path(root, entry.get('prediction_gate_path')))
    require(gate['manual_release'] == 'v1.7.0' and gate['race_id'] == entry.get('race_id'),
            'fixed prediction identity/release mismatch')
    proof = verify_saved(root, capture_ref, conversion_ref, gate['scheduled_post_time_jst'])
    operations = entry.get('operations')
    require(isinstance(operations, dict), 'existing operations references required')
    actual, receipt = verified_artifact(root, operations.get('inputs_ref'), gate['scheduled_post_time_jst'])
    require(actual == proof['input'] and actual['race_id'] == gate['race_id'] and
            actual['data_cutoff'] == gate['data_cutoff'], 'canonical input differs from verified conversion')
    require(iso(receipt['receipt_verified_at_jst'], 'canonical input readback') <=
            iso(gate['data_cutoff'], 'prediction cutoff'), 'canonical input receipt after cutoff')
    # This path runs the real writer's ordering, revision and whole-day validator,
    # but never calls the permanent ledger save operation.
    candidate = record_prediction(root, gate['race_date_jst'], entry, preview=True)
    return {'schema_version': 'chat-entry-preview-v1', 'entry': entry,
            'candidate_day': candidate, 'read_only': True, 'writer_validation_pending': False,
            'ledger_saved': False, 'git_persistence_verified': False, 'formal_kpi_certified': False,
            'capture_ref': copy.deepcopy(capture_ref), 'conversion_ref': copy.deepcopy(conversion_ref)}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument('--entry', type=Path, required=True)
    p.add_argument('--capture-ref', type=Path, required=True)
    p.add_argument('--conversion-ref', type=Path, required=True)
    args = p.parse_args(argv)
    try:
        print(json.dumps(assemble(args.root, json.loads(args.entry.read_text()),
                                  json.loads(args.capture_ref.read_text()),
                                  json.loads(args.conversion_ref.read_text())), ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, KeyError, TypeError, IndexError) as exc:
        print('固定参照の組立て不合格：' + str(exc)); return 1


if __name__ == '__main__': raise SystemExit(main())
