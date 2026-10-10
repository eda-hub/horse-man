"""海外候補の原HTML・公式親情報・独立ID・5代・追記時点を照合する。"""
import base64, copy, gzip, hashlib, json, re, unicodedata
from pathlib import Path
from html.parser import HTMLParser
from pedigree_registry import Registry, digest, dt

def norm(s):
 s=unicodedata.normalize('NFKC',s)
 s=re.sub(r'\s*\((?:[A-Z]{2,3}|米|英|仏|独|愛|加|伊|豪|日|亜|南阿|新|智|巴)\)\s*$','',s)
 s=s.replace('リアルシヤダイ','リアルシャダイ').replace('ダイナフエアリー','ダイナフェアリー')
 s=re.sub(r'(?<=[ァ-ヿ])II$', '2', s)
 s=s.translate(str.maketrans('ァィゥェォャュョッヮ','アイウエオヤユヨツワ'))
 return re.sub(r"[\s’'・.‐‑–-]",'',s).casefold()

class Node:
 def __init__(self, tag, attrs=()):self.tag=tag;self.attrs=dict(attrs);self.items=[]
 def children(self,tag):return [x for x in self.items if isinstance(x,Node) and x.tag==tag]
 def walk(self,tag):
  for x in self.items:
   if isinstance(x,Node):
    if x.tag==tag:yield x
    yield from x.walk(tag)
 def text_content(self):return ''.join(x.text_content() if isinstance(x,Node) else x for x in self.items)
 def get(self,key,default=None):return self.attrs.get(key,default)

class Document(HTMLParser):
 def __init__(self,body):
  super().__init__(convert_charrefs=True);self.root=Node('document');self.stack=[self.root];self.feed(body.decode('euc_jp',errors='replace'))
 def handle_starttag(self,tag,attrs):
  n=Node(tag,attrs);self.stack[-1].items.append(n)
  if tag not in {'area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'}:self.stack.append(n)
 def handle_endtag(self,tag):
  for i in range(len(self.stack)-1,0,-1):
   if self.stack[i].tag==tag:del self.stack[i:];break
 def handle_data(self,data):self.stack[-1].items.append(data)

def parse_table(t):
 tables=[n for n in t.walk('table') if 'blood_table' in n.get('class','').split()];assert len(tables)==1
 rows=[r for r in tables[0].walk('tr') if r.children('td')];assert len(rows)==32
 spans=[0]*5;ancestors={}
 for i,row in enumerate(rows):
  col=0
  for cell in row.children('td'):
   while col<5 and spans[col]>i:col+=1
   assert col<5
   links=[a for a in cell.walk('a') if re.search(r'/horse/[a-zA-Z0-9]+/',a.get('href',''))];assert links
   a=links[0];id=re.search(r'/horse/([a-zA-Z0-9]+)/',a.get('href'))[1];txt=' '.join(cell.text_content().split());year=re.search(r'(?<!\d)(18\d{2}|19\d{2}|20\d{2})(?:年|\s)',txt)
   depth=col+1;position=i//(32//(2**depth));path=format(position,'0%db'%depth).translate(str.maketrans('01','SD'));assert path not in ancestors
   ancestors[path]={'id':id,'name':' '.join(a.text_content().split()),'birth_year':int(year[1]) if year else None};spans[col]=i+int(cell.get('rowspan','1'));col+=1
 assert len(ancestors)==62
 return ancestors

BASE=Path('data/pedigree/reconciliations/2026-10-10-foreign-review')

