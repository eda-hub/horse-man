"""旧記述の明示個体・親子経路・5代内包を再計算し、事実と仮説を分離する。"""
import argparse
import gzip
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from pedigree_registry import Registry, digest
from check_foreign_pedigree_review import norm
from import_legacy_subjects import check as check_subject_sources

BASE = Path('data/pedigree/reconciliations/2026-10-10-training-priority')
BATCH = BASE / 'legacy-fact-followup/batch-02'

def require(value, message):
    if not value:
        raise ValueError(message)

def read(path):
    path = Path(path)
    return json.loads(gzip.decompress(path.read_bytes()) if path.suffix == '.gz' else path.read_text())

def classify_paths(spec, positions, missing):
    require(spec['kind'] in {'ANCESTOR_POSITIONS', 'SIRE_CHAIN'}, 'explicit path kind')
    require(spec['depth'] == 5, 'five-generation bound')
    require(set(spec.get('prefix', '')) <= {'S', 'D'} and len(spec.get('prefix', '')) <= 5, 'explicit side prefix')
    if missing:
        return 'ANCESTRY_INCOMPLETE', []
    paths = [p for p in positions if len(p) <= 5 and p.startswith(spec.get('prefix', ''))]
    if spec['kind'] == 'SIRE_CHAIN':
        require(spec['prefix'] == 'S', 'explicit paternal chain')
        paths = [p for p in paths if set(p) == {'S'}]
    condition = spec.get('expected_generations')
    if condition == 'AT_LEAST_TWO_PATHS':
        match = len(paths) >= 2
    elif isinstance(condition, list):
        match = sorted(len(p) for p in paths) == sorted(condition)
    else:
        match = bool(paths) == spec.get('expected_present', True)
    return ('FACT_COMPONENT_MATCHED' if match else 'FACT_COMPONENT_CONTRADICTED'), paths

class Review:
    def __init__(self, root, cutoff):
        self.root = Path(root)
        self.cutoff = cutoff
        self.registry = Registry(self.root / 'data/pedigree')
        self.names = defaultdict(set)
        for path in self.registry.root.glob('horses/*.json'):
            record = read(path)
            identity = self.registry.identity_at(record, cutoff)
            if identity and identity.get('status') == 'RESOLVED':
                for name in [identity['name'], *identity.get('aliases', [])]:
                    self.names[norm(name)].add(record['horse_key'])
        self.subjects = defaultdict(set)
        manifest = read(self.root / 'data/condition_stats/inputs/prediction-period-jra-20260816-20261004-alternative.json')
        for race in manifest['races']:
            for row in race['runners']:
                self.subjects[norm(row['horse_name'])].add(row['horse_key'])

    def key(self, name, subject=False):
        keys = self.subjects.get(norm(name), set()) if subject else set()
        keys = keys or self.names.get(norm(name), set())
        return next(iter(keys)) if len(keys) == 1 else None, sorted(keys)

    def evaluate(self, spec):
        name = spec.get('subject_name', spec.get('horse'))
        key, candidates = self.key(name, True)
        if key is None:
            return {'subject_key': None, 'status': 'SUBJECT_IDENTITY_UNRESOLVED', 'observed': {'candidate_keys': candidates}, 'evidence': {}}
        if spec['kind'] == 'EXACT_PARENT_PATH':
            require(spec['path'] and set(spec['path']) <= {'S', 'D'} and len(spec['path']) <= 5, 'explicit parent path')
            fact = self.registry.edge(key, spec['path'], self.cutoff)
            if fact['status'] != 'VERIFIED':
                return {'subject_key': key, 'status': 'PARENT_PATH_UNCONFIRMED', 'observed': {'path_status': fact['status']}, 'evidence': {spec['path']: fact}}
            identity = self.registry.identity_at(read(self.registry.path(fact['value'])), self.cutoff)
            require(identity and identity['status'] == 'RESOLVED', 'resolved parent identity')
            matched = norm(spec['expected_name']) in {norm(n) for n in [identity['name'], *identity.get('aliases', [])]}
            return {'subject_key': key, 'status': 'FACT_COMPONENT_MATCHED' if matched else 'FACT_COMPONENT_CONTRADICTED', 'observed': {'horse_key': fact['value'], 'name': identity['name']}, 'evidence': {spec['path']: fact}}
        target, candidates = self.key(spec['expected_name'])
        if target is None:
            return {'subject_key': key, 'status': 'ANCESTOR_IDENTITY_UNRESOLVED', 'observed': {'candidate_keys': candidates}, 'evidence': {}}
        if spec['kind'] == 'SIRE_CHAIN':
            evidence = {'S' * depth: self.registry.edge(key, 'S' * depth, self.cutoff) for depth in range(1, 6)}
            missing = [{'path': p, 'status': f['status']} for p, f in evidence.items() if f['status'] != 'VERIFIED']
            positions = [p for p, f in evidence.items() if f['status'] == 'VERIFIED' and f['value'] == target]
            status, paths = classify_paths(spec, positions, missing)
            return {'subject_key': key, 'status': status, 'observed': {'ancestor_key': target, 'positions': paths, 'generations': sorted(len(p) for p in paths), **({'missing': missing} if missing else {})}, 'evidence': evidence}
        derived = self.registry.derive(key, [target], 5, self.cutoff)
        status, paths = classify_paths(spec, derived['containment'][target]['positions'], derived['missing'])
        observed = {'ancestor_key': target, 'positions': paths, 'generations': sorted(len(p) for p in paths)}
        if derived['missing']:
            observed['missing'] = derived['missing']
        return {'subject_key': key, 'status': status, 'observed': observed, 'evidence': derived['derived_from']}

