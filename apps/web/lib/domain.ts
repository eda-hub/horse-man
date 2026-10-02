import { z } from "zod";
export const RELEASE = "v1.6.1";
const stamp=z.string().datetime({offset:true});
const odd=z.number().positive().max(100000).nullable();
const horse=z.object({number:z.number().int().min(1).max(18),name:z.string().min(1).max(80),mark:z.enum(["◎","○","▲","△","☆","無印"]),rank:z.number().int().positive(),win_probability:z.number().min(0).max(1).nullable(),reason:z.string().max(1500),observed_odds:odd,predicted_final_odds:odd,odds_range:z.tuple([z.number().positive(),z.number().positive()]).nullable()}).strict();
const ticket=z.object({type:z.enum(["単勝","複勝","馬連","馬単","ワイド","三連複","三連単","枠連"]),selection:z.string().min(1).max(120),amount:z.number().int().min(100).max(1000000).refine(n=>n%100===0,"金額は100円単位です"),condition:z.string().max(1500)}).strict();
export const snapshotSchema=z.object({snapshot_id:z.string().min(1).max(120),baseline_forecast_id:z.string().min(1).max(120),stage:z.enum(["INITIAL","FINAL"]),manual_release:z.literal(RELEASE),module_hashes:z.record(z.string().regex(/^[a-f0-9]{64}$/)),data_cutoff:stamp,created_at:stamp,source:z.string().min(1).max(500),summary:z.string().min(1).max(2500),recommendation:z.enum(["VERIFY","PURCHASE","SKIP"]),confidence:z.enum(["高","中","低","未評価"]),horses:z.array(horse).min(1).max(18),tickets:z.array(ticket).max(100),buy_condition:z.string().max(2500),skip_condition:z.string().max(2500)}).strict();
export const raceSchema=z.object({race_id:z.string().regex(/^[a-zA-Z0-9_-]{1,100}$/),date:z.string().regex(/^\d{4}-\d{2}-\d{2}$/),venue:z.string().min(1).max(30),number:z.number().int().min(1).max(12),name:z.string().min(1).max(120),starts_at:stamp,course:z.string().min(1).max(80),going:z.string().min(1).max(40),snapshot:snapshotSchema}).strict();
export const importSchema=z.object({schema_version:z.literal("horse-man-webui-v1"),demo:z.boolean().default(false),races:z.array(raceSchema).min(1).max(72)}).strict();
export type RaceInput=z.infer<typeof raceSchema>;
export type Snapshot=z.infer<typeof snapshotSchema>;
export type State={verify:boolean;purchase:boolean;decision:"BET"|"SKIP"|null;reason:string;note:string;amount:number;at:string|null;snapshot_id:string|null;revision:number};
export const blankState:State={verify:false,purchase:false,decision:null,reason:"",note:"",amount:0,at:null,snapshot_id:null,revision:0};
export type Race={key:string;initial:RaceInput;final:RaceInput|null;demo:boolean;state:State;history:{id:string;kind:string;state:State;at:string}[];stored_at:string;final_stored_at:string|null};
export const reasons:{[key:string]:string}={ODDS:"買い条件を満たさない",UNCERTAIN:"予想の確信が足りない",DATA:"必要な情報が不足",BUDGET:"予算・点数を抑える",RESEARCH:"検証のみ・購入なし",OTHER:"その他"};
export function validateRace(r:RaceInput,demo:boolean){
 const s=r.snapshot;
 if(Number.isNaN(Date.parse(r.starts_at))||r.date!==new Date(r.starts_at).toLocaleDateString("sv-SE",{timeZone:"Asia/Tokyo"})) throw new Error("開催日と日本時間の発走日が一致しません");
 if(Date.parse(s.data_cutoff)>Date.parse(s.created_at)) throw new Error("データ時点が予想作成時刻より後です");
 if(Date.parse(s.created_at)>=Date.parse(r.starts_at)) throw new Error("発走前に作成した予想だけを取り込めます。発走後の再演は対象外です");
 if(!demo&&Date.parse(s.created_at)>Date.now()) throw new Error("未来の作成時刻を持つ実予想は取り込めません");
 if(!demo&&!["00_core","10_prediction","20_conditional","30_betting"].every(k=>s.module_hashes[k])) throw new Error("現行ルールの使用モジュールhashが不足しています");
 if(new Set(s.horses.map(h=>h.number)).size!==s.horses.length||new Set(s.horses.map(h=>h.rank)).size!==s.horses.length) throw new Error("馬番または順位が重複しています");
 if(s.horses.filter(h=>h.mark==="◎").length!==1) throw new Error("基準予想の◎は1頭必要です");
 if(s.horses.some(h=>h.odds_range&&h.odds_range[0]>h.odds_range[1])) throw new Error("予測オッズのレンジが逆転しています");
}
export function raceKey(r:RaceInput,demo:boolean){return `${demo?"demo":"real"}:${r.date}:${r.race_id}`;}
export function canBet(r:Race,now=Date.now()){return !!r.final&&r.state.purchase&&Date.parse(r.initial.starts_at)>now&&r.final.snapshot.tickets.length>0;}
