#!/usr/bin/env python3
"""Read-only, inactive preparation: purpose and selection revision continuity.

A valid chain is a prerequisite, never a pre-race persistence or KPI certificate.
"""
import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path

SCHEMA = 'selection-history-v1'
PURPOSES = {'VALIDATION_ONLY', 'OFFICIAL_VIRTUAL', 'ACTUAL_PURCHASE'}


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def timestamp(value):
    if not isinstance(value, str):
        raise ValueError('timestamp required')
    result = datetime.fromisoformat(value)
    if result.tzinfo is None:
        raise ValueError('timezone required')
    return result


def validate_history(history, root):
    """Reject discontinuity; preserve all events, including cancelled plans."""
    if not isinstance(history, dict) or history.get('schema_version') != SCHEMA:
        raise ValueError('explicit selection-history-v1 required; legacy is not converted')
    posts = history.get('scheduled_posts')
    events = history.get('events')
    if not isinstance(posts, dict) or not posts or not isinstance(events, list) or not events:
        raise ValueError('scope and nonempty event history required')
    if any(not isinstance(race, str) or not race for race in posts):
        raise ValueError('nonempty race IDs required')
    deadlines = {race: timestamp(post) for race, post in posts.items()}
    selected, plans, previous, last_time = {}, {}, None, None
    root = Path(root).resolve()
    for revision, event in enumerate(events, 1):
        if not isinstance(event, dict):
            raise ValueError('event must be an object')
        if 'previous_sha256' not in event:
            raise ValueError('explicit previous revision hash required')
        core = {key: value for key, value in event.items() if key != 'evidence'}
        if type(event.get('revision')) is not int or event['revision'] != revision:
            raise ValueError('revision gap or duplicate')
        if event.get('previous_sha256') != previous:
            raise ValueError('previous revision hash mismatch')
        race, purpose, action = (event.get(key) for key in ('race_id', 'purpose', 'action'))
        if race not in deadlines or purpose not in PURPOSES:
            raise ValueError('race outside scope or unknown purpose')
        at = timestamp(event.get('at'))
        if at >= deadlines[race] or (last_time is not None and at < last_time):
            raise ValueError('late or reverse-time history')
        if not isinstance(event.get('reason'), str) or not event['reason'].strip():
            raise ValueError('reason required')
        evidence = event.get('evidence', {})
        if not isinstance(evidence, dict):
            raise ValueError('event evidence object required')
        if action in {'BUY', 'CHANGE', 'CANCEL', 'DESELECT'} and type(event.get('selection_revision')) is not int:
            raise ValueError('integer selection revision required')
        if action in {'CHANGE', 'CANCEL'} and type(event.get('plan_revision')) is not int:
            raise ValueError('integer plan revision required')
        relative = evidence.get('path')
        if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
            raise ValueError('repository evidence path required')
        path = (root / relative).resolve()
        if not path.is_relative_to(root):
            raise ValueError('evidence escapes repository')
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != evidence.get('sha256'):
            raise ValueError('event evidence hash mismatch')
        if json.loads(raw) != core:
            raise ValueError('event differs from original evidence')
        key = (race, purpose)
        if action == 'SELECT':
            if key in selected:
                raise ValueError('duplicate active selection')
            selected[key] = revision
        elif action == 'DESELECT':
            if event.get('selection_revision') != selected.get(key) or key not in selected:
                raise ValueError('deselection has no matching selection')
            if any(p['race_id'] == race and p['purpose'] == purpose and p['active']
                   for p in plans.values()):
                raise ValueError('cancel active plans before deselection')
            del selected[key]
        elif action in {'BUY', 'CHANGE', 'CANCEL'}:
            if key not in selected or event.get('selection_revision') != selected[key]:
                raise ValueError('BUY/change/cancel lacks matching additional selection or purpose')
            plan_id = event.get('plan_id')
            if not isinstance(plan_id, str) or not plan_id:
                raise ValueError('plan ID required')
            if action == 'BUY':
                if plan_id in plans:
                    raise ValueError('plan ID reused; cancelled plans remain history')
            else:
                prior = plans.get(plan_id)
                if (not prior or not prior['active'] or prior['race_id'] != race
                        or prior['purpose'] != purpose
                        or event.get('plan_revision') != prior['revision']):
                    raise ValueError('change/cancel revision, race or purpose mismatch')
            if action == 'CANCEL':
                plans[plan_id]['active'] = False
                plans[plan_id]['revision'] = revision
            else:
                tickets = event.get('tickets')
                if not isinstance(tickets, list) or not tickets or any(not isinstance(t, dict) for t in tickets):
                    raise ValueError('nonempty ticket objects required')
                if len({digest(t) for t in tickets}) != len(tickets):
                    raise ValueError('duplicate ticket')
                if any(t.get('purpose', purpose) != purpose for t in tickets):
                    raise ValueError('mixed ticket purposes')
                plans[plan_id] = {'race_id': race, 'purpose': purpose, 'revision': revision,
                                  'active': True, 'tickets': tickets}
        else:
            raise ValueError('unknown action')
        previous, last_time = digest(core), at
    return {'history_valid': True, 'kpi_certified': False, 'event_count': len(events),
            'head_sha256': previous, 'plans': plans,
            'note': '履歴の連続性のみ確認。発走前保存・正式KPI認証は別途必要。'}


