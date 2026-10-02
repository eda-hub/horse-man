import assert from 'node:assert/strict';
import { randomUUID } from 'node:crypto';
import { readFileSync, realpathSync, readdirSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { pathToFileURL } from 'node:url';
let mf;
let transport=fetch;
if(process.env.HORSE_TEST_MINIFLARE==='1'){
 const path=resolve(dirname(realpathSync('node_modules/wrangler')),'miniflare/dist/src/index.js');
 const {Miniflare}=await import(pathToFileURL(path).href);
 mf=new Miniflare({modulesRoot:resolve('dist/server'),modules:readdirSync('dist/server',{recursive:true}).filter(p=>p.endsWith('.js')||p.endsWith('.mjs')).sort((a,b)=>a==='index.js'?-1:b==='index.js'?1:a.localeCompare(b)).map(p=>({type:'ESModule',path:resolve('dist/server',p)})),compatibilityDate:'2026-05-15',compatibilityFlags:['nodejs_compat'],d1Databases:{DB:'test-db'},assets:{directory:resolve('dist/client'),binding:'ASSETS',routerConfig:{has_user_worker:true,invoke_user_worker_ahead_of_assets:true}}});
 const db=await mf.getD1Database('DB');
 const sql=readFileSync('drizzle/0000_broken_shooting_star.sql','utf8').replaceAll('--> statement-breakpoint','');
 for(const statement of sql.split(';').map(x=>x.trim()).filter(Boolean))await db.prepare(statement).run();
 transport=(url,init)=>mf.dispatchFetch(url,init);
}
const base=process.env.HORSE_TEST_ORIGIN||'http://127.0.0.1:4173';
const owner='qa-'+randomUUID();
async function request(body,status=200,id=owner,extra={}){const response=await transport(base+'/api/races',{method:body?'POST':'GET',headers:{...(id?{'oai-authenticated-user-id':id}:{}),...(body?{'Content-Type':'application/json'}:{}),...extra},body:body?JSON.stringify(body):undefined});const raw=await response.text();let data;try{data=JSON.parse(raw);}catch{throw new Error(`API returned ${response.status}: ${raw.slice(0,600)} [${[...response.headers]}]`);}assert.equal(response.status,status,JSON.stringify(data));return data;}
const date='2099-10-03';
function race(stage='INITIAL',n=1){return {race_id:'qa-'+n,date,venue:'検証用',number:n,name:'API検証用レース',starts_at:date+'T15:00:00+09:00',course:'芝 1600m',going:'良',snapshot:{snapshot_id:stage+'-'+n,baseline_forecast_id:'base-'+n,stage,manual_release:'v1.6.1',module_hashes:{},data_cutoff:date+'T09:00:00+09:00',created_at:date+'T09:30:00+09:00',source:'APIテスト用の架空データ',summary:'テスト用',recommendation:'PURCHASE',confidence:'中',horses:[{number:1,name:'検証馬',mark:'◎',rank:1,win_probability:.2,reason:'検証',observed_odds:null,predicted_final_odds:6,odds_range:[5,7]}],tickets:stage==='FINAL'?[{type:'単勝',selection:'1',amount:300,condition:'検証用'}]:[],buy_condition:'テスト',skip_condition:'テスト'}};}
const pack=(races,demo=true)=>({action:'import',data:{schema_version:'horse-man-webui-v1',demo,races}});
try {
await request(undefined,401,null);
await request(pack([race()]),403,owner,{Origin:'https://other.example'});
assert.equal((await request(undefined)).races.length,0);
let data=await request(pack([race(),race('INITIAL',2)]));assert.equal(data.added,2);assert.equal(data.races.length,2);
assert.equal((await request(pack([race()]))).added,0);
assert.equal((await request(undefined,200,'other-'+randomUUID())).races.length,0);
const key=data.races.find(x=>x.initial.number===1).key;
await request(pack([race('FINAL')]),400);
const act=(action,revision,extra={})=>({action,key,revision,operation_id:randomUUID(),...extra});
await request(act('decision',0,{decision:'BET',amount:300}),400);
const candidate=act('candidate',0,{verify:true,purchase:true});
data=await request(candidate);assert.equal(data.races.find(x=>x.key===key).state.revision,1);
await request({...candidate,purchase:false},400);
await request(candidate);assert.equal((await request(undefined)).races.find(x=>x.key===key).history.length,1);
await request(act('candidate',0,{verify:false,purchase:false}),409);
const mismatch=race('FINAL');mismatch.snapshot.baseline_forecast_id='other';await request(pack([mismatch]),400);
const rankChange=race('FINAL');rankChange.snapshot.horses[0].win_probability=.4;await request(pack([rankChange]),400);
await request(pack([race('FINAL')]));
const altered=race('FINAL');altered.snapshot.summary='上書き';await request(pack([altered]),400);
await request(act('decision',1,{decision:'SKIP'}),400);
await request(act('decision',1,{decision:'SKIP',reason:'OTHER',note:''}),400);
await request(act('decision',1,{decision:'BET',amount:333}),400);
await request(act('decision',1,{decision:'SKIP',reason:'RESEARCH',note:'購入なし'}));
data=await request(undefined);let r=data.races.find(x=>x.key===key);assert.equal(r.state.decision,'SKIP');assert.equal(r.final.snapshot.tickets[0].amount,300);
await request(act('candidate',2,{verify:false,purchase:false}),400);
await request(act('decision',2,{decision:'BET',amount:300,note:'購入判断の訂正'}));
r=(await request(undefined)).races.find(x=>x.key===key);assert.equal(r.state.amount,300);assert.equal(r.history.length,3);assert.equal(r.history[1].state.decision,'SKIP');
const clone=race('INITIAL',3);await request(pack([clone],false),400);
const coreHashes=Object.fromEntries(['00_core','10_prediction','20_conditional','30_betting'].map(k=>[k,'a'.repeat(64)]));clone.snapshot.module_hashes=coreHashes;await request(pack([clone],false),400);clone.date='2020-01-01';clone.starts_at='2020-01-01T15:00:00+09:00';clone.snapshot.created_at='2020-01-01T09:30:00+09:00';clone.snapshot.data_cutoff='2020-01-01T09:00:00+09:00';await request(pack([clone],false));
const future=race('INITIAL',4);future.snapshot.data_cutoff=date+'T12:00:00+09:00';await request(pack([future]),400);
const replay=race('INITIAL',4);replay.snapshot.created_at=date+'T16:00:00+09:00';await request(pack([replay]),400);
const past=race('INITIAL',5);past.date='2000-01-01';past.starts_at='2000-01-01T15:00:00+09:00';past.snapshot.data_cutoff='2000-01-01T09:00:00+09:00';past.snapshot.created_at='2000-01-01T09:30:00+09:00';await request(pack([past]));
const pk=(await request(undefined)).races.find(x=>x.initial.number===5).key;await request({action:'candidate',key:pk,revision:0,operation_id:randomUUID(),verify:true,purchase:true});const pf=structuredClone(past);pf.snapshot.stage='FINAL';pf.snapshot.snapshot_id='past-final';pf.snapshot.tickets=race('FINAL').snapshot.tickets;await request(pack([pf]));await request({action:'decision',key:pk,revision:1,operation_id:randomUUID(),decision:'BET',amount:300},400);
const html=await (await transport(base)).text();assert.ok(html.includes('horse-man'));assert.ok(html.includes('初回予想'));assert.ok(!html.includes('Your site is taking shape'));
console.log('PASS: import, candidate selection, candidate-only FINAL, basis preservation, immutable FINAL, skip and purchase history, persistence read-back, duplicate retry, stale revisions, owner isolation, authentication, origin restriction, module hashes, cutoff, replay and past-race guards, page rendering.');

} finally { if(mf)await mf.dispose(); }
