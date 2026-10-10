#!/usr/bin/env python3
"""資料確認済み一覧11〜30番目を、原文・Writer履歴・時点で監査する。"""
import hashlib,html,json,re,subprocess
from pathlib import Path
from pedigree_registry import Registry,digest,dt,stamp

BASE=Path('data/pedigree/reconciliations/2026-10-10-training-priority')
SCOPES={
 'r03':['0001138240','0000615577','0001155349','0001090360','0001189721'],
 'r04':['0001240055','0001171845','0000619768','0001104811','0001293348'],
 'r05':['0001170063','0001025279','0001302899','0001157711','0001205475'],
 'r06':['0000749845','0000286968','0001328857','0000324933','0001083691']}
NEW={'0001138240','0001025279','0000749845','0000286968','0001083691'}
FOREIGN={'0001240055':('Drefong (USA)','Bob Baffert',2013),'0001293348':('Bricks And Mortar (USA)','Chad Brown',2014),'0001302899':('Mind Your Biscuits (USA)','Chad Summers',2013)}
def require(ok,message):
 if not ok:raise ValueError(message)
def read(p):return json.loads(p.read_text())
def clean(s):return re.sub(r'\s+',' ',html.unescape(re.sub('<[^>]+>',' ',s))).strip()
def cells(s):return [clean(c) for c in re.findall('<t[dh][^>]*>(.*?)</t[dh]>',s,re.S|re.I)]
def check(root=Path('.')):
 root=Path(root);registry=Registry(root/'data/pedigree');review=read(root/BASE/'training-country-source-review.json');bykey={h['horse_key']:h for h in review['horses']};total=added=0
 for batch,ids in SCOPES.items():
  path=root/BASE/(batch+'-verification.json')
  if not path.exists():continue
  manifest=read(path);require(manifest['schema_version']=='training-country-reviewed-batch-v1' and manifest['batch']==batch,'manifest schema');require(manifest['mode']=='REPLAY' and manifest['production_eligible'] is False,'usage boundary');require([s['horse_key'] for s in manifest['subjects']]==['jbis-'+i for i in ids],'fixed batch scope')
  batch_added=0
  for subject in manifest['subjects']:
   key=subject['horse_key'];ident=key[5:];rp='data/pedigree/horses/'+key+'.json';require(subject['record_path']==rp,'record path');record=read(root/rp);n=len(subject['before_revision_hashes']);require([r['content_hash'] for r in record['revisions'][:n]]==subject['before_revision_hashes'],'old revisions preserved')
   before=dict(record,revisions=record['revisions'][:n]);require(digest(before)==subject['before_record_hash'],'original record hash')
   fact=next(r for r in record['revisions'] if r['revision_id']==subject['registry_revision_id']);registry.validate_fact(fact);require(fact['content_hash']==subject['registry_revision_content_hash']==digest({k:v for k,v in fact.items() if k!='content_hash'}),'revision hash');require(fact['field']=='attribute:training_country_matches' and fact['status']=='VERIFIED','training fact');require({m['country'] for m in fact['value']['matches']}=={subject['country']},'country')
   current=dict(record,revisions=record['revisions'][:n+(ident in NEW)]);require(digest(current)==subject['after_record_hash'],'saved record hash');require(subject['second_save_added_revisions']==[],'idempotent retry');new=ident in NEW;require(subject['operation']==('REGISTER_NEW_FACT' if new else 'IDEMPOTENT_EXISTING_FACT'),'operation');require(subject['writer_result']['added_revisions']==([fact['revision_id']] if new else []),'writer additions');batch_added+=new
   proofs=[]
   for mp in subject['raw_capture_metadata_paths']:
    meta=read(root/mp);role=meta['role'];expected=BASE/(batch+'-raw')/(key+'-'+role+'.capture.json');require(mp==str(expected),'capture metadata path');require(meta['horse_key']==key,'capture identity');bodypath=Path(meta['path']);require(bodypath.parent==BASE/(batch+'-raw') and bodypath.stem==key+'-'+role,'body path');body=(root/bodypath).read_bytes();require(hashlib.sha256(body).hexdigest()==meta['sha256'] and len(body)==meta['byte_length'],'raw hash/length');require(meta['hash_kind']=='http-response-body-bytes-sha256' and meta['http_status']==200 and meta['content_encoding'] in [None,'identity'],'HTTP provenance');require(dt(meta['request_started_at'])<=dt(meta['captured_at'])<=dt(manifest['verified_at'])<=dt(stamp()),'capture ordering');proofs.append((meta,body))
   pm,profile=proofs[0];require(pm['role']=='profile' and pm['requested_url']==pm['final_url']=='https://www.jbis.or.jp/horse/'+ident+'/','individual profile URL');profile=profile.decode('utf-8');require(subject['horse_name'] in html.unescape(re.search('<title>(.*?)</title>',profile,re.S).group(1)),'profile name');birth=clean(re.search(r'<dt>生年月日</dt>\s*<dd>(.*?)</dd>',profile,re.S).group(1))[:10];fields=subject['verified_fields'];require(int(birth[:4])==record['identity']['birth_year'] and birth==fields['birth_date'],'birth identity')
   if subject['country']=='JP':
    require(len(proofs)==1 and subject['proof_kind']=='JBIS_TRAINER_AFFILIATION','domestic evidence scope');block=re.search(r'<dt>調教師</dt>\s*<dd>(.*?)</dd>',profile,re.S).group(1);trainer=clean(re.search('<a[^>]*>(.*?)</a>',block,re.S).group(1));location=re.search(r'\(([^)]+)\)',block).group(1).replace(' ','');require(location in ['美浦','栗東'] and trainer==fields['trainer'] and location==fields['trainer_location'],'Japanese trainer affiliation')
   else:
    require(subject['country']=='US' and len(proofs)==2,'foreign scope');meta,body=proofs[-1]
    if ident in FOREIGN:
     name,trainer,year=FOREIGN[ident];require(meta['requested_url'].startswith('https://www.ifhaonline.org/resources/WTRRankings/'),'official country source');s=body.decode('cp1252');require('Trained' in s,'trained column');rows=[cells(r) for r in re.findall('<tr[^>]*>(.*?)</tr>',s,re.S|re.I)];row=next(r for r in rows if len(r)==10 and r[4]==name and r[5]==str(year) and r[8]==trainer and r[9]=='USA');require(row==fields['official_row'],'official identity/trainer/country row')
    elif ident=='0001025279':
     require(meta['requested_url']=='https://www.ifhaonline.org/resources/2006Rankings/2006_WorldRankings.asp','official source');s=body.decode('cp1252');require('Trained' in s,'trained header');rows=[cells(r) for r in re.findall('<tr[^>]*>(.*?)</tr>',s,re.S|re.I)];row=next(r for r in rows if len(r)==15 and r[5]=='SINISTER MINISTER (USA)' and r[6]=='3' and r[8]=='USA');require(row==fields['official_row'] and record['identity']['birth_year']==2003,'official 2006 identity/country')
    elif ident=='0000749845':
     require(meta['requested_url']=='https://www.ifhaonline.org/resources/Ratings_AlphaList_04.pdf' and body.startswith(b'%PDF'),'original PDF source');text=subprocess.check_output(['pdftotext','-layout',str(root/meta['path']),'-']).decode();require('Trained' in text and fields['official_row'] in text and re.search(r'Empire Maker \(USA\)\s+3\s+C\s+USA\s+Frankel, Robert J\.',fields['official_row']),'official PDF trained country');require(record['identity']['birth_year']==2000 and 'ベルモントS' in profile,'cross-source identity')
    elif ident=='0001083691':
     require(meta['requested_url']=='https://news.sp.netkeiba.com/?no=22698&pid=news_view','original article');text=clean(body.decode());require(all(m in text for m in ['Majestic Warrior','米・W.モット厩舎','2007年09月04日','Dream Supreme','A.P.Indy']),'explicit training/individual evidence');require(record['identity']['birth_year']==2005 and 'ホープフルS' in profile,'individual crosscheck')
    elif ident=='0001328857':
     require(meta['requested_url']=='https://cms.equibase.com/node/119804','replacement source');text=clean(body.decode());require(all(m in text for m in ['Nadal','Bob Baffert','flown back to California','May 2']),'California base');require(record['identity']['birth_year']==2017 and 'アーカンソーダービー' in profile,'cross-source identity')
    else:raise ValueError('unexpected horse')
   primary=proofs[-1][0];link=bykey[key]['raw_html_evidence'];require(link['metadata_path']==subject['raw_capture_metadata_paths'][-1] and link['path']==primary['path'] and link['sha256']==primary['sha256'],'review proof link')
   if new:require(fact['source']['record_hash']==primary['sha256'] and fact['captured_at']==primary['captured_at'] and fact['source']['url']==primary['requested_url'],'new provenance')
   else:require(dt(fact['captured_at'])<dt(primary['captured_at']),'supplement not backdated')
   require(registry.fact(key,'attribute:training_country_matches','2026-10-01T00:00:00+00:00')['status']!='VERIFIED','historical cutoff');total+=1
  require(manifest['added_registry_revisions']==batch_added,'batch addition count');added+=batch_added
 require(total in [5,10,15,20],'checkpoint count')
 return {'integrity':'PASS','verified_subjects':total,'added_revisions':added,'production_eligible':False}
if __name__=='__main__':print(json.dumps(check(),ensure_ascii=False,indent=2))
