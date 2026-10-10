#!/usr/bin/env python3
"""JBIS取得不能分の別サイト原票・訂正・独立IDと固定REPLAYを検査する。"""
from collections import Counter
from pathlib import Path
import json
import re
import unicodedata
from pedigree_registry import Registry, read, digest
from pedigree_stats import verify, main_training_country

DIRECTORY = 'data/pedigree/reconciliations/2026-10-10-alternative'
POSITIONS = {format(i, '0%db' % d).translate(str.maketrans('01', 'SD'))
             for d in range(1, 6) for i in range(2**d)}


def source_name(name):
    value = unicodedata.normalize('NFKC', name)
    value = re.sub(r'\s*\((?:[A-Z]{2,3}|米|英|仏|独|愛|加|伊|豪|日|亜|南阿|新|智|巴)\)\s*$', '', value)
    value = value.replace('リアルシヤダイ', 'リアルシャダイ').replace('ダイナフエアリー', 'ダイナフェアリー')
    value = re.sub(r'(?<=[ァ-ヿ])II$', '2', value)
    value = value.translate(str.maketrans('ァィゥェォャュョッヮ', 'アイウエオヤユヨツワ'))
    return re.sub(r"[\s’'・.‐‑–-]", '', value).casefold()


def parts(directory, name):
    index = read(directory / (name + '.json'))
    records = [r for part in index['records_files'] for r in read(directory / part)['records']]
    assert len(records) == index['record_count'], name
    return records


def check_sheet(sheet, profiles, resolutions):
    assert set(sheet['netkeiba_ancestors']) == set(sheet['umanity_ancestors']) == set(sheet['resolved_ancestors']) == POSITIONS
    assert sheet['record_hash'] == digest({k: sheet[k] for k in [
        'target', 'birth_year', 'netkeiba_ancestors', 'umanity_ancestors', 'resolved_ancestors', 'sources']})
    assert sheet['birth_year'] == int(sheet['target']['entry_reference_id'][:4])
    assert {s['origin_group'] for s in sheet['sources']} == {'NETKEIBA', 'UMANITY'}
    for source in sheet['sources']:
        assert source['source_class'] == 'BREEDING_DB'
        assert re.fullmatch(r'[a-f0-9]{64}', source['raw_sha256'])
        assert source['url'] and source['captured_at']
    observed_mismatches, observed_missing, aliases = [], [], []
    for path, net in sheet['netkeiba_ancestors'].items():
        um = sheet['umanity_ancestors'][path]
        names = {source_name(net['name'])} | {source_name(n) for n in profiles.get(net['id'], {}).get('aliases', [])}
        if um is None:
            observed_missing.append(path)
        elif source_name(um['name']) not in names or (
                net['birth_year'] and um['birth_year'] and net['birth_year'] != um['birth_year']):
            observed_mismatches.append({'path': path, 'netkeiba': net, 'umanity': um})
        elif source_name(um['name']) != source_name(net['name']):
            aliases.append({'path': path, 'profile_id': net['id']})
        selected = sheet['resolved_ancestors'][path]
        if net['id'] in resolutions and (resolutions[net['id']]['decision'] != 'CORRECTED_ANCESTOR_ID' or any(m['path'] == path for m in observed_mismatches)):
            decision = resolutions[net['id']]
            assert (selected['provider'], selected['id'], selected['name'], selected['birth_year']) == (
                decision['selected_provider'], decision['selected_id'], decision['name'], decision['birth_year'])
            assert decision['sources']
            if decision['selected_provider'] == 'UMANITY':
                assert um is not None and selected['id'] == um['id']
                assert selected['id'] != net['id']
        else:
            assert selected['provider'] == 'NETKEIBA' and selected['id'] == net['id']
            assert selected['name'] == net['name'] and selected['birth_year'] == net['birth_year']
            assert not any(m['path'] == path for m in observed_mismatches)
    assert sheet['mismatches'] == observed_mismatches
    assert sheet['secondary_missing_positions'] == observed_missing
    assert sheet['aliases_used'] == aliases
    for path, field in [('S', 'reported_sire'), ('DS', 'reported_damsire')]:
        report = sheet['target'][field]
        if report is not None:
            net = sheet['netkeiba_ancestors'][path]
            names = {source_name(net['name'])} | {source_name(n) for n in profiles.get(net['id'], {}).get('aliases', [])}
            assert source_name(report) in names


