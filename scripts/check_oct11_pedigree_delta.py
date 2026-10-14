"""11日差分17番の固定対象・原HTML・独立ID・追記時点を再検証する。"""
import argparse
import copy
import gzip
import hashlib
import json
from pathlib import Path

from pedigree_registry import Registry, digest, dt, read
from check_foreign_pedigree_review import Document, norm, parse_jbis

BASE = Path('data/pedigree/reconciliations/2026-10-11-delta')


def check(root=Path('.')):
    root = Path(root)
    directory = root / BASE
    completion = read(directory / 'pedigrees/completion.json')
    if completion is None:
        return {'status': 'NOT_REGISTERED', 'target_rows': 0}
    evidence = read(directory / 'pedigrees/source-reconciliation.json')
    identities = {e['entry_id']: e for e in read(directory / 'identities/completion.json')['entries']}
    inventory = read(directory / 'inventory.json')
    queue = list(inventory['queued_tasks']['17'])
    for venue in ['tokyo', 'kyoto']:
        for number in range(6, 13):
            checkpoint = read(directory / 'results' / f'{venue}-{number:02d}' / 'checkpoint.json')
            queue.extend(checkpoint.get('append_queues', {}).get('17', []))
    assert len(queue) == 93
    assert completion['completed_subtasks'] == [b['subtask_id'] for b in queue]
    assert completion['production_eligible'] is False and completion['usage'] == 'REPLAY_ONLY'
    cutoff = completion['data_cutoff']
    baseline = completion['baseline_cutoff']
    assert dt(baseline) < dt(cutoff)
    assert evidence['data_cutoff'] == cutoff and evidence['baseline_cutoff'] == baseline
    assert evidence['production_eligible'] is False
    registry = Registry(root / 'data/pedigree')
    source_rows = {}
    source_hashes = set()
    crosswalks = {(x['entry_id'], x['path']): x for x in evidence.get('provider_position_crosswalks', [])}
    for sheet in evidence['sheets']:
        entry = identities[sheet['entry_id']]
        assert entry['horse_key'] == sheet['horse_key']
        source = sheet['source']
        assert source['status'] == 200 and dt(baseline) <= dt(source['captured_at']) <= dt(cutoff)
        sid = entry['provider_ids']['JBIS']
        assert source['url'] == source['final_url'] == f'https://www.jbis.or.jp/horse/{sid}/pedigree/'
        body = gzip.decompress((root / source['path']).read_bytes())
        assert len(body) == source['bytes'] and hashlib.sha256(body).hexdigest() == source['raw_sha256']
        document = Document(body, 'utf-8').root
        assert any(norm(h.text_content()) == norm(entry['horse_name']) for h in document.walk('h1'))
        ancestors = parse_jbis(body)
        assert ancestors == sheet['ancestors'] and len(ancestors) == 62
        for side in 'SD':
            assert ancestors[side]['id'] == entry['parents'][side]['id']
        for position, ancestor in ancestors.items():
            record = read(registry.path(sheet['ancestor_keys'][position]))
            identity = registry.identity_at(record, cutoff)
            if identity['external_ids'].get('JBIS') != ancestor['id']:
                proof = crosswalks[(sheet['entry_id'], position)]
                assert proof['horse_key'] == sheet['ancestor_keys'][position] and proof['jbis_id'] == ancestor['id']
                assert proof['existing_identity_hash'] == digest(identity)
                assert proof['source_raw_sha256'] == source['raw_sha256']
                prior = proof['prior_graph_proof']
                assert prior['key'] == proof['horse_key'] and prior['jbis_id'] == ancestor['id']
                assert prior['existing'] == identity and registry.identity_at(record, baseline) == identity
                assert norm(prior['source_ancestor']['name']) == norm(ancestor['name'])
                assert prior['source_ancestor']['birth_year'] == ancestor['birth_year']
            assert identity['birth_year'] in (None, ancestor['birth_year'])
            assert norm(ancestor['name']) in {norm(n) for n in [identity['name']] + identity.get('aliases', [])}
        assert sheet['entry_id'] not in source_rows
        source_rows[sheet['entry_id']] = sheet
        source_hashes.add(source['raw_sha256'])
    for proof in crosswalks.values():
        prior = proof['prior_graph_proof']
        prior_sheet = source_rows[prior['source_entry']]
        position = prior['path']
        parent_key = (prior_sheet['horse_key'] if len(position) == 1
                      else prior_sheet['ancestor_keys'][position[:-1]])
        old_edge = registry.fact(parent_key, 'parent:' + position[-1], baseline)
        assert old_edge['status'] == 'VERIFIED' and old_edge['value'] == prior['key']
        assert prior_sheet['ancestors'][position]['id'] == prior['jbis_id']
    rows = []
    seen = set()
    for queued in queue:
        directory_batch = directory / 'pedigrees' / queued['subtask_id']
        batch = read(directory_batch / 'pedigrees.json')
        checkpoint = read(directory_batch / 'checkpoint.json')
        verification = read(directory_batch / 'verification.json')
        targets = [t if isinstance(t, str) else t['entry_id'] for t in queued['targets']]
        assert batch['targets'] == checkpoint['targets'] == targets
        assert [r['entry_id'] for r in batch['rows']] == targets
        assert batch['status'] == checkpoint['status'] == 'COMPLETED' and verification['status'] == 'PASS'
        assert batch['data_cutoff'] == checkpoint['data_cutoff'] == cutoff
        assert batch['production_eligible'] is False and batch['usage'] == 'REPLAY_ONLY'
        assert digest(batch['rows']) == batch['record_hash'] == checkpoint['record_hash'] == verification['record_hash']
        assert batch['positions_checked'] == verification['positions_checked'] == 62 * len(targets)
        for row in batch['rows']:
            assert row['entry_id'] not in seen
            seen.add(row['entry_id'])
            entry = identities[row['entry_id']]
            assert row['horse_key'] == entry['horse_key'] and row['horse_name'] == entry['horse_name']
            ancestry = registry.ancestry(row['horse_key'], 5, cutoff)
            assert not ancestry['missing'] and len(ancestry['paths']) == 62
            expected = {p: {'horse_key': f['value'], 'revision_id': f['revision_id'], 'content_hash': f['content_hash']}
                        for p, f in ancestry['paths'].items()}
            assert row['positions'] == expected and row['status'] == 'VERIFIED_5_GENERATIONS'
            if row['entry_id'] in source_rows:
                assert row['mode'] == 'ORIGINAL_SOURCE_REGISTERED'
                assert {p: x['horse_key'] for p, x in row['positions'].items()} == source_rows[row['entry_id']]['ancestor_keys']
            else:
                assert row['mode'] == 'EXISTING_REGISTRY_REUSED'
                assert not registry.ancestry(row['horse_key'], 5, baseline)['missing']
        rows.extend(batch['rows'])
    added_individuals = 0
    added_revisions = 0
    for receipt in evidence['write_receipts']:
        record = copy.deepcopy(read(registry.path(receipt['horse_key'])))
        record['revisions'] = record['revisions'][:receipt['after_revision_count']]
        assert digest(record) == receipt['after_record_hash']
        count_before = len(receipt['before_revision_hashes'])
        assert [r['content_hash'] for r in record['revisions'][:count_before]] == receipt['before_revision_hashes']
        appended = record['revisions'][count_before:]
        assert [r['revision_id'] for r in appended] == receipt['added_revision_ids']
        if receipt['new_identity']:
            added_individuals += 1
            assert receipt['before_record_hash'] is None and registry.identity_at(record, baseline) is None
        else:
            before = copy.deepcopy(record)
            before['revisions'] = before['revisions'][:count_before]
            assert digest(before) == receipt['before_record_hash']
        for revision in appended:
            registry.validate_fact(revision)
            assert revision['source']['record_hash'] in source_hashes
            assert dt(baseline) <= dt(revision['captured_at']) <= dt(cutoff)
            assert registry.fact(receipt['horse_key'], revision['field'], baseline).get('revision_id') != revision['revision_id']
        added_revisions += len(appended)
    assert len(rows) == len(seen) == completion['target_rows'] == 184
    assert len(rows) * 62 == completion['positions_checked'] == 11408
    assert digest(rows) == completion['record_hash']
    assert len(source_rows) == completion['source_pedigrees_registered'] == 162
    assert len(rows) - len(source_rows) == completion['existing_pedigrees_reused'] == 22
    assert added_individuals == completion['registry_individuals_added']
    assert added_revisions == completion['registry_parent_revisions_added']
    assert completion['status'] == 'COMPLETED' and completion['unresolved_rows'] == 0
    return {'status': 'PASS', 'batches': 93, 'target_rows': 184, 'positions_checked': 11408,
            'source_pedigrees': 162, 'reused_pedigrees': 22, 'new_individuals': added_individuals,
            'new_parent_revisions': added_revisions, 'production_eligible': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', default='.')
    args = parser.parse_args()
    print(json.dumps(check(Path(args.repo)), ensure_ascii=False, indent=2))