def audit_oct11(root):
    """Audit existing legacy sources without constructing new historical events."""
    import re
    from check_cycle03 import block, DAY_TAG
    from check_betting_performance import snapshot_tickets
    root = Path(root)
    base = 'docs/validation/'
    record_path = base + 'records/2026-10-11.md'
    snapshot_path = base + 'snapshots/2026-10-11.md'
    receipt_path = base + 'persistence-receipts/2026-10-11.md'
    day = block(root / record_path, DAY_TAG)
    text = (root / snapshot_path).read_text()
    morning = text.split('## 東京8R', 1)[0]
    if not re.search(r'^- purchase_candidates: \[\]$', morning, re.M):
        raise ValueError('initial empty candidate evidence changed')
    settlement = day['fixed_plan_settlement']
    races = []
    for race, ref in sorted(settlement['races'].items()):
        sections = re.split(r'(?=^##\s+)', text, flags=re.M)
        matches = [s for s in sections if re.search(
            r'^snapshot_id:\s*' + re.escape(ref['snapshot_id']) + r'\s*$', s, re.M)]
        if len(matches) != 1:
            raise ValueError('ambiguous final snapshot')
        section = matches[0]
        if not re.search(r'^purchase_decision: BUY$', section, re.M):
            raise ValueError('settlement not backed by BUY')
        if not re.search(r'^ticket_purpose: OFFICIAL_VIRTUAL$', section, re.M):
            raise ValueError('settlement purpose mismatch')
        tickets = snapshot_tickets(root, snapshot_path, ref['snapshot_id'])
        if sum(t['stake_yen'] for t in tickets) != ref['stake_yen']:
            raise ValueError('reference settlement stake mismatch')
        races.append({'race_id': race, 'snapshot_id': ref['snapshot_id'],
                      'claimed_fixed_commit': ref['claimed_source']['commit_sha'],
                      'ticket_count': len(tickets), 'stake_yen': ref['stake_yen'],
                      'return_yen': ref['return_yen'], 'purpose': 'OFFICIAL_VIRTUAL',
                      'additional_selection_verified': False, 'formal_count_allowed': False,
                      'reason': '発走前の追加選定revision未確認。元記録の保留を維持。'})
    expected = {row['race_id'] for row in races}
    kpi = day['kpis']['betting']
    if (set(kpi['pending_ids']) != expected or kpi['eligible_ids']
            or len(races) != 5 or sum(r['ticket_count'] for r in races) != 7
            or sum(r['stake_yen'] for r in races) != settlement['stake_yen']
            or sum(r['return_yen'] for r in races) != settlement['return_yen']):
        raise ValueError('legacy eligibility or reference totals changed')
    paths = [record_path, snapshot_path, receipt_path,
             base + 'handoffs/2026-10-11-seven-open-issues.md']
    paths += sorted(str(p.relative_to(root)) for p in
                    (root / base / 'persistence-intents/2026-10-11').glob('*.json'))
    return {'audit_type': 'READ_ONLY_LEGACY_EVIDENCE', 'manual_release': 'v1.6.1',
            'initial_purchase_candidates': [], 'races': races,
            'reference_settlement': {'stake_yen': settlement['stake_yen'],
                                     'return_yen': settlement['return_yen']},
            'legacy_formal_betting': {'eligible': 0, 'pending': 5, 'roi': None},
            'next_recommendation_kpi': 'NOT_APPLICABLE_TO_LEGACY',
            'issue_status': 'OPEN', 'historical_events_created': 0,
            'sources': [{'path': p, 'sha256': hashlib.sha256((root / p).read_bytes()).hexdigest()}
                        for p in paths]}


def main():
    parser = argparse.ArgumentParser(description='用途と選定変更の履歴を読取専用で検査')
    parser.add_argument('--root', type=Path, default=Path('.'))
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--history', type=Path)
    modes.add_argument('--audit-oct11', action='store_true')
    args = parser.parse_args()
    try:
        report = audit_oct11(args.root) if args.audit_oct11 else validate_history(
            json.loads(args.history.read_text()), args.root)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0  # Audit executed; never a certificate for its pending subjects.
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(f'履歴確認失敗：{exc}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
