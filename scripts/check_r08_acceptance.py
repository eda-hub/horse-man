"""R08の公式成績・血統条件・調教国・固定集計の受入を再照合する。"""
import base64
import copy
import re
import unicodedata
from html.parser import HTMLParser
import gzip
import hashlib
import json
from collections import Counter
from pathlib import Path
from pedigree_registry import Registry, digest
from check_foreign_pedigree_review import norm
from check_training_country_ancestors import source_text
from pedigree_stats import select_training_country

def require(value, message):
    if not value: raise ValueError(message)
def read(path): return json.loads(path.read_text())
R08=Path('data/pedigree/reconciliations/2026-10-10-r08-followup')
class TableRows(HTMLParser):
    def __init__(self):super().__init__();self.rows=[];self.row=None;self.cell=None
    def handle_starttag(self,tag,attrs):
        if tag=='tr':self.row=[]
        elif tag=='td' and self.row is not None:self.cell=[]
    def handle_data(self,data):
        if self.cell is not None:self.cell.append(data)
    def handle_endtag(self,tag):
        if tag=='td' and self.cell is not None:
            self.row.append(' '.join(''.join(self.cell).split()));self.cell=None
        elif tag=='tr' and self.row is not None:
            self.rows.append(self.row);self.row=None

def country_evidence(entry,target,kind):
    if kind=='OWN_PROFILE_TRAINER_COUNTRY':
        text=source_text(entry)
        profile=re.search(r'馬名 .*? 血統表',text)
        require(profile and target['name'] in profile.group() and '生年月日 '+str(target['birth_year'])+'.' in profile.group(),'own profile name/year')
        trainer=re.search(r' 調教師 (.*?) 馬主 ',profile.group()).group(1)
        mapping={'英国':'GB','愛国':'IE','米国':'US','仏国':'FR','独国':'DE','豪州':'AU','UAE':'AE'}
        labels=[label for group in re.findall(r'（([^）]+)）',trainer) for label in unicodedata.normalize('NFKC',group).split('/')]
        require(labels and all(label in mapping for label in labels),'explicit own trainer countries')
        return sorted({mapping[label] for label in labels}),trainer,None
    require(kind=='IFHA_EXPLICIT_TRAINED_COLUMN','explicit country proof type')
    body=base64.b64decode(entry['body_base64'],validate=True);meta=entry['capture']
    require(meta['http_status']==200 and meta['hash_kind']=='http-response-body-bytes-sha256' and len(body)==meta['byte_length'] and hashlib.sha256(body).hexdigest()==meta['sha256'],'IFHA raw response hash')
    parser=TableRows();parser.feed(body.decode('utf-8',errors='replace'))
    rows=[row for row in parser.rows if len(row)>=10 and row[4].split(' (')[0]==target['name'] and row[5]==str(target['birth_year'])]
    require(rows and all(row[9] in ['FR','AUS'] for row in rows),'IFHA own identity/Trained column')
    return sorted({'AU' if row[9]=='AUS' else row[9] for row in rows}),rows[0][8],rows

