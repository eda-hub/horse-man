"""R07のPR HEAD・中間commit・全docs treeから真正な既存保存証跡を再照合する。"""
import argparse
import gzip
import hashlib
import json
import re
import tempfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from check_prediction_compliance import receipt_records

BASE = Path('data/pedigree/reconciliations/2026-10-10-training-priority')
REVIEW = BASE / 'persistence-pr-ref-review'

def require(ok, message):
    if not ok:
        raise ValueError(message)

def read(path):
    path = Path(path)
    return json.loads(gzip.decompress(path.read_bytes()) if path.suffix == '.gz' else path.read_text())

def git_hash(kind, raw):
    return hashlib.sha1(kind.encode() + b' ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()

def tree_hash(entries):
    ordered = sorted(entries, key=lambda f: (f['path'] + ('/' if f['type'] == 'tree' else '')).encode())
    raw = b''.join(format(int(f['mode'], 8), 'o').encode() + b' ' + f['path'].encode() + b'\0' + bytes.fromhex(f['sha']) for f in ordered)
    return git_hash('tree', raw)

def verify_tree(tree, recursive=False):
    require(tree['truncated'] is False, 'complete tree required')
    require(len({f['path'] for f in tree['tree']}) == len(tree['tree']), 'unique tree entries')
    if not recursive:
        require(tree_hash(tree['tree']) == tree['sha'], 'root tree Git hash')
        return
    groups = defaultdict(list)
    for f in tree['tree']:
        parent, _, name = f['path'].rpartition('/')
        groups[parent].append({**f, 'path': name})
    require(tree_hash(groups['']) == tree['sha'], 'docs root Git tree hash')
    for f in tree['tree']:
        if f['type'] == 'tree':
            require(tree_hash(groups[f['path']]) == f['sha'], 'nested docs Git tree hash')

def candidate(path):
    return ((path.startswith('validation/persistence-intents/') and path.endswith('.json')) or
            (path.startswith('validation/persistence-receipts/') and path.endswith('.md')))

def date_time(value):
    try:
        d = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return d if d.tzinfo else None
    except (ValueError, TypeError, AttributeError):
        return None

def intent_issues(obj, path, date):
    issues = []
    if obj.get('schema_version') != 'prediction-persistence-intent-v1':
        issues.append('INVALID_SCHEMA')
    if obj.get('race_date_jst') != date or Path(path).parent.name != date:
        issues.append('DATE_OR_PATH_MISMATCH')
    if obj.get('working_branch') != 'prediction/' + date:
        issues.append('WORKING_BRANCH_MISMATCH')
    races = obj.get('required_race_ids')
    if not isinstance(races, list) or not races or any(not isinstance(r, str) or not r for r in races) or (isinstance(races, list) and all(isinstance(r, str) for r in races) and len(set(races)) != len(races)):
        issues.append('INVALID_REQUIRED_RACES')
    if date_time(obj.get('deadline_jst')) is None:
        issues.append('INVALID_DEADLINE')
    if 'failed-attempts' in Path(path).parts:
        issues.append('FAILED_ATTEMPT_HISTORY_ONLY')
    return issues

def index_evidence(evidence):
    collection = evidence['collection']
    inventory = collection['pull_inventory']
    require(len(inventory) < 100 and len({p['number'] for p in inventory}) == len(inventory), 'one complete PR inventory page')
    selected = [p for p in inventory if '2026-09-25' <= p['created_at'] < '2026-10-05']
    selection_fields = ['number', 'created_at', 'head_sha', 'head_ref', 'merge_commit_sha']
    require([{k: p[k] for k in selection_fields} for p in selected] == collection['selected'], 'explicit complete PR selection')
    commits = evidence['commits']
    expected = set()
    for group in collection['commit_pages']:
        require(group['pr_number'] in {p['number'] for p in selected}, 'selected PR history')
        for number, page in enumerate(group['pages'], 1):
            require(page['url'].endswith('/pulls/' + str(group['pr_number']) + '/commits?per_page=100&page=' + str(number)), 'ordered API pages')
            require(len(page['items']) == 100 if number < len(group['pages']) else len(page['items']) < 100, 'history pagination complete')
            for c in page['items']:
                expected.add(c['sha'])
                require(commits[c['sha']]['tree']['sha'] == c['commit']['tree']['sha'], 'PR commit root binding')
        p = next(p for p in selected if p['number'] == group['pr_number'])
        local_commits = [c['sha'] for page in group['pages'] for c in page['items']]
        require(p['head_sha'] in local_commits and len(set(local_commits)) == len(local_commits), 'PR head covered without duplicate pages')
    require({g['pr_number'] for g in collection['commit_pages']} == {p['number'] for p in selected}, 'all PR histories')
    for m in evidence['merge_commits']:
        expected.add(m['commit']['sha'])
        p = next(p for p in selected if p['number'] == m['pr_number'])
        require(p['merge_commit_sha'] == m['commit']['sha'] and commits[m['commit']['sha']] == m['commit'], 'merge commit binding')
    require({m['pr_number'] for m in evidence['merge_commits']} == {p['number'] for p in selected if p['state'] == 'closed'}, 'closed PR merge roots')
    require(set(commits) == expected, 'exact unique commit scope')
    for tree in evidence['roots'].values():
        verify_tree(tree)
    for tree in evidence['docs'].values():
        verify_tree(tree, True)
    occurrences = defaultdict(list)
    for sha, commit in commits.items():
        root = evidence['roots'][commit['tree']['sha']]
        doc_entry = next(f for f in root['tree'] if f['path'] == 'docs' and f['type'] == 'tree')
        docs = evidence['docs'][doc_entry['sha']]
        for f in docs['tree']:
            if f['type'] == 'blob' and candidate(f['path']):
                occurrences[(f['path'], f['sha'])].append(sha)
    require({sha for _, sha in occurrences} == set(evidence['files']), 'all intent and receipt candidate bodies')
    for sha, f in evidence['files'].items():
        require(f['sha'] == sha == git_hash('blob', f['content'].encode()), 'candidate exact Git blob bytes')
    return occurrences

def compute(root, evidence):
    occurrences = index_evidence(evidence)
    parsed_receipts = {}
    with tempfile.TemporaryDirectory() as directory:
        for sha, f in evidence['files'].items():
            if any(s == sha and p.startswith('validation/persistence-receipts/') for p, s in occurrences):
                path = Path(directory) / (sha + '.md')
                path.write_text(f['content'])
                parsed_receipts[sha] = receipt_records(path)
    results = []
    for item in read(root / BASE / 'persistence-40-audit.json')['items']:
        artifact = item['artifact_id']
        date = re.search(r'\d{4}-\d{2}-\d{2}', item['path'])[0]
        intents = []
        receipts = []
        for (path, sha), seen in sorted(occurrences.items()):
            first = min(seen, key=lambda c: (evidence['commits'][c]['committer']['date'], c))
            binding = {'path': 'docs/' + path, 'blob_sha': sha, 'seen_in_commits': len(seen), 'first_observed_commit': first, 'first_observed_commit_at': evidence['commits'][first]['committer']['date']}
            if path.startswith('validation/persistence-intents/'):
                obj = json.loads(evidence['files'][sha]['content'])
                if obj.get('snapshot_id') == artifact:
                    issues = intent_issues(obj, path, date)
                    deadline = date_time(obj.get('deadline_jst'))
                    first_at = date_time(binding['first_observed_commit_at'])
                    intents.append({**binding, 'schema_version': obj.get('schema_version'), 'issues': issues, 'deadline_jst': obj.get('deadline_jst'), 'first_commit_before_declared_deadline': first_at < deadline if deadline and first_at else None})
            else:
                matching = [r for r in parsed_receipts[sha] if r.get('artifact_id') == artifact]
                if matching:
                    receipts.append({**binding, 'records': matching, 'qualification': 'CANDIDATE_ONLY_NOT_PRE_RACE_CERTIFIED'})
        status = 'NO_CORRESPONDING_INTENT_IN_PR_HISTORY'
        if intents:
            status = 'CORRESPONDING_INTENT_INVALID' if all(i['issues'] for i in intents) else 'VALID_INTENT_WITHOUT_VERIFIED_RECEIPT'
            require(status != 'VALID_INTENT_WITHOUT_VERIFIED_RECEIPT' or not receipts, 'receipt found: perform full original-artifact/time/hash verification before changing conclusion')
        results.append({'artifact_id': artifact, 'original_path': item['path'], 'original_reason': item['reason'], 'matching_intents': intents, 'receipt_candidates': receipts, 'status': status, 'eligibility': 'UNRESOLVED_INELIGIBLE', 'new_intent_or_receipt_created': False})
    return results

def generate(root=Path('.')):
    root = Path(root)
    archive = root / REVIEW / 'git-evidence.json.gz'
    evidence = read(archive)
    results = compute(root, evidence)
    previous = read(root / BASE / 'persistence-expanded-review/git-evidence.json.gz')
    old = {t['commit']['sha'] for t in previous['intermediate_trees'] + previous['branch_heads']}
    progress = {'schema_version': 'historical-pr-ref-review-v1', 'baseline_head': 'b29454a04dc2dcf06ab7c162bea7a97bf711913b', 'reviewed_at': datetime.now(timezone.utc).isoformat(), 'prs': len(evidence['collection']['selected']), 'commits': len(evidence['commits']), 'new_commits_outside_previous_trees': len(set(evidence['commits']) - old), 'docs_trees': len(evidence['docs']), 'candidate_blobs': len(evidence['files']), 'reviewed': len(results), 'resolved_eligible': 0, 'unresolved': len(results), 'status_counts': dict(Counter(r['status'] for r in results)), 'artifacts_with_receipt_candidates': sum(bool(r['receipt_candidates']) for r in results), 'evidence_path': str(REVIEW / 'git-evidence.json.gz'), 'evidence_sha256': hashlib.sha256(archive.read_bytes()).hexdigest(), 'new_intent_or_receipt_created': False, 'mode': 'REPLAY', 'production_eligible': False, 'scope': '対象期間作成PR22件のHEAD・全PR commit履歴・閉鎖PR merge commit・全docs tree。GitHubでPR参照可能な削除branch履歴も含む。', 'limitation': 'PRなしで削除されたbranch・到達不能commit・ローカルreflog・Git外の真正証跡は取得不能。commit時刻はreceiptの発走前読戻し時刻の代用にしない。'}
    (root / REVIEW / 'checks.json').write_text(json.dumps({'items': results}, ensure_ascii=False, indent=2) + '\n')
    (root / REVIEW / 'progress.json').write_text(json.dumps(progress, ensure_ascii=False, indent=2) + '\n')
    return progress

def check(root=Path('.')):
    root = Path(root)
    progress = read(root / REVIEW / 'progress.json')
    archive = root / REVIEW / 'git-evidence.json.gz'
    require(hashlib.sha256(archive.read_bytes()).hexdigest() == progress['evidence_sha256'], 'fixed evidence archive hash')
    evidence = read(archive)
    results = compute(root, evidence)
    require(results == read(root / REVIEW / 'checks.json')['items'], 'all forty conclusions from exact Git evidence')
    require(len(results) == progress['reviewed'] == progress['unresolved'] == 40 and progress['resolved_eligible'] == 0, 'all original omissions unresolved')
    require(progress['status_counts'] == dict(Counter(r['status'] for r in results)) and progress['artifacts_with_receipt_candidates'] == sum(bool(r['receipt_candidates']) for r in results), 'intent and receipt counts')
    require(progress['prs'] == len(evidence['collection']['selected']) and progress['commits'] == len(evidence['commits']) and progress['docs_trees'] == len(evidence['docs']) and progress['candidate_blobs'] == len(evidence['files']), 'exact search scope counts')
    previous = read(root / BASE / 'persistence-expanded-review/git-evidence.json.gz')
    old = {t['commit']['sha'] for t in previous['intermediate_trees'] + previous['branch_heads']}
    require(progress['new_commits_outside_previous_trees'] == len(set(evidence['commits']) - old), 'new commit count excludes prior review')
    require(progress['new_intent_or_receipt_created'] is False and progress['mode'] == 'REPLAY' and progress['production_eligible'] is False, 'no retrospective eligibility or new receipts')
    return progress

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--generate', action='store_true')
    args = parser.parse_args()
    print(json.dumps(generate() if args.generate else check(), ensure_ascii=False))