def generate(root):
    root = Path(root)
    selection = read(root / BATCH / 'selection.json')
    cutoff = datetime.now(timezone.utc).isoformat()
    review = Review(root, cutoff)
    ledger_path = root / BASE / 'legacy-535-claim-review.json'
    claims = {c['claim_id']: c for c in read(ledger_path)['claims']}
    results = []
    for spec in selection['checks']:
        claim = claims[spec['claim_id']]
        results.append({'claim_id': claim['claim_id'], 'original_path': claim['path'], 'original_line': claim['line'], 'original_sha256': claim['source']['record_hash'], 'specification': spec, **review.evaluate(spec), 'data_cutoff': cutoff, 'mode': 'REPLAY', 'production_eligible': False, 'full_claim_status': 'UNVERIFIED', 'limitation': selection['limitations']})
    output = {'schema_version': 'legacy-fact-path-checks-v1', 'reviewed_at': cutoff, 'selection_sha256': hashlib.sha256((root / BATCH / 'selection.json').read_bytes()).hexdigest(), 'checks': results}
    previous = read(root / BASE / 'legacy-fact-followup/checks.json')['checks']
    progress = {'schema_version': 'legacy-fact-followup-batch-v1', 'baseline_head': selection['baseline_head'], 'reviewed_at': cutoff, 'checks': len(results), 'claims_touched': len({r['claim_id'] for r in results}), 'status_counts': dict(Counter(r['status'] for r in results)), 'previous_checks_preserved': len(previous), 'total_checks': len(previous) + len(results), 'total_claims_touched': len({r['claim_id'] for r in previous + results}), 'full_claim_promotions': 0, 'ledger_unchanged_sha256': hashlib.sha256(ledger_path.read_bytes()).hexdigest(), 'mode': 'REPLAY', 'production_eligible': False}
    for name, data in [('checks.json', output), ('progress.json', progress)]:
        raw = (json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode()
        if name == 'checks.json':
            (root / BATCH / (name + '.gz')).write_bytes(gzip.compress(raw, mtime=0))
        else:
            (root / BATCH / name).write_bytes(raw)
    return progress

def check(root=Path('.')):
    root = Path(root)
    check_subject_sources(root)
    ledger_path = root / BASE / 'legacy-535-claim-review.json'
    ledger = read(ledger_path)
    claims = {c['claim_id']: c for c in ledger['claims']}
    p = read(root / BASE / 'legacy-remaining-review/progress.json')
    source_bytes = (root / p['source_bundle_path']).read_bytes()
    require(hashlib.sha256(source_bytes).hexdigest() == p['source_bundle_sha256'], 'original archive hash')
    originals = json.loads(gzip.decompress(source_bytes))
    for original in originals.values():
        raw = original['content'].encode()
        require(hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest() == original['sha'], 'original Git blob hash')
    data = read(root / BATCH / 'checks.json.gz')
    selection_path = root / BATCH / 'selection.json'
    selection = read(selection_path)
    require(hashlib.sha256(selection_path.read_bytes()).hexdigest() == data['selection_sha256'], 'fixed selection hash')
    require(selection['mode'] == 'REPLAY' and selection['production_eligible'] is False, 'selection replay isolation')
    batches = [read(root / BASE / 'legacy-fact-followup/checks.json')['checks'], data['checks']]
    require([r['specification'] for r in batches[1]] == selection['checks'], 'all explicit selected checks')
    reviews = {}
    for row in batches[0] + batches[1]:
        claim = claims[row['claim_id']]
        original = originals[claim['path']]
        text = original['content'].splitlines()[claim['line'] - 1].strip()
        require(text == claim['original_text'].strip() and hashlib.sha256(claim['original_text'].encode()).hexdigest() == claim['source']['record_hash'], 'exact original line hash')
        require(row['original_path'] == claim['path'] and row['original_line'] == claim['line'] and row['original_sha256'] == claim['source']['record_hash'], 'exact original claim binding')
        require(row['mode'] == 'REPLAY' and row['production_eligible'] is False and row['full_claim_status'] == 'UNVERIFIED', 'no claim promotion')
        spec = row['specification']
        context = [claim['original_text']]
        for number in spec.get('context_lines', []):
            require(type(number) is int and 1 <= number <= len(original['content'].splitlines()), 'bounded original context')
            context.append(original['content'].splitlines()[number - 1])
        if 'subject_name' in spec:
            require(norm(spec['subject_name']) in norm(' '.join(context)), 'explicit individual in original context')
        cutoff = row['data_cutoff']
        if cutoff not in reviews:
            reviews[cutoff] = Review(root, cutoff)
        observed = reviews[cutoff].evaluate(row['specification'])
        require(all(row[field] == observed[field] for field in ['subject_key', 'status', 'observed', 'evidence']), 'fact conclusion and source revisions recomputation')
    progress = read(root / BATCH / 'progress.json')
    require(progress['checks'] == len(batches[1]) and progress['claims_touched'] == len({r['claim_id'] for r in batches[1]}), 'batch counts')
    require(progress['status_counts'] == dict(Counter(r['status'] for r in batches[1])), 'batch status counts')
    require(progress['previous_checks_preserved'] == len(batches[0]) and progress['total_checks'] == sum(map(len, batches)) and progress['total_claims_touched'] == len({r['claim_id'] for r in batches[0] + batches[1]}), 'cumulative unique claim scope')
    require(progress['full_claim_promotions'] == 0 and progress['ledger_unchanged_sha256'] == hashlib.sha256(ledger_path.read_bytes()).hexdigest(), 'legacy ledger preserved')
    queue = read(root / BATCH / 'remaining-queue.json')
    classified = [c for path in sorted((root / BASE / 'legacy-remaining-review').glob('batch-*.json')) for c in read(path)['claims']]
    touched = Counter(r['claim_id'] for r in batches[0] + batches[1])
    require(queue['mode'] == 'REPLAY' and queue['production_eligible'] is False, 'remaining queue isolation')
    require([r['claim_id'] for r in queue['rows']] == [c['claim_id'] for c in classified] and len(classified) == 482, 'all 482 remaining claims preserved in order')
    for row, claim in zip(queue['rows'], classified):
        require(all(row[f] == claim[f] for f in ['path', 'line', 'original_text_sha256', 'categories']) and row['fact_checks'] == touched[row['claim_id']] and row['full_claim_status'] == 'UNVERIFIED', 'remaining source and partial fact scope')
    require(queue['remaining_full_claims'] == 482 and queue['partly_fact_checked_claims'] == sum(bool(touched[c['claim_id']]) for c in classified) and queue['no_followup_fact_checks'] == sum(not touched[c['claim_id']] for c in classified), 'remaining queue counts')
    return progress

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--generate', action='store_true')
    args = parser.parse_args()
    print(json.dumps(generate(Path('.')) if args.generate else check(), ensure_ascii=False))
