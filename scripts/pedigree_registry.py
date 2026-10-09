#!/usr/bin/env python3
"""Git-backed pedigree facts. No network or prediction/snapshot writes.

Candidates require explicit human/source verification; VERIFIED is not inferred
from AI text or repository history. All timestamps are timezone aware.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import subprocess
import unicodedata

SCHEMA = 'pedigree-registry-v1'
SOURCES = {'OFFICIAL_JRA_VAN', 'OFFICIAL_JRA', 'BREEDING_DB', 'MEDIA_ORIGINAL',
           'WEB_AGGREGATOR', 'LEGACY_REPOSITORY'}
STATUSES = {'VERIFIED', 'UNVERIFIED', 'CONFLICT'}
KEY = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,119}$')


def stamp():
    return datetime.now(timezone.utc).isoformat()


def dt(value):
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('timezone required')
    return result


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':')).encode()).hexdigest()


def norm(value):
    return unicodedata.normalize('NFKC', value).strip().casefold()


def safe(value):
    if not isinstance(value, str) or not KEY.fullmatch(value):
        raise ValueError('invalid key')
    return value


def read(path, default=None):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default


def atomic(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix='.pedigree-')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
        if read(path) != value:
            raise OSError('readback mismatch')
    finally:
        if os.path.exists(name):
            os.unlink(name)


class Registry:
    def __init__(self, root):
        self.root = Path(root)

    @contextmanager
    def writer(self):
        self.root.mkdir(parents=True, exist_ok=True)
        with (self.root / '.writer.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            if read(self.root / 'writer.json', {'writer': 'JSON'})['writer'] != 'JSON':
                raise ValueError('JSON writer disabled after DB migration')
            yield

    def path(self, key):
        return self.root / 'horses' / (safe(key) + '.json')

    def records(self):
        return [read(p) for p in sorted((self.root / 'horses').glob('*.json'))]

    @staticmethod
    def identity_at(record, cutoff=None):
        """Use identity only after its first observation, and replay later changes."""
        if cutoff is None:
            return record['identity']
        point = dt(cutoff)
        first_observed = record.get('identity_observed_at')
        # Records without authenticated initial observation time fail closed.
        # Do not silently treat the latest identity as historical evidence.
        if not first_observed or dt(first_observed) > point:
            return None
        identity = record['identity']
        for event in reversed(record.get('identity_revisions', [])):
            if dt(event['at']) > point:
                identity = event['before']
            else:
                break
        if identity['status'] == 'RESOLVED':
            confirmed = record.get('identity_confirmed_at')
            if not confirmed or dt(confirmed) > point:
                return None
        return identity

    def search(self, query, cutoff=None):
        """Search canonical identity and aliases as of cutoff (if supplied)."""
        if cutoff is not None:
            dt(cutoff)
        matches = []
        for record in self.records():
            identity = self.identity_at(record, cutoff)
            if identity is None:
                continue
            names = [identity['name']] + identity.get('aliases', [])
            ids = [record['horse_key']] + list(identity.get('external_ids', {}).values())
            if query in ids or any(norm(query) == norm(n) for n in names):
                matches.append({'horse_key': record['horse_key'], 'identity': identity})
        return {'status': 'RESOLVED' if len(matches) == 1 and
                matches[0]['identity']['status'] == 'RESOLVED' else 'IDENTITY_UNRESOLVED',
                'matches': matches}

    def validate_identity(self, identity, horse_key=None, records=None):
        if identity['status'] not in {'RESOLVED', 'IDENTITY_UNRESOLVED'} or not identity['name']:
            raise ValueError('invalid identity')
        if not isinstance(identity.get('external_ids', {}), dict) or any(not isinstance(v, str) or not v for v in identity.get('external_ids', {}).values()):
            raise ValueError('external_ids must be provider -> id')
        if identity['status'] == 'RESOLVED':
            proof = identity.get('identity_evidence', {})
            if not proof.get('source') or not proof.get('record_key'):
                raise ValueError('identity evidence required')
            if not identity.get('external_ids') and not all(identity.get(k) for k in
                    ('birth_year', 'country', 'parents')):
                raise ValueError('local identity requires birth year, country and parents')
        for other in self.records() if records is None else records:
            if other['horse_key'] == horse_key:
                continue
            for provider, value in identity.get('external_ids', {}).items():
                if other['identity'].get('external_ids', {}).get(provider) == value:
                    raise ValueError('external ID already belongs to another horse')

    def validate_fact(self, fact):
        field = fact['field']
        if not (re.fullmatch(r'parent:[SD]{1,10}', field) or
                field in {'attribute:birth_country', 'attribute:training_country', 'attribute:training_start_history', 'attribute:sex'}):
            raise ValueError('only pedigree edges and ancestor attributes are facts')
        if fact['status'] not in STATUSES:
            raise ValueError('invalid fact status')
        source = fact['source']
        for k in ('source_class', 'origin_group', 'acquisition_method', 'record_hash'):
            if not source.get(k):
                raise ValueError('source provenance incomplete')
        if source['source_class'] not in SOURCES or not (source.get('url') or source.get('record_key')):
            raise ValueError('source reference required')
        if not re.fullmatch(r'[0-9a-f]{64}', source['record_hash']):
            raise ValueError('source record SHA256 required')
        observed, captured = dt(fact['first_observed_at']), dt(fact['captured_at'])
        if observed > captured or captured > dt(stamp()):
            raise ValueError('invalid observation/capture ordering')
        if source.get('provider_timestamp'):
            dt(source['provider_timestamp'])
        if fact['status'] == 'VERIFIED':
            if source['source_class'] == 'LEGACY_REPOSITORY':
                raise ValueError('legacy claims require original source verification')
            check = fact.get('verification', {})
            if not all(check.get(k) is True for k in
                       ('identity_checked', 'source_checked', 'relationship_checked')) or not check.get('reviewed_by'):
                raise ValueError('explicit verification required')
        if field.startswith('parent:'):
            ancestor = read(self.path(fact['value']))
            if not ancestor:
                raise ValueError('ancestor must have an independent record')
            if fact['status'] == 'VERIFIED' and ancestor['identity']['status'] != 'RESOLVED':
                raise ValueError('ancestor identity unresolved')
        elif field == 'attribute:training_start_history':
            value = fact['value']
            if not isinstance(value, dict) or type(value.get('complete')) is not bool or \
                    type(value.get('total_starts')) is not int or value['total_starts'] < 0 or \
                    not isinstance(value.get('starts'), list):
                raise ValueError('training start history object required')
        elif not isinstance(fact['value'], str) or not fact['value']:
            raise ValueError('attribute must be a nonempty string')

    def save(self, candidate, expected_hash=None):
        """CAS + single writer. Conflicting values become append-only CONFLICTs."""
        if candidate.get('schema_version') != SCHEMA:
            raise ValueError('unsupported schema')
        key = safe(candidate['horse_key'])
        with self.writer():
            path = self.path(key)
            old = read(path)
            if old and expected_hash != digest(old):
                raise ValueError('CONCURRENT_UPDATE: reread and merge fields')
            if not old and expected_hash is not None:
                raise ValueError('CONCURRENT_UPDATE: record does not exist')
            identity = candidate['identity']
            self.validate_identity(identity, key)
            if old and old['identity'] != identity:
                raise ValueError('identity cannot be silently changed')
            # The initial identity cannot precede the actual first capture.
            # Historical fact timestamps do not establish when identity was known.
            initial_at = stamp()
            record = old or {'schema_version': SCHEMA, 'horse_key': key,
                             'identity': identity, 'initial_identity': json.loads(json.dumps(identity)),
                             'identity_observed_at': initial_at,
                             'identity_confirmed_at': initial_at if identity['status'] == 'RESOLVED' else None,
                             'revisions': []}
            added = []
            for input_fact in candidate.get('facts', []):
                fact = json.loads(json.dumps(input_fact))
                self.validate_fact(fact)
                if fact['field'].startswith('parent:') and fact['value'] == key:
                    raise ValueError('self-parent forbidden')
                signature = digest({k: fact.get(k) for k in
                                    ('field', 'value', 'source', 'status', 'supersedes')})
                if any(r['input_hash'] == signature for r in record['revisions']):
                    continue
                prior = [r for r in record['revisions'] if r['field'] == fact['field']]
                supersedes = fact.get('supersedes', [])
                if supersedes:
                    if set(supersedes) != {r['revision_id'] for r in self.active(prior, stamp())}:
                        raise ValueError('correction must supersede all current competing revisions')
                    if not fact.get('correction_reason') or fact['status'] != 'VERIFIED' or fact['source']['source_class'] not in {'OFFICIAL_JRA', 'OFFICIAL_JRA_VAN', 'BREEDING_DB'}:
                        raise ValueError('correction requires authority and reason')
                    if any(dt(fact['first_observed_at']) < dt(r['first_observed_at']) for r in prior):
                        raise ValueError('correction cannot precede prior observation')
                elif prior and dt(fact['first_observed_at']) < max(dt(r['first_observed_at']) for r in prior):
                    raise ValueError('new observations cannot be backdated before prior revisions')
                elif any(r['value'] != fact['value'] for r in self.active(prior, stamp())):
                    fact['status'] = 'CONFLICT'
                if fact['field'] in {'parent:S', 'parent:D'}:
                    self.check_cycle(key, fact['value'])
                fact.update(revision_id='rev-' + signature[:24], input_hash=signature,
                            previous_revision=prior[-1]['revision_id'] if prior else None,
                            saved_at=stamp())
                fact['content_hash'] = digest(fact)
                record['revisions'].append(fact)
                added.append(fact['revision_id'])
            atomic(path, record)
            # Index failure is harmless: the records remain the canonical truth.
            self.reindex()
            return {'horse_key': key, 'content_hash': digest(record), 'added_revisions': added,
                    'persistence': 'LOCAL_READBACK_VERIFIED', 'git_persistence': 'UNCONFIRMED',
                    'snapshot_persistence': 'NOT_EVALUATED', 'verified_at': stamp()}

    def reindex(self):
        """Rebuild disposable alias index from canonical horse records."""
        aliases = {}
        for horse in self.records():
            for name in [horse['identity']['name']] + horse['identity'].get('aliases', []):
                aliases.setdefault(norm(name), []).append(horse['horse_key'])
        atomic(self.root / 'aliases.json', {'schema_version': SCHEMA, 'aliases': aliases})

    def update_identity(self, candidate, expected_hash, reason, reviewed_by):
        """Explicit, CAS-protected identity enrichment with append-only evidence history."""
        if candidate.get('schema_version') != SCHEMA:
            raise ValueError('unsupported schema')
        key = safe(candidate['horse_key'])
        if candidate.get('facts'):
            raise ValueError('identity update cannot modify pedigree facts')
        if not isinstance(reason, str) or not reason.strip() or not isinstance(reviewed_by, str) or not reviewed_by.strip():
            raise ValueError('identity update requires a reason and reviewer')
        with self.writer():
            path = self.path(key)
            record = read(path)
            if record is None or expected_hash is None or digest(record) != expected_hash:
                raise ValueError('CONCURRENT_UPDATE: identity update requires current record hash')
            identity = candidate['identity']
            self.validate_identity(identity, key)
            before = record['identity']
            if before == identity:
                return {'horse_key': key, 'content_hash': digest(record),
                        'identity_updated': False, 'persistence': 'LOCAL_READBACK_VERIFIED'}
            if before['status'] == 'RESOLVED' and identity['status'] != 'RESOLVED':
                raise ValueError('resolved identity cannot be downgraded')
            for provider, value in before.get('external_ids', {}).items():
                if identity.get('external_ids', {}).get(provider) != value:
                    raise ValueError('existing external ID cannot be silently replaced')
            changed_at = stamp()
            if not record.get('identity_observed_at'):
                raise ValueError('initial identity observation missing; explicit migration required')
            if dt(changed_at) < dt(record['identity_observed_at']):
                raise ValueError('identity update cannot precede initial identity observation')
            if record.get('identity_revisions') and dt(changed_at) < dt(record['identity_revisions'][-1]['at']):
                raise ValueError('identity update cannot precede earlier identity evidence')
            event = {'before': before, 'after': identity, 'at': changed_at,
                     'reason': reason.strip(), 'reviewed_by': reviewed_by.strip()}
            event['event_hash'] = digest(event)
            record.setdefault('identity_revisions', []).append(event)
            record['identity'] = identity
            if before['status'] != 'RESOLVED' and identity['status'] == 'RESOLVED':
                if record.get('identity_confirmed_at') is not None:
                    raise ValueError('identity confirmation timestamp inconsistent')
                record['identity_confirmed_at'] = changed_at
            atomic(path, record)
            self.reindex()
            return {'horse_key': key, 'content_hash': digest(record),
                    'identity_updated': True, 'identity_revision_hash': event['event_hash'],
                    'persistence': 'LOCAL_READBACK_VERIFIED',
                    'git_persistence': 'UNCONFIRMED', 'snapshot_persistence': 'NOT_EVALUATED'}

    def check_cycle(self, child, ancestor):
        visited, pending = set(), [ancestor]
        while pending:
            current = pending.pop()
            if current == child:
                raise ValueError('pedigree cycle forbidden')
            if current in visited:
                continue
            visited.add(current)
            record = read(self.path(current), {'revisions': []})
            pending.extend(r['value'] for r in record['revisions']
                           if r['field'] in {'parent:S', 'parent:D'} and r['status'] == 'VERIFIED')

    @staticmethod
    def active(revisions, cutoff):
        eligible = [r for r in revisions if dt(r['first_observed_at']) <= dt(cutoff)]
        retired = {s for r in eligible for s in r.get('supersedes', [])}
        return [r for r in eligible if r['revision_id'] not in retired]

    def fact(self, key, field, cutoff):
        record = read(self.path(key))
        if not record:
            return {'status': 'NOT_FOUND'}
        identity = self.identity_at(record, cutoff)
        if identity is None or identity['status'] != 'RESOLVED':
            return {'status': 'IDENTITY_UNRESOLVED'}
        revisions = self.active([r for r in record['revisions'] if r['field'] == field], cutoff)
        if not revisions:
            return {'status': 'NOT_FOUND'}
        if len({digest(r['value']) for r in revisions}) > 1 or any(r['status'] == 'CONFLICT' for r in revisions):
            return {'status': 'CONFLICT', 'candidates': revisions}
        verified = [r for r in revisions if r['status'] == 'VERIFIED']
        if not verified:
            return {'status': 'UNVERIFIED', 'candidates': revisions}
        r = max(verified, key=lambda r: dt(r['first_observed_at']))
        result = {'status': 'VERIFIED', 'value': r['value'], 'revision_id': r['revision_id'],
                  'content_hash': r['content_hash'], 'first_observed_at': r['first_observed_at'],
                  'source': r['source'], 'horse_key': key, 'field': field,
                  'identity_evidence': identity.get('identity_evidence')}
        if field.startswith('parent:'):
            ancestor = read(self.path(r['value']))
            ancestor_identity = self.identity_at(ancestor, cutoff) if ancestor else None
            if not ancestor_identity or ancestor_identity['status'] != 'RESOLVED':
                return {'status': 'IDENTITY_UNRESOLVED', 'candidates': revisions}
            result['ancestor_identity_evidence'] = ancestor_identity.get('identity_evidence')
        return result

    def edge(self, key, path, cutoff):
        direct = self.fact(key, 'parent:' + path, cutoff)
        if len(path) == 1:
            return direct
        parent = self.edge(key, path[:-1], cutoff)
        if parent['status'] != 'VERIFIED':
            # A direct long-path claim cannot override a conflicting/unresolved
            # intermediate ancestor identity or relationship.
            if parent['status'] in {'CONFLICT', 'UNVERIFIED', 'IDENTITY_UNRESOLVED'}:
                return {'status': parent['status'], 'candidates': [direct, parent]}
            return direct if direct['status'] != 'NOT_FOUND' else parent
        result = self.fact(parent['value'], 'parent:' + path[-1], cutoff)
        if direct['status'] != 'NOT_FOUND':
            if result['status'] == 'CONFLICT':
                return {'status': 'CONFLICT', 'candidates': [direct, result]}
            if direct['status'] == 'VERIFIED':
                if result['status'] == 'VERIFIED' and direct['value'] != result['value']:
                    return {'status': 'CONFLICT', 'candidates': [direct, result]}
                if result['status'] in {'UNVERIFIED', 'IDENTITY_UNRESOLVED'}:
                    return {'status': result['status'], 'candidates': [direct, result]}
            return direct
        if result['status'] == 'VERIFIED':
            result = dict(result, dependencies=[parent, result.copy()])
        return result

    def ancestry(self, key, depth, cutoff):
        if not 1 <= depth <= 10:
            raise ValueError('depth must be between 1 and 10')
        paths = ['']
        found, missing = {}, []
        for _ in range(depth):
            paths = [p + side for p in paths for side in 'SD']
            for p in paths:
                f = self.edge(key, p, cutoff)
                if f['status'] == 'VERIFIED':
                    found[p] = f
                else:
                    missing.append({'path': p, 'status': f['status']})
        return {'paths': found, 'missing': missing, 'depth': depth,
                'status': 'VERIFIED' if not missing else 'PARTIAL'}

    def derive(self, key, ancestors, depth, cutoff, taxonomy_version=None):
        tree = self.ancestry(key, depth, cutoff)
        taxonomy = None
        if taxonomy_version:
            taxonomy = read(self.root / 'taxonomies' / (safe(taxonomy_version) + '.json'))
            if not taxonomy or taxonomy.get('schema_version') != SCHEMA or not taxonomy.get('source') or taxonomy.get('version') != taxonomy_version:
                raise ValueError('taxonomy version/source unavailable')
            if dt(taxonomy['first_observed_at']) > dt(cutoff):
                raise ValueError('taxonomy observed after cutoff')
        results = {}
        for ancestor in ancestors:
            safe(ancestor)
            positions = [p for p, f in tree['paths'].items() if f['value'] == ancestor]
            results[ancestor] = {'status': 'PRESENT' if positions else
                                 'ABSENT_WITHIN_SCOPE' if not tree['missing'] else 'UNKNOWN',
                                 'positions': positions, 'generations': [len(p) for p in positions]}
        lines = {}
        if taxonomy:
            for role, prefix in [('sire_line', 'S'), ('dam_sire_line', 'DS')]:
                chain = [prefix + 'S' * n for n in range(depth - len(prefix) + 1)]
                matches = [(p, taxonomy['ancestor_lines'][tree['paths'][p]['value']]) for p in chain
                           if p in tree['paths'] and tree['paths'][p]['value'] in taxonomy['ancestor_lines']]
                lines[role] = {'status': 'VERIFIED' if matches else 'UNKNOWN',
                               'line': matches[0][1] if matches else None,
                               'path': matches[0][0] if matches else None}
        return {'schema_version': SCHEMA, 'horse_key': key, 'data_cutoff': cutoff,
                'calculator_version': 'pedigree-paths-v1', 'taxonomy_version': taxonomy_version,
                'taxonomy_hash': digest(taxonomy) if taxonomy else None, 'depth': depth,
                'containment': results, 'lines': lines, 'derived_from': tree['paths'],
                'coverage': len(tree['paths']) / (2 ** (depth + 1) - 2), 'missing': tree['missing']}

    def plan(self, request, force=False):
        if request.get('schema_version') != SCHEMA:
            raise ValueError('unsupported request schema')
        request_id = safe(request['request_id'])
        dt(request['data_cutoff'])
        key = request.get('horse_key')
        identity = self.search(key or request['query'], request['data_cutoff'])
        results, missing = {}, []
        if identity['status'] != 'RESOLVED':
            missing.append({'item': 'identity', 'status': 'IDENTITY_UNRESOLVED'})
        else:
            key = identity['matches'][0]['horse_key']
            for field in request.get('fields', []):
                if not (re.fullmatch(r'parent:[SD]{1,10}', field) or field in {'attribute:birth_country', 'attribute:training_country', 'attribute:training_start_history', 'attribute:sex'}):
                    raise ValueError('unsupported fact field; statistics and scores use a separate API')
                if field.startswith('parent:'):
                    if not re.fullmatch(r'parent:[SD]{1,10}', field):
                        raise ValueError('invalid parent path')
                    f = self.edge(key, field.split(':')[1], request['data_cutoff'])
                else:
                    f = self.fact(key, field, request['data_cutoff'])
                results[field] = f
                if f['status'] != 'VERIFIED':
                    missing.append({'item': field, 'status': f['status']})
            if request.get('ancestors') or request.get('taxonomy_version'):
                derived = self.derive(key, request.get('ancestors', []), request.get('depth', 5),
                                      request['data_cutoff'], request.get('taxonomy_version'))
                results['derived'] = derived
                missing.extend({'item': 'parent:' + m['path'], 'status': m['status']}
                               for m in derived['missing'])
        # Same item appears once even if required by both explicit field and derivation.
        missing = list({m['item']: m for m in missing}.values())
        request_hash = digest({k: v for k, v in request.items() if k != 'source_key'})
        with self.writer():
            path = self.root / 'research' / (request_id + '.json')
            old = read(path, {})
            if old and old.get('request_hash') != request_hash:
                raise ValueError('request ID already used for different requirements')
            failures = old.get('failures', [])
            now = dt(stamp())
            budget = request.get('budget_seconds', 60)
            if not isinstance(budget, (int, float)) or budget <= 0:
                raise ValueError('positive finite request budget required')
            # --force bypasses only backoff, not a consumed time budget.
            started_at = old.get('started_at') or now.isoformat()
            deadline_at = (dt(started_at) + timedelta(seconds=budget)).isoformat()
            for item in missing:
                recent = [f for f in failures if f['item'] == item['item'] and
                          f.get('source_key') == request.get('source_key', 'manual')]
                # Exhaustion is persistent, including with --force or after a
                # backoff deadline. A different source_key has its own budget.
                if recent and (len(recent) >= recent[-1].get('max_retries', 2) + 1 or
                               (recent[-1].get('retry_exhausted') and
                                not recent[-1].get('budget_exhausted'))):
                    item.update(retry_state='RETRY_EXHAUSTED', last_failure=recent[-1]['status'])
                elif (now >= dt(deadline_at) or
                      (recent and recent[-1].get('budget_exhausted'))):
                    item.update(retry_state='BUDGET_EXHAUSTED')
                elif recent and not force and dt(recent[-1]['next_retry_at']) > now:
                    item.update(retry_state='DEFERRED', next_retry_at=recent[-1]['next_retry_at'],
                                last_failure=recent[-1]['status'])
            result = {'schema_version': SCHEMA, 'request': request, 'request_hash': request_hash,
                      'results': results, 'missing': missing, 'failures': failures,
                      'started_at': started_at, 'deadline_at': deadline_at,
                      'status': 'VERIFIED' if not missing else 'PARTIAL',
                      'metrics': {'reused_fields': sum(f.get('status') == 'VERIFIED' for f in results.values()),
                                  'missing_items': len(missing), 'recorded_failure_attempts': len(failures), 'external_queries': 0},
                      'persistence': 'LOCAL_READBACK_VERIFIED', 'snapshot_persistence': 'NOT_EVALUATED'}
            atomic(path, result)
            return result

    def failure(self, request_id, item, status, source_key='manual', max_retries=2,
                not_found_hours=24, budget_seconds=60):
        if status not in {'NOT_FOUND', 'SOURCE_ERROR', 'SAVE_ERROR'}:
            raise ValueError('invalid failure status')
        if (not isinstance(max_retries, int) or isinstance(max_retries, bool) or
                max_retries < 0 or not_found_hours <= 0 or budget_seconds <= 0):
            raise ValueError('invalid retry configuration')
        with self.writer():
            path = self.root / 'research' / (safe(request_id) + '.json')
            r = read(path)
            if not r or item not in {m['item'] for m in r['missing']}:
                raise ValueError('failure must refer to a pending request item')
            prior = [f for f in r['failures'] if f['item'] == item and f['source_key'] == source_key]
            current = dt(stamp())
            if prior and (len(prior) >= prior[-1].get('max_retries', max_retries) + 1 or
                          (prior[-1].get('retry_exhausted') and
                           not prior[-1].get('budget_exhausted'))):
                raise ValueError('RETRY_EXHAUSTED: choose another source or request')
            if prior and prior[-1].get('budget_exhausted'):
                raise ValueError('BUDGET_EXHAUSTED: choose another source or request')
            if current >= dt(r['deadline_at']):
                raise ValueError('BUDGET_EXHAUSTED: request time budget has expired')
            # Do not increase the existing retry allowance by changing the CLI flag.
            limit = prior[0].get('max_retries', max_retries) if prior else max_retries
            exhausted = len(prior) + 1 >= limit + 1
            budget_end = dt(prior[0]['at']) + timedelta(seconds=budget_seconds) if prior else current + timedelta(seconds=budget_seconds)
            budget_exhausted = current >= budget_end
            delay = not_found_hours * 3600 if status == 'NOT_FOUND' or exhausted or budget_exhausted else min(2 ** len(prior), budget_seconds)
            r['failures'].append({'item': item, 'status': status, 'source_key': source_key,
                                  'at': current.isoformat(), 'next_retry_at': (current + timedelta(seconds=delay)).isoformat(),
                                  'max_retries': limit,
                                  'retry_exhausted': exhausted or budget_exhausted,
                                  'budget_exhausted': budget_exhausted})
            atomic(path, r)
            return r['failures'][-1]

    def audit(self, repo=None):
        errors = []
        external_ids = {}
        records = list(self.records())
        owners = {}
        by_key = {r['horse_key']: r for r in records if isinstance(r.get('horse_key'), str)}
        for record in records:
            if not isinstance(record.get('horse_key'), str):
                continue
            ids = record.get('identity', {}).get('external_ids', {})
            if isinstance(ids, dict):
                for provider, value in ids.items():
                    if isinstance(value, str):
                        owners.setdefault((provider, value), set()).add(record['horse_key'])

        def validate_indexed(identity, key):
            # 全体の外部ID所有者を先に作り、現在/旧identityの重複検査を保つ。
            self.validate_identity(identity, key, [])
            candidates = set()
            for provider, value in identity.get('external_ids', {}).items():
                candidates.update(owners.get((provider, value), set()))
            self.validate_identity(identity, key, [by_key[k] for k in candidates])

        for record in records:
            try:
                if record['schema_version'] != SCHEMA:
                    raise ValueError('schema mismatch')
                safe(record['horse_key'])
                validate_indexed(record['identity'], record['horse_key'])
                first = record.get('initial_identity')
                observed = record.get('identity_observed_at')
                if not isinstance(first, dict) or not observed:
                    raise ValueError('initial identity or observation timestamp missing')
                validate_indexed(first, record['horse_key'])
                first_time = dt(observed)
                if first_time > dt(stamp()):
                    raise ValueError('initial identity observation is in the future')
                history = record.get('identity_revisions', [])
                if history and history[0]['before'] != first:
                    raise ValueError('initial identity revision chain broken')
                if not history and record['identity'] != first:
                    raise ValueError('initial identity mismatch')
                confirmed = observed if first['status'] == 'RESOLVED' else None
                for index, event in enumerate(history):
                    event_body = {k: v for k, v in event.items() if k != 'event_hash'}
                    if digest(event_body) != event['event_hash']:
                        raise ValueError('identity revision hash mismatch')
                    if not event.get('reason') or not event.get('reviewed_by'):
                        raise ValueError('identity revision missing review')
                    event_time = dt(event['at'])
                    if event_time < first_time or event_time > dt(stamp()):
                        raise ValueError('identity revision timestamp outside observation interval')
                    if event['before']['status'] != 'RESOLVED' and event['after']['status'] == 'RESOLVED':
                        if confirmed is not None:
                            raise ValueError('identity already confirmed')
                        confirmed = event['at']
                    if index and history[index - 1]['after'] != event['before']:
                        raise ValueError('identity revision chain broken')
                    if index and dt(event['at']) < dt(history[index - 1]['at']):
                        raise ValueError('identity revision chronology broken')
                    validate_indexed(event['before'], record['horse_key'])
                    validate_indexed(event['after'], record['horse_key'])
                if history and history[-1]['after'] != record['identity']:
                    raise ValueError('identity revision does not match current identity')
                if record.get('identity_confirmed_at') != confirmed:
                    raise ValueError('identity confirmation timestamp mismatch')
                for provider, value in record['identity'].get('external_ids', {}).items():
                    pair = (provider, value)
                    if pair in external_ids:
                        raise ValueError('duplicate external identity')
                    external_ids[pair] = record['horse_key']
                known = set()
                for r in record['revisions']:
                    self.validate_fact(r)
                    body = {k: v for k, v in r.items() if k != 'content_hash'}
                    if digest(body) != r['content_hash'] or r['revision_id'] in known:
                        raise ValueError('revision hash/ID mismatch')
                    if not set(r.get('supersedes', [])).issubset(known):
                        raise ValueError('invalid superseded revision')
                    known.add(r['revision_id'])
            except (ValueError, KeyError, TypeError) as exc:
                errors.append({'horse_key': record.get('horse_key'), 'error': str(exc)})
        manifest = read(self.root / 'migration.json')
        if manifest:
            try:
                claims = manifest['claims']
                if manifest['schema_version'] != SCHEMA or manifest['extracted'] != len(claims):
                    raise ValueError('migration schema/count mismatch')
                known = set()
                file_counts = {}
                for c in claims:
                    dt(c['first_observed_at']); dt(c['captured_at'])
                    if c['status'] != 'UNVERIFIED' or c['identity_status'] != 'IDENTITY_UNRESOLVED':
                        raise ValueError('legacy candidate promoted without source revalidation')
                    expected_id = digest({'commit': c['commit'], 'path': c['path'], 'line': c['line'], 'text': c['text']})
                    if c['claim_id'] != expected_id or c['claim_id'] in known or c['commit'] != manifest['commit']:
                        raise ValueError('migration ID/commit mismatch')
                    if c['source']['record_hash'] != hashlib.sha256(c['text'].encode()).hexdigest():
                        raise ValueError('migration record hash mismatch')
                    if any(component['status'] != 'UNVERIFIED' for component in c['components']):
                        raise ValueError('migration component incorrectly verified')
                    known.add(c['claim_id'])
                    file_counts[c['path']] = file_counts.get(c['path'], 0) + 1
                if any(file_counts.get(f['path'], 0) != f['extracted'] for f in manifest['files']):
                    raise ValueError('migration file count mismatch')
                if manifest['verified'] != 0 or manifest['unverified'] != len(claims):
                    raise ValueError('migration verification summary mismatch')
                if repo is not None and migration_manifest(repo, manifest['commit'],
                                                             manifest['first_observed_at']) != manifest:
                    raise ValueError('migration differs from referenced commit')
            except (ValueError, KeyError, TypeError) as exc:
                errors.append({'migration': str(exc)})
        return {'status': 'PASS' if not errors else 'FAIL', 'horses': len(records),
                'migration_claims': manifest['extracted'] if manifest else 0, 'errors': errors}


def split_claim(line):
    """Extract only explicit table statements; never infer horse IDs or lineage."""
    parts = [part.strip() for part in line.split('|')]
    components = []
    if len(parts) > 3 and parts[1].isdigit() and parts[2]:
        for part in parts[3:]:
            pair = re.search(r'^([^×、（]+)×母父([^、（]+)', part)
            if pair:
                for field, name in [('parent:S', pair[1]), ('parent:DS', pair[2])]:
                    components.append({'kind': 'OBJECTIVE_FACT_CANDIDATE', 'horse_name': parts[2],
                                       'field': field, 'ancestor_name': name.strip(),
                                       'status': 'UNVERIFIED', 'identity_status': 'IDENTITY_UNRESOLVED'})
    if re.search(r'系|内包|クロス', line):
        components.append({'kind': 'DERIVED_CLAIM', 'text': line, 'status': 'UNVERIFIED'})
    if re.search(r'好成績|優勢|傾向|仮説|勝率|複勝|成績|適性', line):
        components.append({'kind': 'TREND_OR_INTERPRETATION', 'text': line,
                           'status': 'UNVERIFIED', 'production_input': False})
    if not components:
        components.append({'kind': 'UNCLASSIFIED', 'text': line, 'status': 'UNVERIFIED'})
    return components


def git_save(repo, root, expected_head):
    """Commit data on an authorized research branch, CAS locally, then read back.

    Remote push remains separate and must use an expected remote HEAD/blob lease.
    """
    repo = Path(repo).resolve()
    root = Path(root).resolve()
    relative = root.relative_to(repo).as_posix()
    def git(*args):
        return subprocess.check_output(['git', '-C', str(repo), *args], text=True).strip()
    branch = git('branch', '--show-current')
    if not re.fullmatch(r'(research/pedigree/[a-zA-Z0-9_.-]+|prediction/\d{4}-\d{2}-\d{2})', branch):
        raise ValueError('use research/pedigree/<request_id> or prediction/YYYY-MM-DD')
    if git('rev-parse', 'HEAD') != expected_head:
        raise ValueError('CONCURRENT_UPDATE: branch HEAD changed')
    with Registry(root).writer():
        if Registry(root).audit(repo=repo)['status'] != 'PASS':
            raise ValueError('registry audit failed')
        staged = git('diff', '--cached', '--name-only').splitlines()
        if any(not p.startswith(relative + '/') for p in staged):
            raise ValueError('unrelated staged changes; use an isolated worktree')
        if git('rev-parse', 'HEAD') != expected_head:
            raise ValueError('CONCURRENT_UPDATE: branch HEAD changed')
        git('add', '--', relative)
        if git('diff', '--cached', '--name-only'):
            git('commit', '-m', '血統調査情報を検証して保存')
        commit = git('rev-parse', 'HEAD')
        hashes = {}
        for path in sorted(root.rglob('*.json')):
            name = path.relative_to(repo).as_posix()
            remote_content = json.loads(git('show', commit + ':' + name))
            if remote_content != read(path):
                raise OSError('Git readback mismatch')
            hashes[name] = digest(remote_content)
        return {'commit_sha': commit, 'branch': branch, 'hashes': hashes,
                'persistence': 'LOCAL_GIT_READBACK_VERIFIED', 'remote_persistence': 'UNCONFIRMED',
                'snapshot_persistence': 'NOT_EVALUATED', 'verified_at': stamp()}


def migration_manifest(repo, commit, observed_at):
    """Reconstruct every imported byte exclusively from the requested Git commit."""
    dt(observed_at)
    repo = Path(repo).resolve()
    def git(*args):
        return subprocess.check_output(['git', '-C', str(repo), *args],
                                       stderr=subprocess.PIPE)
    sha = git('rev-parse', '--verify', commit + '^{commit}').decode().strip()
    entries = git('ls-tree', '-r', '-z', sha, '--', 'docs/yosou',
                  'docs/validation/records', 'docs/validation/snapshots')
    files = []
    for entry in entries.split(b'\0'):
        if not entry:
            continue
        meta, name = entry.split(b'\t', 1)
        relative = name.decode('utf-8')
        if meta.split()[0] not in {b'100644', b'100755'}:
            continue
        if ((relative.startswith('docs/yosou/') and relative.endswith('.md')) or
            (relative.startswith('docs/validation/records/') and
             '/' not in relative[len('docs/validation/records/'):]) or
            (relative.startswith('docs/validation/snapshots/') and
             '/' not in relative[len('docs/validation/snapshots/'):] and
             relative.endswith('.md'))):
            files.append(relative)
    claims, inventory = [], []
    pattern = re.compile(r'血統|母父|父系|母系|内包|Danzig|Roberto|Caro|ノーザンダンサー|ディープインパクト')
    for relative in sorted(files):
        content = git('show', sha + ':' + relative)
        count = 0
        for number, line in enumerate(content.decode('utf-8').splitlines(), 1):
            if not pattern.search(line):
                continue
            claim_id = digest({'commit': sha, 'path': relative, 'line': number, 'text': line})
            components = split_claim(line)
            claims.append({'components': components, 'claim_id': claim_id, 'status': 'UNVERIFIED',
                           'identity_status': 'IDENTITY_UNRESOLVED', 'text': line,
                           'claim_kind': 'LEGACY_CLAIM_REQUIRES_REVIEW',
                           'source': {'source_class': 'LEGACY_REPOSITORY', 'origin_group': 'horse-man',
                                      'acquisition_method': 'repository-line-extraction',
                                      'url': 'https://github.com/eda-hub/horse-man/blob/' + sha + '/' + relative + '#L' + str(number),
                                      'record_hash': hashlib.sha256(line.encode()).hexdigest()},
                           'first_observed_at': observed_at, 'captured_at': observed_at,
                           'path': relative, 'line': number, 'commit': sha})
            count += 1
        inventory.append({'path': relative, 'commit': sha,
                          'sha256': hashlib.sha256(content).hexdigest(), 'extracted': count})
    return {'schema_version': SCHEMA, 'commit': sha, 'first_observed_at': observed_at,
            'files': inventory, 'extracted': len(claims), 'verified': 0,
            'unverified': len(claims), 'duplicate_texts': len(claims) - len({c['text'] for c in claims}),
            'conflicts': 'NOT_ASSESSED_IDENTITIES_UNRESOLVED',
            'unaccessed': ['past chats', 'original external sources', 'other branches'],
            'claims': claims}


def migrate(repo, root, commit, observed_at):
    """Commit-pinned, idempotent migration that preserves an existing manifest."""
    dt(observed_at)
    with Registry(root).writer():
        path = Path(root) / 'migration.json'
        previous = read(path)
        if previous:
            if previous['commit'] != subprocess.check_output(
                    ['git', '-C', str(repo), 'rev-parse', '--verify', commit + '^{commit}'],
                    text=True, stderr=subprocess.PIPE).strip():
                raise ValueError('migration commit changed; keep prior manifest and use a separate import batch')
            observed_at = previous['first_observed_at']
        manifest = migration_manifest(repo, commit, observed_at)
        if previous:
            if manifest != previous:
                raise ValueError('migration manifest differs from referenced commit; existing manifest preserved')
        else:
            atomic(path, manifest)
        return {'files': len(manifest['files']), 'extracted': len(manifest['claims']), 'verified': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', default='data/pedigree')
    sub = parser.add_subparsers(dest='command', required=True)
    s = sub.add_parser('search'); s.add_argument('query'); s.add_argument('--cutoff')
    s = sub.add_parser('claims'); s.add_argument('query')
    s = sub.add_parser('save'); s.add_argument('candidate'); s.add_argument('--expected-hash')
    s = sub.add_parser('update-identity'); s.add_argument('candidate'); s.add_argument('--expected-hash', required=True); s.add_argument('--reason', required=True); s.add_argument('--reviewed-by', required=True)
    s = sub.add_parser('plan'); s.add_argument('request'); s.add_argument('--force', action='store_true')
    s = sub.add_parser('failure'); s.add_argument('request_id'); s.add_argument('item'); s.add_argument('status', choices=['NOT_FOUND', 'SOURCE_ERROR', 'SAVE_ERROR']); s.add_argument('--source-key', default='manual'); s.add_argument('--max-retries', type=int, default=2); s.add_argument('--not-found-hours', type=float, default=24); s.add_argument('--budget-seconds', type=float, default=60)
    s = sub.add_parser('derive'); s.add_argument('horse_key'); s.add_argument('--ancestor', action='append', default=[]); s.add_argument('--depth', type=int, default=5); s.add_argument('--cutoff', required=True); s.add_argument('--taxonomy-version')
    s = sub.add_parser('migrate'); s.add_argument('--repo', default='.'); s.add_argument('--commit', required=True); s.add_argument('--observed-at', default=stamp())
    s = sub.add_parser('git-save'); s.add_argument('--repo', default='.'); s.add_argument('--expected-head', required=True)
    s = sub.add_parser('audit'); s.add_argument('--repo', default='.')
    args = parser.parse_args()
    registry = Registry(args.root)
    try:
        if args.command == 'search': result = registry.search(args.query, args.cutoff)
        elif args.command == 'claims':
            result = [c for c in read(Path(args.root) / 'migration.json', {'claims': []})['claims'] if norm(args.query) in norm(c['text'])]
        elif args.command == 'save': result = registry.save(read(Path(args.candidate)), args.expected_hash)
        elif args.command == 'update-identity': result = registry.update_identity(read(Path(args.candidate)), args.expected_hash, args.reason, args.reviewed_by)
        elif args.command == 'plan': result = registry.plan(read(Path(args.request)), args.force)
        elif args.command == 'derive': result = registry.derive(args.horse_key, args.ancestor, args.depth, args.cutoff, args.taxonomy_version)
        elif args.command == 'failure': result = registry.failure(args.request_id, args.item, args.status, args.source_key, args.max_retries, args.not_found_hours, args.budget_seconds)
        elif args.command == 'migrate': result = migrate(args.repo, args.root, args.commit, args.observed_at)
        elif args.command == 'git-save': result = git_save(args.repo, args.root, args.expected_head)
        else:
            with registry.writer():
                result = registry.audit(repo=args.repo)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1 if isinstance(result, dict) and result.get('status') == 'FAIL' else 0
    except (ValueError, KeyError, TypeError, OSError, subprocess.CalledProcessError) as exc:
        print(json.dumps({'status': 'ERROR', 'persistence': 'UNCONFIRMED', 'error': str(exc)}, ensure_ascii=False))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())