def check(repo='.'):
    root = Path(repo); directory = root / DIRECTORY
    imported = read(directory / 'import_summary.json')
    sheets = parts(directory, 'pedigree_evidence')
    profiles = {p['id']: p for p in read(directory / 'published_aliases.json')['records']}
    resolutions = {r['netkeiba_id']: r for r in read(directory / 'source_resolutions.json')['records']}
    for decision in resolutions.values():
        for source in decision['sources']:
            assert source['record_hash'] == digest(source['fields'])
    baseline = read(root / 'data/pedigree/reconciliations/2026-10-09-followup/missing_pedigrees.json')
    assert {r['target']['entry_reference_id'] for r in sheets} == {r['entry_reference_id'] for r in baseline['horses']}
    assert len(sheets) == imported['source_sheet_count'] == 1747
    for sheet in sheets:
        check_sheet(sheet, profiles, resolutions)
    relations = parts(directory, 'registry_relationships')
    assert len(relations) == len(sheets)
    by_sheet = {s['target']['entry_reference_id']: s for s in sheets}
    crosswalk = parts(directory, 'identity_crosswalk')
    mapping = {}
    registry = Registry(root / 'data/pedigree'); cutoff = imported['verification_cutoff']
    baseline_cutoff = read(root / 'data/condition_stats/definitions/prediction-period-jra-kizuna-deep-20261009.json')['data_cutoff']
    for row in crosswalk:
        assert row['record_hash'] == digest({k: v for k, v in row.items() if k != 'record_hash'})
        pair = row['provider'], row['provider_id']
        assert pair not in mapping
        mapping[pair] = row['horse_key']
        sheet = by_sheet[row['evidence_sheet']]
        source = next(s for s in sheet['sources'] if s['origin_group'] == row['provider'])
        assert (row['source_url'], row['source_raw_sha256']) == (source['url'], source['raw_sha256'])
        record = read(registry.path(row['horse_key']))
        names = {source_name(n) for n in [record['identity']['name']] + record['identity'].get('aliases', [])}
        assert names.intersection(source_name(n) for n in row['names'])
        if row['birth_year'] is not None:
            assert row['birth_year'] == record['identity']['birth_year']
        proof = row['mapping_proof']; method = proof['method']
        if method == 'NAME_BIRTH_YEAR_BOTH_PARENTS':
            for side, parent in proof['parent_keys'].items():
                fact = registry.fact(row['horse_key'], 'parent:' + side, baseline_cutoff)
                assert fact['status'] == 'VERIFIED' and fact['value'] == parent
        elif method == 'VERIFIED_CHILD_PARENT_AND_NAME':
            fact = registry.fact(proof['child'], 'parent:' + proof['side'], baseline_cutoff)
            assert fact['status'] == 'VERIFIED' and fact['value'] == row['horse_key']
        elif method == 'THIRD_SOURCE_PARENT_CORRECTION_AND_EXISTING_IDENTITY':
            assert proof['resolution_id'] == '000a02545a' and row['horse_key'] == 'jbis-0000339699'
        elif method == 'NEW_INDEPENDENT_PROVIDER_ID':
            assert row['horse_key'] == row['provider'].lower() + '-' + row['provider_id']
        else:
            assert method == 'SAME_SECONDARY_PROVIDER_ID_NAME_YEAR'
            assert proof['umanity_id']
    edges = {}
    for row in relations:
        sheet = by_sheet[row['entry_reference_id']]
        assert row['source_record_hash'] == sheet['record_hash']
        assert row['horse_key'] == mapping['NETKEIBA', row['entry_reference_id']]
        assert set(row['ancestor_keys']) == POSITIONS
        for path, selected in sheet['resolved_ancestors'].items():
            value = mapping[selected['provider'], selected['id']]
            assert row['ancestor_keys'][path] == value
            parent = row['horse_key'] if len(path) == 1 else row['ancestor_keys'][path[:-1]]
            pair = parent, path[-1]
            assert pair not in edges or edges[pair] == value
            edges[pair] = value
    for (key, side), value in edges.items():
        fact = registry.fact(key, 'parent:' + side, cutoff)
        assert fact['status'] == 'VERIFIED' and fact['value'] == value, (key, side, fact, value)
    summary = read(directory / 'scope_summary.json')
    manifest = read(root / summary['input_manifest'])
    old_manifest = read(root / 'data/condition_stats/inputs/prediction-period-jra-20260816-20261004.json')
    by_id = {r['entry_reference_id']: r for r in relations}
    assert len(manifest['races']) == len(old_manifest['races']) == 159
    assert manifest['all_runners_included'] is True
    ids, rows, statuses = set(), 0, Counter()
    for race, old in zip(manifest['races'], old_manifest['races']):
        assert {k: v for k, v in race.items() if k != 'runners'} == {k: v for k, v in old.items() if k != 'runners'}
        assert len(race['runners']) == len(old['runners'])
        for runner, before in zip(race['runners'], old['runners']):
            assert {k: v for k, v in runner.items() if k not in {'horse_key','identity_status'}} == {k: v for k, v in before.items() if k not in {'horse_key','identity_status'}}
            eid = runner['entry_reference_id']; ids.add(eid); rows += 1; statuses[runner['status']] += 1
            assert runner['horse_key'] == (by_id[eid]['horse_key'] if eid in by_id else before['horse_key'])
    assert len(ids) == summary['unique_horses'] == 2089
    assert rows == summary['entered_rows'] == 2182
    assert dict(statuses) == summary['result_statuses']
    assert statuses['FINISHED'] + statuses['DNF'] + statuses['DQ'] == summary['starters'] == 2177
    snapshot = verify(root, root / summary['condition_snapshot'])
    assert snapshot['completeness'] == summary['condition_snapshot_completeness'] == 'COMPLETE'
    assert snapshot['mode'] == summary['mode'] == 'REPLAY'
    assert summary['production_eligible'] is False
    for group in snapshot['groups'].values():
        assert group['cohorts']['UNKNOWN']['entries'] == 0
        assert group['coverage']['pedigree_coverage'] == 1
        cohort = group['cohorts']['MATCH']
        # 取消・除外は結果未確認ではなく、出走分母から外す。
        assert cohort['pending_results'] == 0
        assert group['coverage']['result_coverage'] == cohort['valid_starts'] / cohort['entries']
        assert sum(c['entries'] for c in group['cohorts'].values()) == rows
    training = read(directory / 'training_start_histories.json')
    for row in training['records']:
        fact = registry.fact(row['horse_key'], 'attribute:training_start_history', training['verification_cutoff'])
        assert fact['status'] == 'VERIFIED' and fact['value'] == row['history']
        country, reason = main_training_country(row['history'], training['verification_cutoff'])
        assert country == row['main_training_country']
        if country:
            assert country == 'US' and row['history']['complete'] is True
            assert len(row['history']['starts']) == row['history']['total_starts']
            for start in row['history']['starts']:
                source = start['source']
                assert source['record_hash'] == digest({'fields': source['fields'], 'affiliation_evidence': source['affiliation_evidence']})
                for affiliation in source['affiliation_evidence']:
                    if 'fields' in affiliation:
                        assert affiliation['record_hash'] == digest(affiliation['fields'])
        else:
            assert row['history']['complete'] is False
    return {'integrity': 'PASS', 'alternative_pedigrees': len(sheets), 'verified_positions': len(sheets) * 62,
            'jra_unique_horses': len(ids), 'entered_rows': rows, 'starters': 2177,
            'condition_snapshot': 'COMPLETE', 'production_eligible': False,
            'secondary_no_data_positions': imported['secondary_missing_positions'],
            'remaining_training_and_foreign_scope': 'PARTIAL'}


if __name__ == '__main__':
    print(json.dumps(check(), ensure_ascii=False, indent=2))