def check_r08(root,registry):
    directory=root/R08;reviews=read(directory/'country-reviews.json');bundles={};statuses=Counter()
    for review in reviews['reviews']:
        target=review['target'];key=target['horse_key'];proof=review['proof'];path=proof['bundle_path']
        if path not in bundles:bundles[path]=json.loads(gzip.decompress((root/path).read_bytes()))
        item=bundles[path][proof['entry_key']];entry=item.get('source',item);statuses[review['status']]+=1
        if review['status']=='NO_COUNTRY_CONFIRMED':
            require(target['name']=='Commissioner' and '404' in entry['capture'].get('error',''),'unconfirmed own source retained')
            require(registry.fact(key,'attribute:training_country_matches',reviews['data_cutoff'])['status']=='NOT_FOUND','unconfirmed country not invented');continue
        countries,trainer,rows=country_evidence(entry,target,review['proof_kind'])
        require(trainer==review['trainer_field'] and countries==sorted({m['country'] for m in review['matches']}),'own country extraction')
        if rows is not None:require(rows==proof['ifha_rows'],'IFHA saved exact rows')
        for match in review['matches']:
            require(match['source']=={'url':entry['capture']['final_url'],'record_hash':entry['capture']['sha256'],'captured_at':entry['capture']['captured_at']},'country match raw source')
        record=read(registry.path(key));n=len(review['before_revision_hashes']);record['revisions']=record['revisions'][:n+1];before=copy.deepcopy(record);before['revisions']=before['revisions'][:n]
        require(digest(before)==review['before_record_hash'] and digest(record)==review['after_record_hash'] and [v['content_hash'] for v in before['revisions']]==review['before_revision_hashes'],'country old prefix and appended readback')
        revision=record['revisions'][-1];registry.validate_fact(revision)
        require(revision['revision_id']==review['added_revision_id'] and revision['value']['matches']==review['matches'] and revision['source']['record_hash']==entry['capture']['sha256'],'country revision source binding')
        selected,reason=select_training_country(revision['value'],review['data_cutoff'])
        require(selected==review['selected_country'] and reason==review['selection_reason'] and review['repeated_save_added']==0,'country selection and repeat save')
        require(registry.fact(key,'attribute:training_country_matches',review['historical_cutoff'])['status']=='NOT_FOUND','country historical cutoff')
    require(statuses=={'COUNTRY_CONFIRMED':17,'LATEST_MEMBERSHIP_DATE_REQUIRED':2,'NO_COUNTRY_CONFIRMED':1} and reviews['reviewed']==20 and reviews['confirmed']==17 and reviews['waiting']==3,'country scope counts')
    results_path=root/'data/pedigree/reconciliations/2026-10-09-followup/foreign_results_evidence.json';results=read(results_path)['races'];bindings=read(directory/'foreign-runner-bindings.json')
    require(hashlib.sha256(results_path.read_bytes()).hexdigest()==bindings['source_results_sha256'],'original foreign result hash')
    pairs={}
    for binding in bindings['rows']:
        pair=(binding['race_id'],binding['source_row']);require(pair not in pairs,'unique foreign binding');pairs[pair]=binding
        batch=read(root/binding['batch_path']);require(batch.get('race_id','FOREIGN-20261004-LONG05')==pair[0],'batch race identity')
        row=next(row for row in batch['rows'] if row['horse_key']==binding['horse_key']);result=next(r for r in results if r['race_id']==pair[0])['runners'][pair[1]]
        require(row.get('result_scope_index',pair[1])==pair[1],'batch row identity')
        if row.get('result_scope_index') is None:require(str(row['target']['reported_horse_number'])==str(result['horse_number']),'numeric/text horse number exact value')
    require(len(pairs)==42,'all foreign runner bindings')
    progress=read(directory/'statistics-progress.json');jra_ids=set();jra_entries=0;jra_starts=0
    selection=read(directory/'structural-condition-selection.json');expected_groups=None
    for summary in progress['snapshots']:
        definition=read(root/summary['definition']);snapshot=read(root/summary['snapshot'])
        require(snapshot['content_sha256']==summary['hash']==digest({k:v for k,v in snapshot.items() if k!='content_sha256'}),'immutable statistic content hash')
        require((root/summary['snapshot']).stat().st_size==summary['bytes'] and len(snapshot['groups'])==summary['groups'] and snapshot['all_runners']==summary['all_runners'] and snapshot['completeness']==summary['completeness'],'snapshot summary readback')
        structural=[g for g in definition['groups'] if g['axis']!='TRAINING_REGION']
        require(len(structural)==39 and Counter(g['axis'] for g in structural)=={'ANCESTOR':21,'SIRE_LINE':6,'DAM_SIRE_LINE':6,'CROSS':6},'selected structural condition counts')
        if expected_groups is None:expected_groups=structural
        require(structural==expected_groups and definition['condition_selection']['record_hash']==digest(selection) and definition['mode']=='REPLAY','fixed selected conditions and replay')
        if summary['scope']=='JRA':
            ids=set(snapshot['races_in_scope']);require(not ids&jra_ids and snapshot['completeness']=='COMPLETE' and summary['unknown_entries']==summary['conflict_entries']==0,'complete nonoverlapping JRA periods');jra_ids|=ids;jra_entries+=summary['all_runners']['entries'];jra_starts+=summary['all_runners']['valid_starts']
        else:
            manifest=read(root/summary['input']);require(len(manifest['races'])==(3 if summary['scope']=='official-three' else 4),'explicit foreign race scope')
            for race in manifest['races']:
                original=next(r for r in results if r['race_id']==race['race_id']);official=original['source_class']=='OFFICIAL_JRA'
                require(race['result_status']==('OFFICIAL' if official else 'PENDING') and len(race['runners'])==len(original['runners']),'foreign authority and full field')
                for index,(row,old) in enumerate(zip(race['runners'],original['runners'])):
                    status=old['status'] if official or old['status']=='SCRATCHED' else 'PENDING'
                    require(row['horse_key']==pairs[(race['race_id'],index)]['horse_key'] and row['status']==status and row['finish_position']==(old['finish_position'] if official else None),'foreign source exact runner/result isolation')
            require(summary['all_runners']['valid_starts']==30 and summary['all_runners']['pending_results']==(0 if summary['scope']=='official-three' else 8),'BHA unresolved denominator isolation')
            require(all(snapshot['groups'][g['group_id']]['cohorts']['UNKNOWN']['entries']==snapshot['groups'][g['group_id']]['cohorts']['CONFLICT']['entries']==0 for g in structural),'foreign structural ancestry complete')
    jra_input=read(root/'data/condition_stats/inputs/prediction-period-jra-20260816-20261004-alternative.json')
    require(jra_ids=={r['race_id'] for r in jra_input['races']} and len(jra_ids)==progress['jra_races']==159 and jra_entries==progress['jra_entries']==2182 and jra_starts==progress['jra_starts']==2177,'all JRA scope covered once')
    acquisition=read(directory/'bha-acquisition.json');response=json.loads(gzip.decompress((directory/'bha-response.json.gz').read_bytes()));body=base64.b64decode(response['body_base64'],validate=True)
    require(response['capture']==acquisition and acquisition['http_status']==403 and acquisition['result_table_obtained'] is False and acquisition['authentication_values_stored'] is False and len(body)==acquisition['response_bytes'] and hashlib.sha256(body).hexdigest()==acquisition['response_sha256'],'BHA actual acquisition failure and response binding')
    return {'foreign_country_confirmed':17,'foreign_country_waiting':3,'additional_snapshots':8,'jra_races':159}


