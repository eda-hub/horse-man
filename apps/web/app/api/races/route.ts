import { z } from "zod";
import { database, digest, eventStatement, listRaces } from "@/db/store";
import { canBet, importSchema, raceKey, reasons, validateRace, type State } from "@/lib/domain";
export const dynamic="force-dynamic";
function json(data:unknown,status=200){return Response.json(data,{status,headers:{"Cache-Control":"no-store"}});}
function owner(req:Request){const id=req.headers.get("oai-authenticated-user-id");if(!id)throw new Error("AUTH");return id;}
function failure(e:unknown){if(e instanceof z.ZodError)return json({error:"予想ファイルの形式が違います。"+e.issues.slice(0,3).map(x=>`${x.path.join(".")}: ${x.message}`).join(" / ")},400);const m=e instanceof Error?(e.message+" "+(e.cause instanceof Error?e.cause.message:"")).trim():"";if(m==="AUTH")return json({error:"サインインしてから操作してください"},401);if(/UNIQUE constraint/.test(m))return json({error:"別の操作で記録が更新されました。再読み込みしてもう一度お試しください"},409);if(m.startsWith("INPUT:"))return json({error:m.slice(6)},400);console.error("horse-man storage",e);return json({error:"記録を読み書きできませんでした。入力内容を残したまま再試行してください"},503);}
export async function GET(req:Request){try{return json({races:await listRaces(owner(req))});}catch(e){return failure(e);}}
export async function POST(req:Request){try{
 const uid=owner(req);const origin=req.headers.get("origin");if(origin&&origin!==new URL(req.url).origin)return json({error:"この画面から操作してください"},403);
 const raw=await req.text();if(raw.length>2_000_000)return json({error:"ファイルが大きすぎます（2MBまで）"},413);
 const body=JSON.parse(raw);const db=database();
 if(body.action==="import"){
  const pack=importSchema.parse(body.data);const existing=await listRaces(uid);const map=new Map(existing.map(r=>[r.key,r]));const statements:D1PreparedStatement[]=[];let added=0;const keys=new Set<string>();
  for(const input of pack.races){try{validateRace(input,pack.demo);}catch(e){throw new Error("INPUT:"+(e as Error).message);}
   const key=raceKey(input,pack.demo),stage=input.snapshot.stage;if(keys.has(`${key}:${stage}`))throw new Error("INPUT:同じレース・時点が重複しています");keys.add(`${key}:${stage}`);
   const current=map.get(key);const saved=stage==="INITIAL"?current?.initial:current?.final;
   if(saved){if(await digest(saved)!==await digest(input))throw new Error("INPUT:保存済みの予想を上書きできません。同じデータを再度取り込むことはできます");continue;}
   if(stage==="FINAL"){
    if(!current||(!current.state.verify&&!current.state.purchase))throw new Error("INPUT:初回予想から候補を選んだレースだけ最終予想を取り込めます");
    if(current.initial.snapshot.baseline_forecast_id!==input.snapshot.baseline_forecast_id)throw new Error("INPUT:初回予想と最終予想の基準が一致しません");
    const a=current.initial;
    const identity=(x:typeof input)=>x.snapshot.horses.map(h=>({number:h.number,name:h.name,rank:h.rank,mark:h.mark,win_probability:h.win_probability})).sort((x,y)=>x.number-y.number);
    if(JSON.stringify(identity(a))!==JSON.stringify(identity(input)))throw new Error("INPUT:同じ基準予想の順位・印・確率を変更できません。正式な基準更新は予想エンジン側で行ってください");
    if(a.starts_at!==input.starts_at||a.venue!==input.venue||a.number!==input.number||a.course!==input.course||a.name!==input.name)throw new Error("INPUT:初回予想とレース情報が一致しません");
    if(Date.parse(input.snapshot.data_cutoff)<Date.parse(a.snapshot.data_cutoff))throw new Error("INPUT:最終予想のデータ時点が初回予想より前です");
   }
   statements.push(db.prepare("INSERT INTO race_snapshots (id,owner,race_key,date,stage,demo,payload,digest,stored_at) VALUES (?,?,?,?,?,?,?,?,?)").bind(crypto.randomUUID(),uid,key,input.date,stage,pack.demo?1:0,JSON.stringify(input),await digest(input),new Date().toISOString()));added++;
  }
  if(statements.length)await db.batch(statements);return json({added,races:await listRaces(uid)});
 }
 const command=z.object({action:z.enum(["candidate","decision","note"]),key:z.string().max(200),revision:z.number().int().min(0),operation_id:z.string().uuid(),verify:z.boolean().optional(),purchase:z.boolean().optional(),decision:z.enum(["BET","SKIP"]).optional(),reason:z.string().max(50).optional(),note:z.string().max(2000).optional(),amount:z.number().int().min(0).max(1000000).optional()}).strict().parse(body);
 const replay=await db.prepare("SELECT owner,race_key,kind,revision,state FROM race_events WHERE id=?").bind(command.operation_id).first<any>();
 if(replay){
 const prior=JSON.parse(replay.state) as State;
 const same=command.action==="candidate"?prior.verify===command.verify&&prior.purchase===command.purchase:command.action==="note"?prior.note===(command.note||"").trim():prior.decision===command.decision&&prior.note===(command.note||"").trim()&&prior.amount===(command.decision==="BET"?command.amount:0)&&prior.reason===(command.decision==="SKIP"?command.reason:"");
 if(replay.owner!==uid||replay.race_key!==command.key||replay.kind!==command.action||replay.revision!==command.revision+1||!same)throw new Error("INPUT:同じ操作識別で異なる内容を保存できません");
 return json({races:await listRaces(uid)});
 }
 const r=(await listRaces(uid)).find(x=>x.key===command.key);if(!r)return json({error:"レースが見つかりません"},404);
 if(r.state.revision!==command.revision)return json({error:"記録が更新されています。再読み込みしてもう一度お試しください"},409);
 const state:State={...r.state,revision:r.state.revision+1,at:new Date().toISOString()};
 if(command.action==="candidate"){
  if(r.state.decision)throw new Error("INPUT:判断記録があるレースの候補を変更できません");if(command.verify===undefined||command.purchase===undefined)throw new Error("INPUT:候補を指定してください");state.verify=command.verify;state.purchase=command.purchase;
 }else if(command.action==="decision"){
  if(!command.decision)throw new Error("INPUT:判断を選んでください");
  if(command.decision==="BET"&&!canBet(r))throw new Error("INPUT:購入候補・発走前の最終予想・買い目が必要です");
  if(command.decision==="BET"&&(!command.amount||command.amount%100!==0))throw new Error("INPUT:購入判断の金額を100円単位で入力してください");
  if(command.decision==="SKIP"&&(!command.reason||!reasons[command.reason]))throw new Error("INPUT:見送り理由を選んでください");
  if(command.decision==="SKIP"&&command.reason==="OTHER"&&!command.note?.trim())throw new Error("INPUT:その他の見送り理由を入力してください");
  state.decision=command.decision;state.reason=command.decision==="SKIP"?command.reason!:"";state.note=command.note?.trim()||"";state.amount=command.decision==="BET"?command.amount!:0;state.snapshot_id=(r.final||r.initial).snapshot.snapshot_id;
 }else{if(!command.note?.trim())throw new Error("INPUT:メモを入力してください");state.note=command.note.trim();}
 await eventStatement(uid,r.key,command.action,state,command.operation_id).run();return json({races:await listRaces(uid)});
 }catch(e){if(e instanceof SyntaxError)return json({error:"JSONファイルを読み込めませんでした"},400);return failure(e);}}
