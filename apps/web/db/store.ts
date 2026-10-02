import { env } from "cloudflare:workers";
import { blankState, type Race, type State } from "@/lib/domain";
export function database(){if(!env.DB)throw new Error("記録の保存先を利用できません");return env.DB;}
export async function listRaces(owner:string):Promise<Race[]>{
 const db=database();
 const [ss,es]=await Promise.all([db.prepare("SELECT * FROM race_snapshots WHERE owner=? ORDER BY date DESC,race_key,stage").bind(owner).all<any>(),db.prepare("SELECT * FROM race_events WHERE owner=? ORDER BY race_key,revision").bind(owner).all<any>()]);
 const map=new Map<string,Race>();
 for(const s of ss.results)if(s.stage==="INITIAL")map.set(s.race_key,{key:s.race_key,initial:JSON.parse(s.payload),final:null,demo:!!s.demo,state:{...blankState},history:[],stored_at:s.stored_at,final_stored_at:null});
 for(const s of ss.results)if(s.stage==="FINAL"&&map.has(s.race_key)){map.get(s.race_key)!.final=JSON.parse(s.payload);map.get(s.race_key)!.final_stored_at=s.stored_at;}
 for(const e of es.results){const r=map.get(e.race_key);if(r){const state=JSON.parse(e.state);r.state=state;r.history.push({id:e.id,kind:e.kind,state,at:e.at});}}
 return [...map.values()].sort((a,b)=>b.initial.date.localeCompare(a.initial.date)||a.initial.starts_at.localeCompare(b.initial.starts_at));
}
export async function digest(value:unknown){const bytes=new TextEncoder().encode(JSON.stringify(value));return Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256",bytes))).map(b=>b.toString(16).padStart(2,"0")).join("");}
export function eventStatement(owner:string,key:string,kind:string,state:State,id:string){return database().prepare("INSERT INTO race_events (id,owner,race_key,revision,kind,state,at) VALUES (?,?,?,?,?,?,?)").bind(id,owner,key,state.revision,kind,JSON.stringify(state),state.at);}