def check(root=Path('.')):
    root=Path(root)
    registry=Registry(root/'data/pedigree')
    original=check_r08(root, registry)
    current=root/'data/pedigree/reconciliations/2026-10-11-r08-acceptance'
    review=read(current/'commissioner-review.json')
    entry=json.loads(gzip.decompress((root/review['proof_bundle']).read_bytes()))[review['proof_entry']]
    body=base64.b64decode(entry['body_base64'],validate=True)
    require(hashlib.sha256(body).hexdigest()==entry['capture']['sha256'],'Commissioner source response hash')
    parser=TableRows();parser.feed(body.decode())
    rows=[r for r in parser.rows if len(r)>=10 and r[4].split(' (')[0].casefold()=='commissioner' and r[5]=='2011']
    require(rows==review['ifha_rows'] and rows and all(r[9]=='USA' for r in rows),'Commissioner own identity and Trained column')
    record=read(registry.path(review['target']['horse_key']))
    n=len(review['before_revision_hashes']);record['revisions']=record['revisions'][:n+1]
    before=copy.deepcopy(record);before['revisions']=before['revisions'][:n]
    require(digest(before)==review['before_record_hash'] and digest(record)==review['after_record_hash'],'Commissioner append preserves original record')
    revision=record['revisions'][-1];registry.validate_fact(revision)
    require(revision['revision_id']==review['added_revision_id'] and revision['source']['record_hash']==entry['capture']['sha256'],'Commissioner revision source')
    require(select_training_country(revision['value'],review['data_cutoff'])[0]=='US' and review['repeated_save_added']==0,'Commissioner single country and idempotence')
    require(registry.fact(review['target']['horse_key'],'attribute:training_country_matches',review['historical_cutoff'])['status']=='NOT_FOUND','Commissioner no historical backdating')
    progress=read(current/'progress.json')
    require(progress['mode']=='REPLAY' and progress['production_eligible'] is False and progress['country_confirmed']==18,'research-only current scope')
    expected={'Sakhee':None,'Starspangledbanner':None}
    for target in progress['country_waiting']:
        require(target['name'] in expected,'explicit remaining country subjects')
        value=registry.fact(target['horse_key'],'attribute:training_country_matches',progress['data_cutoff'])
        require(value['status']=='VERIFIED' and select_training_country(value['value'],progress['data_cutoff'])[0] is None,'unresolved latest country not invented')
        expected[target['name']]=target['horse_key']
    require(all(expected.values()) and len(progress['country_waiting'])==2,'exact two remaining country subjects')
    require(len(progress['snapshots'])==2,'current foreign snapshots count')
    old=read(root/R08/'statistics-progress.json')
    for summary in progress['snapshots']:
        snapshot=read(root/summary['snapshot']);definition=read(root/summary['definition'])
        require(snapshot['content_sha256']==summary['hash']==digest({k:v for k,v in snapshot.items() if k!='content_sha256'}),'current snapshot immutable content hash')
        require((root/summary['snapshot']).stat().st_size==summary['bytes'] and snapshot['all_runners']==summary['all_runners'] and snapshot['completeness']==summary['completeness']=='PARTIAL','current snapshot summary')
        prior=next(s for s in old['snapshots'] if s['scope']==summary['scope'])
        require(summary['input']==prior['input'] and summary['all_runners']==prior['all_runners'],'fixed official results and denominator unchanged')
        require(definition['mode']=='REPLAY' and definition['data_cutoff']==progress['data_cutoff'] and len(snapshot['groups'])==summary['groups']==43,'current definition scope and cutoff')
        unknown=sum(g['cohorts']['UNKNOWN']['entries'] for g in snapshot['groups'].values())
        conflict=sum(g['cohorts']['CONFLICT']['entries'] for g in snapshot['groups'].values())
        require(unknown==summary['unknown_entries']==4 and conflict==summary['conflict_entries']==0,'current unknown separation')
    acquisition=read(current/'bha-retry.json');response=json.loads(gzip.decompress((current/'bha-retry-response.json.gz').read_bytes()))
    body=base64.b64decode(response['body_base64'],validate=True)
    require(response['capture']==acquisition and acquisition['http_status']==403 and acquisition['result_table_obtained'] is False and acquisition['authentication_values_stored'] is False and len(body)==acquisition['response_bytes'] and hashlib.sha256(body).hexdigest()==acquisition['response_sha256'],'BHA retry response hash and unresolved status')
    result={'jra_races':original['jra_races'],'added_snapshots':10,'foreign_country_confirmed':18,'foreign_country_waiting':2,'bha_pending_runners':8,'mode':'REPLAY','production_eligible':False}
    if 'user_resolution' in progress:
        resolution=progress['user_resolution'];reply=read(root/resolution['manifest_path'])
        require(reply['mode']=='REPLAY' and reply['production_eligible'] is False and hashlib.sha256(reply['user_reply_text'].encode()).hexdigest()==reply['user_reply_sha256'],'user reply raw text and hash')
        require(reply['historical_cutoff']==progress['data_cutoff'] and reply['data_cutoff']==resolution['data_cutoff'],'user reply cutoff binding')
        require({(r['name'],r['birth_year'],r['country'],r['role']) for r in reply['reviews']}=={('Sakhee',1997,'GB','DAM_SIRE'),('Starspangledbanner',2006,'AU','SIRE')} and len(reply['reviews'])==2,'explicit two individual answers and roles')
        for row in reply['reviews']:
            validate_user_answer(root,registry,reply,row)
        require(resolution['externally_confirmed']==18 and resolution['user_confirmed']==2 and resolution['resolved_total']==20 and resolution['remaining']==0,'country resolution counts')
        require(resolution['total_snapshots']==16 and resolution['previous_snapshots_preserved']==14 and len(resolution['snapshots'])==2,'append-only snapshot count')
        for summary in resolution['snapshots']:
            obj=read(root/summary['snapshot']);definition=read(root/summary['definition'])
            require(obj['content_sha256']==summary['hash']==digest({k:v for k,v in obj.items() if k!='content_sha256'}),'user resolution snapshot hash')
            require((root/summary['snapshot']).stat().st_size==summary['bytes'] and definition['data_cutoff']==reply['data_cutoff'] and definition['mode']=='REPLAY','user resolution time and bytes')
            previous=next(p for p in progress['snapshots'] if p['scope']==summary['scope'])
            require(summary['input']==previous['input'] and obj['all_runners']==summary['all_runners']==previous['all_runners'] and len(obj['groups'])==summary['groups']==43,'user resolution unchanged results and denominator')
            require(all(g['cohorts']['UNKNOWN']['entries']==g['cohorts']['CONFLICT']['entries']==0 for g in obj['groups'].values()) and summary['unknown_entries']==summary['conflict_entries']==0,'all foreign country missing resolved')
            expected='COMPLETE' if summary['scope']=='official-three' else 'PARTIAL'
            require(obj['completeness']==summary['completeness']==expected,'BHA pending cannot become complete')
        result.update(added_snapshots=12,foreign_country_user_confirmed=2,foreign_country_waiting=0,total_snapshots=16)
    return result

