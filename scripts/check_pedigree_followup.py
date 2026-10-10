#!/usr/bin/env python3
"""実データ保存の整合性と未完了の誤昇格を、固定原票と観測時刻から検査する。"""
from collections import Counter
from pathlib import Path
import json
from pedigree_registry import Registry, read, digest
from pedigree_stats import verify


def check(repo='.'):
    root = Path(repo)
    directory = root / 'data/pedigree/reconciliations/2026-10-09-followup'
    summary = read(directory / 'scope_summary.json')
    imported = read(directory / 'import_summary.json')
    evidence = read(directory / 'jbis_evidence.json')
    sheets = evidence.get('records', []) or [r for part in evidence['records_files'] for r in read(directory / part)['records']]
    manifest = read(root / 'data/condition_stats/inputs/prediction-period-jra-20260816-20261004.json')
    entry_index = read(directory / 'reported_pedigree_entries.json')
    entries = entry_index.get('entries', []) or [e for part in entry_index['entries_files'] for e in read(directory / part)['entries']]
    scope = read(directory / 'prediction_scope.json')
    assert summary['mode'] == 'REPLAY' and summary['production_eligible'] is False
    assert set(r['race_id'] for r in scope['races']) == set(r['race_id'] for r in manifest['races'])
    assert len(manifest['races']) == summary['jra_races'] == 159
    assert manifest['all_runners_included'] is True
    assert all(scope['period_start'] <= r['race_date_jst'] <= scope['period_end'] for r in manifest['races'])
    pairs = {(e['race_id'], e['horse_number']): e for e in entries}
    assert len(pairs) == len(entries) == summary['entered_rows'] == 2182
    runner_ids, unresolved, status = set(), set(), Counter()
    for race in manifest['races']:
        assert race['official_source']['source_class'] == 'OFFICIAL_JRA'
        assert len(race['runners']) - sum(x['status'] in {'SCRATCHED', 'EXCLUDED'} for x in race['runners']) == race['declared_starters']
        for runner in race['runners']:
            entry = pairs[race['race_id'], runner['horse_number']]
            assert entry['name'] == runner['horse_name']
            assert entry['horse_key'] == runner['horse_key']
            assert entry['jra_id'] == runner['entry_reference_id']
            runner_ids.add(entry['jra_id']); status[runner['status']] += 1
            if runner['identity_status'] != 'RESOLVED_WITH_JBIS':
                assert entry['pedigree_verification'] == 'WEB_AGGREGATOR_REPORTED_UNVERIFIED'
                unresolved.add(entry['jra_id'])
    assert len(runner_ids) == summary['unique_horses'] == 2089
    assert dict(status) == summary['result_statuses']
    assert status['FINISHED'] + status['DNF'] + status['DQ'] == summary['starters'] == 2177
    missing = read(directory / 'missing_pedigrees.json')
    assert unresolved == {x['entry_reference_id'] for x in missing['horses']}
    assert len(unresolved) == missing['missing_unique_count'] == summary['missing_jbis_unique_horses'] 
    assert missing['status'] == summary['remaining_status'] == 'BLOCKED_SOURCE_HTTP_403'
    registry = Registry(root / 'data/pedigree')
    cutoff = imported['verification_cutoff']
    expected = {format(i, '0%db' % d).translate(str.maketrans('01', 'SD')) for d in range(1, 6) for i in range(2**d)}
    edges = {}
    for sheet in sheets:
        assert set(sheet['ancestors']) == expected
        assert sheet['horse']['birth_year'] == int(sheet['jra_id'][:4])
        for i, path in enumerate(['S', 'SS', 'SD', 'D', 'DS', 'DD']):
            assert sheet['ancestors'][path]['id'] == sheet['basic_parent_links'][i]['id']
        for path, ancestor in sheet['ancestors'].items():
            parent = sheet['horse']['id'] if len(path) == 1 else sheet['ancestors'][path[:-1]]['id']
            pair, value = ('jbis-' + parent, path[-1]), 'jbis-' + ancestor['id']
            assert pair not in edges or edges[pair] == value
            edges[pair] = value
    for (key, path), value in edges.items():
        fact = registry.fact(key, 'parent:' + path, cutoff)
        assert fact['status'] == 'VERIFIED' and fact['value'] == value
    assert len(sheets) + len(unresolved) == len(runner_ids)
    assert len(sheets) == imported['source_sheet_count'] == summary['verified_jbis_unique_horses'] 
    assert len(edges) == imported['source_parent_edge_count']
    for history in read(directory / 'training_history.json')['records']:
        fact = registry.fact(history['horse_key'], 'attribute:training_country', cutoff)
        assert fact['status'] == 'VERIFIED' and fact['value'] == history['country']
        assert registry.fact(history['horse_key'], 'attribute:training_country', '2026-10-04T23:59:59+09:00')['status'] != 'VERIFIED'
        for source in history['sources']:
            assert digest(source['fields']) == source['record_hash']
    snapshot = verify(root, root / summary['condition_snapshot'])
    assert snapshot['completeness'] == summary['condition_snapshot_completeness'] == 'PARTIAL'
    assert snapshot['all_runners']['valid_starts'] == summary['starters']
    for group in snapshot['groups'].values():
        assert group['cohorts']['UNKNOWN']['horses'] == len(unresolved)
        assert group['coverage']['result_coverage'] == 1
        assert sum(c['entries'] for c in group['cohorts'].values()) == summary['entered_rows']
    return {'integrity': 'PASS', 'data_completion': 'BLOCKED_SOURCE_HTTP_403', 'jra_races':159,
            'entered_rows':2182, 'starters':2177, 'verified_jbis_horses':len(sheets),
            'unverified_jbis_horses':len(unresolved), 'historical_training_episodes_confirmed':3,
            'condition_snapshot': 'PARTIAL', 'production_eligible':False}


if __name__ == '__main__':
    print(json.dumps(check(), ensure_ascii=False, indent=2))