def check(root=Path('.')):
 root=Path(root);directory=root/BASE
 if not directory.exists():return {'registered_rows':0}
 registry=Registry(root/'data/pedigree');registered=0;positions=0
 official=json.loads((root/'data/pedigree/reconciliations/2026-10-09-followup/foreign_pedigree_evidence.json').read_text())['races'][0]['entries']
 results=json.loads((root/'data/pedigree/reconciliations/2026-10-09-followup/foreign_results_evidence.json').read_text())['races']
 assert len(results)==4 and sum(len(r['runners']) for r in results)==42
 assert sum(x['status']=='FINISHED' for r in results for x in r['runners'])==38
 assert sum(x['status']=='SCRATCHED' for r in results for x in r['runners'])==4
 for path in sorted(directory.glob('batch-*.json')):
  batch=json.loads(path.read_text());assert batch['mode']=='REPLAY' and batch['production_eligible'] is False
  raw=(root/batch['source_bundle_path']).read_bytes();assert hashlib.sha256(raw).hexdigest()==batch['source_bundle_sha256'];bundle=json.loads(gzip.decompress(raw))
  for entry in bundle.values():
   if 'body_base64' not in entry:continue
   body=base64.b64decode(entry['body_base64'],validate=True);m=entry['capture'];assert m['http_status']==200 and m['hash_kind']=='response-body-sha256' and hashlib.sha256(body).hexdigest()==m['sha256'] and len(body)==m['bytes'] and dt(m['captured_at'])<=dt(batch['data_cutoff'])
  for row in batch['rows']:
   id=row['target']['netkeiba_id'];ped=Document(base64.b64decode(bundle[id+'-pedigree']['body_base64'])).root;profile=Document(base64.b64decode(bundle[id+'-profile']['body_base64'])).root
   assert any(norm(n.text_content())==norm(row['target']['reported_name']) for n in ped.walk('h1'))
   parsed=parse_table(ped);assert parsed==row['ancestors'] and len(parsed)==62
   birth=next(tr.children('td')[0].text_content().strip() for tr in [tr for tr in profile.walk('tr') if tr.children('th')] if tr.children('th')[0].text_content().strip()=='生年月日');assert int(re.match(r'(\d{4})年',birth)[1])==row['birth_year']
   parent=next(p for p in official if p['horse_number']==int(row['target']['reported_horse_number']));assert parent==row['official_parent_evidence']
   result=next(r for r in results[0]['runners'] if r['horse_number']==parent['horse_number']);assert result['birth_year']==row['birth_year']
   assert all(norm(parsed[p]['name'])==norm(parent[f]) for p,f in [('S','sire'),('D','dam'),('DS','damsire')])
   assert row['registry_promoted'] and row['status']=='REGISTERED_5_GENERATIONS'
   for ancestry,key in row['ancestor_keys'].items():
    fact=registry.edge(row['horse_key'],ancestry,batch['data_cutoff']);assert fact['status']=='VERIFIED' and fact['value']==key
   registered+=1;positions+=62
  for receipt in batch['write_receipts']:
   record=json.loads(registry.path(receipt['horse_key']).read_text());assert digest(record)==receipt['after_record_hash'];n=len(receipt['before_revision_hashes']);assert [r['content_hash'] for r in record['revisions'][:n]]==receipt['before_revision_hashes']
   if not receipt['new_identity']:
    before=copy.deepcopy(record);before['revisions']=before['revisions'][:n];assert digest(before)==receipt['before_record_hash']
   assert [r['revision_id'] for r in record['revisions'][n:]]==receipt['added_revision_ids']
   for fact in record['revisions'][n:]:
    registry.validate_fact(fact);assert dt(fact['first_observed_at'])>dt(batch['historical_cutoff']) and dt(fact['captured_at'])>dt(batch['historical_cutoff'])
    assert registry.fact(receipt['horse_key'],fact['field'],batch['historical_cutoff']).get('revision_id') not in receipt['added_revision_ids']
    assert fact['source']['record_hash'] in {e['capture'].get('sha256') for e in bundle.values()} and dt(fact['captured_at'])<=dt(batch['data_cutoff'])
   assert sum(len(r['added_revision_ids']) for r in batch['write_receipts'])==batch['new_parent_revisions']
  assert batch['registry_promoted']==len(batch['rows'])
 return {'scope_rows':42,'registered_rows':registered,'ancestor_positions':positions,'remaining_rows':42-registered,'finished':38,'scratched':4}

if __name__=='__main__':
 print(json.dumps(check(),ensure_ascii=False))