def validate_user_answer(root,registry,reply,row):
    record=read(registry.path(row['horse_key']));n=len(row['before_revision_hashes'])
    before=copy.deepcopy(record);before['revisions']=before['revisions'][:n]
    require(record['identity']['birth_year']==row['birth_year'] and norm(record['identity']['name'])==norm(row['name']),'user answer own identity')
    require(digest(before)==row['before_record_hash'] and digest(record)==row['after_record_hash'] and [r['content_hash'] for r in before['revisions']]==row['before_revision_hashes'],'user answer original record prefix')
    revision=record['revisions'][-1];registry.validate_fact(revision)
    source=revision['source']
    require(revision['revision_id']==row['added_revision_id'] and revision['field']=='attribute:training_country_user' and revision['value']==row['country'],'user answer revision and country')
    require(source.get('source_class')=='USER_PROVIDED' and source.get('resolution_policy')=='USER_EXPLICIT_COUNTRY_V1' and source.get('subject_name')==row['name'] and source.get('record_key')==row['horse_key'],'user answer explicit source binding')
    require(source.get('user_reply_text')==reply['user_reply_text'] and source.get('record_hash')==reply['user_reply_sha256'] and source.get('user_received_at')==reply['received_at'] and revision['first_observed_at']==reply['received_at'],'user answer exact text and receipt time')
    require(row['repeated_save_added']==0 and registry.fact(row['horse_key'],'attribute:training_country_user',reply['historical_cutoff'])['status']=='NOT_FOUND','user answer idempotence and old cutoff')
    require(registry.fact(row['horse_key'],'attribute:training_country_user',reply['data_cutoff'])['value']==row['country'],'user answer available only at new cutoff')

if __name__=='__main__': print(json.dumps(check(),ensure_ascii=False))
