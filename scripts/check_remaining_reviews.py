"""旧記述分類と歴史的保存再照合を原文・Git blob・元台帳へ結び付ける。"""
import gzip
import hashlib
import json
from collections import Counter
from pathlib import Path

BASE=Path('data/pedigree/reconciliations/2026-10-10-training-priority')
KINDS={'OBJECTIVE_FACT_CANDIDATE':'FACT','DERIVED_CLAIM':'DERIVED_INTERPRETATION','TREND_OR_INTERPRETATION':'HYPOTHESIS','UNCLASSIFIED':'UNCONFIRMED'}

def require(value,message):
    if not value:raise ValueError(message)

def read(path):return json.loads(path.read_text())

def blob(text):
    raw=text.encode();return hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()

def bundle(root,progress,path_key,hash_key):
    path=Path(progress[path_key]);require(not path.is_absolute() and '..' not in path.parts,'evidence relative path')
    raw=(root/path).read_bytes();require(hashlib.sha256(raw).hexdigest()==progress[hash_key],'evidence archive hash')
    return json.loads(gzip.decompress(raw))

def check(root=Path('.')):
    root=Path(root);base=root/BASE
    ledger_path=base/'legacy-535-claim-review.json';ledger=read(ledger_path)
    p=read(base/'legacy-remaining-review/progress.json')
    require(hashlib.sha256(ledger_path.read_bytes()).hexdigest()==p['ledger_sha256'],'original ledger unchanged')
    originals=bundle(root,p,'source_bundle_path','source_bundle_sha256')
    require(len(originals)==p['source_files']==32,'original source scope')
    for v in originals.values():require(blob(v['content'])==v['sha'],'original git blob hash')
    claims={c['claim_id']:c for c in ledger['claims']}
    require(len(claims)==p['claims']==535,'all original claims')
    for c in claims.values():
        text=originals[c['path']]['content'].splitlines()[c['line']-1].strip()
        require(text==c['original_text'].strip() and hashlib.sha256(c['original_text'].encode()).hexdigest()==c['source']['record_hash'],'original claim line hash')
    expected={k:c for k,c in claims.items() if c['review_status']=='OPEN_REVIEW'}
    seen=set();counts=Counter()
    for path in p['batches']:
        batch=read(root/path)
        require(batch['mode']=='REPLAY' and batch['production_eligible'] is False,'classification replay boundary')
        for r in batch['claims']:
            key=r['claim_id'];require(key in expected and key not in seen,'classification exact scope');seen.add(key);c=expected[key]
            require(r['full_claim_status']=='UNVERIFIED' and r['production_eligible'] is False,'no legacy promotion')
            require(r['path']==c['path'] and r['line']==c['line'] and r['original_text_sha256']==c['source']['record_hash'] and r['original_blob_sha']==originals[c['path']]['sha'] and r['original_commit']=='439faa54a524ce9d242f100788f2a80fa2b0b698','review original binding')
            require(len(r['parts'])==len(c['parts']),'all components retained')
            for part,old in zip(r['parts'],c['parts']):
                require(part['component_index']==old['component_index'] and part['basis_kind']==old['kind'] and part['category']==KINDS[old['kind']],'conservative category binding')
                require(part['verification_status']==old['status'] and part['linked_original_evidence']==old['linked_original_evidence'],'original source matching retained')
                counts[part['category']]+=1
            require(r['categories']==sorted({part['category'] for part in r['parts']}),'claim mixed categories')
    require(seen==set(expected) and len(seen)==p['remaining_claims_classified']==482 and p['remaining_claims_unclassified']==0,'remaining claim counts')
    require(dict(counts)==p['category_components'] and p['new_verified_claims']==0,'component counts and no promotion')
    matched=[c for c in claims.values() if c['review_status']!='OPEN_REVIEW']
    require(len(matched)==p['previously_matched_claims']==53 and sum(part['status']=='SOURCE_JRA_PARENT_FIELD_MATCHED' for c in claims.values() for part in c['parts'])==p['previously_matched_parent_components']==106,'original objective matches')

    audit=read(base/'persistence-40-audit.json');p=read(base/'persistence-history-review/progress.json');evidence=bundle(root,p,'evidence_path','evidence_sha256')
    original={(i['path'],i['artifact_id']):i for i in audit['items']};seen=set();results=Counter()
    for path in p['batches']:
        for r in read(root/path)['items']:
            key=(r['path'],r['artifact_id']);require(key in original and key not in seen,'historical review scope');seen.add(key)
            require(r['original_reason']==original[key]['reason'] and r['eligibility']=='UNRESOLVED_INELIGIBLE' and r['new_intent_or_receipt_created'] is False,'historical eligibility preserved')
            e=next(e for e in evidence['trees'] if e['commit']['sha']==r['reviewed_commit']);commit=e['commit'];date=commit['committer']['date'][:10]
            require(date in r['path'] and r['commit_at']==commit['committer']['date'],'historical day and commit')
            require(e['docs']['truncated'] is False and commit['tree']['sha']==e['root']['sha'] and next(t for t in e['root']['tree'] if t['path']=='docs')['sha']==e['docs']['sha'],'complete historical docs tree')
            tree={t['path']:t for t in e['docs']['tree'] if t['type']=='blob'}
            files={k.split(':',1)[1]:v for k,v in evidence['files'].items() if k.startswith(commit['sha']+':')}
            for name,v in files.items():require(blob(v['content'])==v['sha']==tree[name.removeprefix('docs/')]['sha'],'historical git file binding')
            snap=files['docs/validation/snapshots/'+date+'.md'];require(r['artifact_id'] in snap['content'] and r['snapshot_blob_sha']==snap['sha'],'historical exact artifact')
            intent_paths=[k for k in tree if k.startswith('validation/persistence-intents/'+date+'/') and k.endswith('.json')]
            intents=[]
            for k in intent_paths:
                v=files['docs/'+k];obj=json.loads(v['content'])
                if obj.get('snapshot_id')==r['artifact_id']:intents.append({'path':'docs/'+k,'blob_sha':v['sha'],'schema_version':obj.get('schema_version')})
            require(intents==r['matching_intents'],'all historical declaration candidates')
            receipt='validation/persistence-receipts/'+date+'.md';require(r['receipt_file_present']==(receipt in tree),'historical receipt existence')
            if r['original_reason']=='NO_INTENT':
                expected_status='HISTORICAL_INTENT_FOUND_INVALID_SCHEMA' if intents else 'NO_MATCHING_INTENT_IN_REVIEWED_TREE'
                require(not intents or all(i['schema_version']!='prediction-persistence-intent-v1' for i in intents),'no valid declaration silently discarded')
            else:
                require(len(intents)==1 and receipt not in tree,'original receipt absence');expected_status='RECEIPT_ABSENT_IN_REVIEWED_TREE'
            require(r['review_status']==expected_status,'historical conclusion binding');results[expected_status]+=1
    require(seen==set(original) and len(seen)==p['reviewed']==p['unresolved']==40 and p['resolved_eligible']==0 and dict(results)==p['results'],'historical counts')
    return {'classified_claims':482,'categories':dict(counts),'historical_reviewed':40,'historical_unresolved':40,'historical_results':dict(results)}

if __name__=='__main__':print(json.dumps(check(),ensure_ascii=False))
