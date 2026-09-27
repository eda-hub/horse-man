#!/usr/bin/env python3
import argparse, json, re, sys
from datetime import datetime
from pathlib import Path

SCHEMA = 'prediction-compliance-v1'
SUPPORTED_RELEASE = 'v1.6.1'
PAIR_TYPES = {'QUINELLA','WIDE','EXACTA'}
ALL_BET_TYPES = {'WIN','PLACE','QUINELLA','WIDE','EXACTA','TRIO','TRIFECTA'}
VERTICAL_REASON_CODES = {'INDEPENDENT_POSITIVE_EV'}
BETTING_EVIDENCE_SCHEMA = 'betting-evidence-v1'
RECEIPT_RECORD_TAG = 'persistence-receipt-v1'
KPI_STATES = {'ELIGIBLE','INELIGIBLE','PENDING','NOT_APPLICABLE'}
KNOWN_CONFLICTS = {'E-11'}
SNAPSHOT_RACE_ID_RE = re.compile(r'^snapshot_id:\s*(\d{8}-[A-Z]{3}-\d{2})-', re.M)
WHOLE_DAY_RACE_RE = re.compile(r'^\|\s*(中山|阪神)\s*(\d{1,2})R\b', re.M)

class ComplianceError(ValueError): pass

def iso(v, label):
    if not isinstance(v,str) or not v: raise ComplianceError(f'{label}: timestamp required')
    try: d=datetime.fromisoformat(v.replace('Z','+00:00'))
    except ValueError as e: raise ComplianceError(f'{label}: invalid timestamp') from e
    if d.tzinfo is None: raise ComplianceError(f'{label}: timezone required')
    return d

def req(o,k,label):
    v=o.get(k)
    if not isinstance(v,str) or not v: raise ComplianceError(f'{label}: {k} required')
    return v

def release(root):
    p=root/'docs/manual/README.md'; s=p.read_text(encoding='utf-8')
    m=re.search(r'現行リリース[^\x60\n]*\x60([^\x60]+)\x60',s)
    if not m: raise ComplianceError(f'{p}: release not found')
    return m.group(1)

def segment(path, ident):
    s=path.read_text(encoding='utf-8'); i=s.find(ident)
    if i<0: raise ComplianceError(f'{path}: evidence id not found: {ident}')
    return s[max(0,i-300):min(len(s),i+3000)]

def exact_record(path, tag, id_key, ident, label):
    matches=[o for o in blocks(path,tag) if isinstance(o,dict) and o.get(id_key)==ident]
    if len(matches)!=1:
        raise ComplianceError(f'{label}: expected exactly one {tag} record for {ident}, found {len(matches)}')
    return matches[0]

def evidence(root, ref, label, pre_race, scheduled_post=None):
    if not isinstance(ref,dict): raise ComplianceError(f'{label}: evidence_ref required')
    artifact_rel=req(ref,'artifact_path',label); ap=root/artifact_rel; aid=req(ref,'artifact_id',label)
    if not ap.is_file(): raise ComplianceError(f'{label}: artifact missing: {ap}')
    segment(ap,aid)
    if pre_race:
        receipt_rel=req(ref,'receipt_path',label); rp=root/receipt_rel; rid=req(ref,'receipt_id',label)
        if not rp.is_file(): raise ComplianceError(f'{label}: receipt missing: {rp}')
        rr=exact_record(rp,RECEIPT_RECORD_TAG,'receipt_id',rid,label+'/receipt')
        expected={
            'receipt_id':rid,
            'artifact_id':aid,
            'artifact_path':artifact_rel,
            'timing_eligibility':'PRE_RACE_ELIGIBLE',
            'artifact_persist_status':'PERSIST_VERIFIED',
            'receipt_persist_status':'RECEIPT_VERIFIED'
        }
        for k,v in expected.items():
            if rr.get(k)!=v: raise ComplianceError(f'{label}: receipt {k} mismatch')
        if ref.get('timing_eligibility')!='PRE_RACE_ELIGIBLE': raise ComplianceError(f'{label}: timing must be PRE_RACE_ELIGIBLE')
        verified=iso(ref.get('persist_verified_at_jst'),label+'/persist_verified_at_jst')
        receipt_verified=iso(rr.get('persist_verified_at_jst'),label+'/receipt/persist_verified_at_jst')
        if verified!=receipt_verified: raise ComplianceError(f'{label}: receipt persist_verified_at_jst mismatch')
        if scheduled_post is not None:
            receipt_post=iso(rr.get('scheduled_post_time_jst'),label+'/receipt/scheduled_post_time_jst')
            if receipt_post!=scheduled_post: raise ComplianceError(f'{label}: receipt scheduled_post_time_jst mismatch')
            if receipt_verified>=scheduled_post: raise ComplianceError(f'{label}: receipt verified at/after post time')
    return ap

def betting_evidence(root, ref, ticket, scenario_id, probability_low, odds, label, scheduled_post, race_id):
    ap=evidence(root,ref,label,True,scheduled_post)
    try: data=json.loads(ap.read_text(encoding='utf-8'))
    except json.JSONDecodeError as e: raise ComplianceError(f'{label}: betting evidence must be JSON') from e
    if not isinstance(data,dict) or data.get('schema_version')!=BETTING_EVIDENCE_SCHEMA:
        raise ComplianceError(f'{label}: betting evidence schema mismatch')
    if data.get('evidence_id')!=ref.get('artifact_id'):
        raise ComplianceError(f'{label}: betting evidence_id mismatch')
    if data.get('race_id')!=race_id:
        raise ComplianceError(f'{label}: betting evidence race_id mismatch')
    kind=req(ticket,'type',label); hs=ticket.get('horses')
    if not isinstance(hs,list) or not hs: raise ComplianceError(f'{label}: ticket horses required')
    target=tuple(sorted(hs))
    prices=[
        x for x in data.get('prices',[]) if isinstance(x,dict)
        and x.get('type')==kind and tuple(sorted(x.get('horses',[])))==target
    ]
    if len(prices)!=1: raise ComplianceError(f'{label}: exact price evidence record required')
    price=prices[0]
    if price.get('odds')!=odds: raise ComplianceError(f'{label}: odds do not match pre-race evidence')
    req(price,'source_url',label+'/price'); observed=iso(price.get('observed_at_jst'),label+'/price/observed_at_jst')
    if observed>=scheduled_post: raise ComplianceError(f'{label}: price observed at/after post time')
    probs=[
        x for x in data.get('probabilities',[]) if isinstance(x,dict)
        and x.get('type')==kind and tuple(sorted(x.get('horses',[])))==target
        and x.get('scenario_id')==scenario_id
    ]
    if len(probs)!=1: raise ComplianceError(f'{label}: exact probability evidence record required')
    prob=probs[0]
    if prob.get('probability_low')!=probability_low:
        raise ComplianceError(f'{label}: probability_low does not match pre-race evidence')
    req(prob,'method_ref',label+'/probability'); fixed=iso(prob.get('fixed_at_jst'),label+'/probability/fixed_at_jst')
    if fixed>=scheduled_post: raise ComplianceError(f'{label}: probability fixed at/after post time')

def pair(t,label):
    kind=req(t,'type',label); hs=t.get('horses')
    if kind not in PAIR_TYPES: return None
    if not isinstance(hs,list) or len(hs)!=2 or any(type(x) is not int or x<=0 for x in hs):
        raise ComplianceError(f'{label}: pair horses invalid')
    a,b=sorted(hs)
    if a==b: raise ComplianceError(f'{label}: duplicate horse')
    return a,b

def key(t,label):
    p=pair(t,label); return (req(t,'type',label), p if p else tuple(t.get('horses',[])))

def vertical(root,t,label,scheduled_post,race_id):
    e=t.get('vertical_exception')
    if not isinstance(e,dict): raise ComplianceError(f'{label}: non-anchor pair requires vertical_exception')
    reason=req(e,'reason_code',label)
    if reason not in VERTICAL_REASON_CODES:
        raise ComplianceError(f'{label}: vertical reason_code not allowed: {reason}')
    scenario=req(e,'scenario_id',label)
    p=e.get('probability_low'); odds=e.get('odds'); declared=e.get('ev_low')
    if not isinstance(p,(int,float)) or not 0<p<=1: raise ComplianceError(f'{label}: probability_low invalid')
    if not isinstance(odds,(int,float)) or odds<=1: raise ComplianceError(f'{label}: odds invalid')
    ev=p*odds
    if not isinstance(declared,(int,float)) or abs(declared-ev)>1e-6: raise ComplianceError(f'{label}: ev_low mismatch')
    if ev<=1.0: raise ComplianceError(f'{label}: conservative EV must be > 1.0')
    betting_evidence(root,e.get('evidence_ref'),t,scenario,p,odds,label+'/evidence',scheduled_post,race_id)

def betting(root, b, marks, label, scheduled_post, race_id):
    if not isinstance(b,dict): raise ComplianceError(f'{label}: betting object required')
    st=req(b,'status',label)
    if st not in {'NOT_REQUIRED','SKIP','BLOCKED','FIXED'}: raise ComplianceError(f'{label}: invalid status')
    if st!='FIXED': return
    if b.get('audit_status')!='PASS': raise ComplianceError(f'{label}: FIXED requires audit PASS')
    decisions=b.get('ticket_type_decisions')
    if not isinstance(decisions,dict) or set(decisions) != ALL_BET_TYPES:
        raise ComplianceError(f'{label}: ticket_type_decisions must cover all bet types')
    for kind,obj in decisions.items():
        if not isinstance(obj,dict): raise ComplianceError(f'{label}/{kind}: decision object required')
        state=req(obj,'status',f'{label}/{kind}')
        if state not in {'SELECTED','REJECTED','UNAVAILABLE','NOT_APPLICABLE'}:
            raise ComplianceError(f'{label}/{kind}: invalid decision status')
        req(obj,'reason',f'{label}/{kind}')
    anchor=marks.get('honmei'); opp=marks.get('taikou')
    if type(anchor) is not int or type(opp) is not int: raise ComplianceError(f'{label}: honmei/taikou required')
    tickets=b.get('tickets'); natural=b.get('natural_candidates'); rejected=b.get('rejected_candidates')
    if not isinstance(tickets,list) or not tickets: raise ComplianceError(f'{label}: tickets required')
    if not isinstance(natural,list) or not isinstance(rejected,list): raise ComplianceError(f'{label}: natural/rejected candidates required')
    nk={key(x,label+'/natural') for x in natural}; rk={key(x,label+'/rejected') for x in rejected}; ak=set(); total=0; kinds=set()
    for i,t in enumerate(tickets):
        tl=f'{label}/tickets[{i}]'; amount=t.get('amount_yen')
        if type(amount) is not int or amount<=0: raise ComplianceError(f'{tl}: positive amount required')
        total+=amount; ak.add(key(t,tl)); p=pair(t,tl)
        if p:
            kinds.add(t['type'])
            if anchor not in p: vertical(root,t,tl,scheduled_post,race_id)
    selected_types={t.get('type') for t in tickets}
    for kind,obj in decisions.items():
        if obj['status']=='SELECTED' and kind not in selected_types:
            raise ComplianceError(f'{label}/{kind}: SELECTED but no adopted ticket')
        if kind in selected_types and obj['status']!='SELECTED':
            raise ComplianceError(f'{label}/{kind}: adopted ticket requires SELECTED decision')
    if ak-nk: raise ComplianceError(f'{label}: adopted ticket missing from natural_candidates')
    if nk-ak-rk: raise ComplianceError(f'{label}: natural candidate lacks adopt/reject decision')
    main=tuple(sorted((anchor,opp)))
    for kind in kinds:
        if (kind,main) not in nk: raise ComplianceError(f'{label}: {kind} missing natural honmei-taikou candidate')
    budget_kind=b.get('budget_kind')
    if budget_kind not in {'VALIDATION_FIXED','USER_BUDGET'}: raise ComplianceError(f'{label}: invalid budget_kind')
    if budget_kind=='VALIDATION_FIXED' and total!=10000: raise ComplianceError(f'{label}: validation stake must be 10000')
    if b.get('total_stake_yen')!=total: raise ComplianceError(f'{label}: stake total mismatch')
    if budget_kind=='USER_BUDGET':
        plan=b.get('validation_stake_plan')
        if not isinstance(plan,dict): raise ComplianceError(f'{label}: USER_BUDGET requires separate validation_stake_plan')
        vt=plan.get('tickets')
        if not isinstance(vt,list) or not vt: raise ComplianceError(f'{label}: validation_stake_plan tickets required')
        vtotal=0
        for i,t in enumerate(vt):
            tl=f'{label}/validation_stake_plan/tickets[{i}]'
            amount=t.get('amount_yen')
            if type(amount) is not int or amount<=0: raise ComplianceError(f'{tl}: positive amount required')
            vtotal+=amount
            if key(t,tl) not in nk: raise ComplianceError(f'{tl}: validation ticket missing from natural_candidates')
            p=pair(t,tl)
            if p and anchor not in p: vertical(root,t,tl,scheduled_post,race_id)
        if plan.get('total_stake_yen')!=vtotal: raise ComplianceError(f'{label}: validation_stake_plan total mismatch')
        if vtotal!=10000: raise ComplianceError(f'{label}: separate validation stake must be 10000')

def review(rv, gate, mode, label):
    if not isinstance(rv,dict): raise ComplianceError(f'{label}: review object required')
    st=req(rv,'status',label)
    if st=='NOT_STARTED': return
    if st!='COMPLETE': raise ComplianceError(f'{label}: invalid review status')
    src=rv.get('result_sources')
    if not isinstance(src,list) or not src: raise ComplianceError(f'{label}: result_sources required')
    post=iso(gate['scheduled_post_time_jst'],label+'/post')
    for i,x in enumerate(src):
        req(x,'url',f'{label}/source[{i}]'); rt=iso(x.get('retrieved_at_jst'),f'{label}/source[{i}]')
        if rt<post: raise ComplianceError(f'{label}: result retrieved before post time')
    if rv.get('counterfactual_check') not in {'SAME','DIFFERENT','UNDETERMINED'}: raise ComplianceError(f'{label}: counterfactual_check required')
    result=rv.get('result')
    if not isinstance(result,dict) or not isinstance(result.get('top3'),list) or len(result.get('top3'))!=3 or any(type(x) is not int or x<=0 for x in result.get('top3',[])):
        raise ComplianceError(f'{label}: result.top3 required')
    ec=rv.get('error_classification')
    if not isinstance(ec,dict): raise ComplianceError(f'{label}: error_classification required')
    primary=req(ec,'primary',label+'/error_classification')
    if primary not in set('ABCDEFGHIJKL')|{'NONE','UNDETERMINED'}:
        raise ComplianceError(f'{label}: invalid primary error classification')
    secondary=ec.get('secondary',[])
    if not isinstance(secondary,list) or any(x not in set('ABCDEFGHIJKL') for x in secondary):
        raise ComplianceError(f'{label}: invalid secondary error classification')
    la=rv.get('layer_assessment')
    if not isinstance(la,dict) or set(la) != {'prediction','price','betting'}:
        raise ComplianceError(f'{label}: layer_assessment prediction/price/betting required')
    allowed_layers={'PASS','FAIL','PARTIAL','NOT_APPLICABLE','UNDETERMINED'}
    if any(v not in allowed_layers for v in la.values()):
        raise ComplianceError(f'{label}: invalid layer_assessment')
    nd=rv.get('non_degradation')
    if not isinstance(nd,dict) or any(not isinstance(nd.get(k),list) for k in ('protect','retest','improve')):
        raise ComplianceError(f'{label}: non_degradation protect/retest/improve required')
    kpis=rv.get('kpis')
    if not isinstance(kpis,dict) or not kpis: raise ComplianceError(f'{label}: kpis required')
    for name,o in kpis.items():
        e=req(o,'eligibility',label+'/'+name)
        if e not in KPI_STATES: raise ComplianceError(f'{label}/{name}: invalid eligibility')
        if e=='ELIGIBLE' and o.get('evidence_state')!='PRE_RACE_ELIGIBLE': raise ComplianceError(f'{label}/{name}: eligible KPI lacks pre-race evidence')
        if mode=='REPLAY' and e=='ELIGIBLE': raise ComplianceError(f'{label}/{name}: replay KPI cannot be eligible')

def validate_gate(root,path):
    g=json.loads(path.read_text(encoding='utf-8')); label=str(path)
    if g.get('schema_version')!=SCHEMA: raise ComplianceError(f'{label}: schema mismatch')
    date=req(g,'race_date_jst',label); race_id=req(g,'race_id',label); mode=req(g,'mode',label)
    if mode not in {'FORWARD','REPLAY'}: raise ComplianceError(f'{label}: invalid mode')
    if g.get('working_branch')!=f'prediction/{date}': raise ComplianceError(f'{label}: wrong working_branch')
    rel=release(root)
    if rel!=SUPPORTED_RELEASE: raise ComplianceError(f'{label}: checker supports {SUPPORTED_RELEASE}, manual is {rel}')
    if g.get('manual_release')!=rel: raise ComplianceError(f'{label}: manual_release mismatch')
    if not re.fullmatch(r'[0-9a-f]{40}',req(g,'manual_ref_commit',label)): raise ComplianceError(f'{label}: full manual commit SHA required')
    post=iso(g.get('scheduled_post_time_jst'),label+'/post'); route=req(g,'timing_route',label)
    if mode=='REPLAY' and route!='LATE_PRESERVATION': raise ComplianceError(f'{label}: replay must be LATE_PRESERVATION')
    p=g.get('production')
    if not isinstance(p,dict): raise ComplianceError(f'{label}: production required')
    req(p,'baseline_forecast_id',label+'/production'); marks=p.get('marks')
    if not isinstance(marks,dict) or type(marks.get('honmei')) is not int: raise ComplianceError(f'{label}: production marks/honmei required')
    k=g.get('kpi_eligibility')
    if not isinstance(k,dict) or any(k.get(x) not in KPI_STATES for x in ('production','betting','shadow')): raise ComplianceError(f'{label}: KPI states invalid')
    if mode=='REPLAY' and k['shadow']=='ELIGIBLE': raise ComplianceError(f'{label}: replay shadow KPI cannot be eligible')
    if k['production']=='ELIGIBLE': evidence(root,p.get('evidence_ref'),label+'/production',True,post)
    if p.get('fixed_at_jst') and mode=='FORWARD' and k['production']=='ELIGIBLE' and iso(p['fixed_at_jst'],label+'/fixed')>=post:
        raise ComplianceError(f'{label}: post-time production cannot be eligible')
    items=g.get('shadow_items')
    if not isinstance(items,list): raise ComplianceError(f'{label}: shadow_items required')
    for i,x in enumerate(items):
        il=f'{label}/shadow[{i}]'; item=req(x,'item_id',il); state=req(x,'state',il)
        if item in KNOWN_CONFLICTS and state!='PENDING_RULE_CONFLICT': raise ComplianceError(f'{il}: unresolved rule conflict must remain pending')
        elig=x.get('kpi_eligibility','NOT_APPLICABLE')
        if elig not in KPI_STATES: raise ComplianceError(f'{il}: invalid KPI state')
        if mode=='REPLAY' and elig=='ELIGIBLE': raise ComplianceError(f'{il}: replay shadow cannot be eligible')
        if elig=='ELIGIBLE': evidence(root,x.get('evidence_ref'),il,True,post)
    betting(root,g.get('betting',{}),marks,label+'/betting',post,race_id)
    review(g.get('review',{'status':'NOT_STARTED'}),g,mode,label+'/review')
    return g

def blocks(path,tag):
    s=path.read_text(encoding='utf-8')
    for raw in re.findall(r'^\x60\x60\x60'+re.escape(tag)+r'\s*\n(.*?)\n\x60\x60\x60\s*$',s,re.M|re.S): yield json.loads(raw)

def cycle_links(root,gates):
    rd=root/'docs/validation/records'
    if not rd.exists(): return []
    missing=[]
    for path in rd.glob('*.md'):
        for d in blocks(path,'cycle03-day-v1'):
            date=d.get('race_date_jst')
            for race in d.get('initial_scope',[]):
                if (date,race) not in gates:
                    missing.append(f'{path}: missing execution gate for {race}')
                    continue
                g=gates[(date,race)]
                if race in d.get('reviewed_scope',[]) and g.get('review',{}).get('status')!='COMPLETE': raise ComplianceError(f'{path}: reviewed race lacks COMPLETE review gate')
                for name in ('production','betting','shadow'):
                    o=d.get('kpis',{}).get(name,{})
                    expected='ELIGIBLE' if race in o.get('eligible_ids',[]) else 'INELIGIBLE' if race in o.get('ineligible_ids',[]) else 'PENDING' if race in o.get('pending_ids',[]) else None
                    if expected and g['kpi_eligibility'][name]!=expected: raise ComplianceError(f'{path}: {race}/{name} gate state mismatch')
    return missing

def snapshot_links(root,gates):
    sd=root/'docs/validation/snapshots'
    if not sd.exists(): return []
    missing=[]
    for path in sd.glob('*.md'):
        content=path.read_text(encoding='utf-8')
        races=set(SNAPSHOT_RACE_ID_RE.findall(content))
        if 'snapshot_type: WHOLE_DAY' in content:
            for venue, number in WHOLE_DAY_RACE_RE.findall(content):
                races.add(f'{path.stem.replace("-", "")}-{"NAK" if venue=="中山" else "HAN"}-{int(number):02d}')
        for race in sorted(races):
            if (path.stem,race) not in gates:
                missing.append(f'{path}: snapshot race lacks execution gate: {race}')
        for claim in blocks(path,'execution-gate-ref-v1'):
            date=req(claim,'race_date_jst',str(path))
            race=req(claim,'race_id',str(path))
            if (date,race) not in gates:
                entry=f'{path}: snapshot race lacks execution gate: {race}'
                if entry not in missing: missing.append(entry)
    return missing

def run(root, audit=False):
    gd=root/'docs/validation/execution-gates'; gates={}; aliases={}
    for path in sorted(gd.glob('*/*.json')) if gd.exists() else []:
        g=validate_gate(root,path); key=(g['race_date_jst'],g['race_id'])
        if key in gates: raise ComplianceError(f'duplicate gate: {key}')
        gates[key]=g
        race_aliases=g.get('snapshot_race_ids',[])
        if not isinstance(race_aliases,list):
            raise ComplianceError(f'{path}: snapshot_race_ids must be a list')
        for alias in race_aliases:
            if not isinstance(alias,str) or not re.fullmatch(re.escape(g['race_date_jst'].replace('-',''))+r'-[A-Z]{3}-\d{2}',alias):
                raise ComplianceError(f'{path}: invalid snapshot race alias: {alias}')
            alias_key=(g['race_date_jst'],alias)
            if alias_key in aliases and aliases[alias_key]!=key:
                raise ComplianceError(f'{path}: duplicate snapshot race alias: {alias}')
            aliases[alias_key]=key
    for alias,key in aliases.items():
        if alias in gates and alias!=key:
            raise ComplianceError(f'snapshot race alias overlaps another gate: {alias}')
    snapshot_gate_keys={**gates,**{alias:gates[key] for alias,key in aliases.items()}}
    missing=snapshot_links(root,snapshot_gate_keys)+cycle_links(root,gates)
    if missing:
        if not audit: raise ComplianceError('\n'.join(missing))
        print(f'AUDIT_INCOMPLETE: {len(gates)} gate(s) validated; {len(missing)} missing links')
        for item in missing: print(item)
    else:
        print(f'COMPLIANT: {len(gates)} execution gate(s) validated; no missing links')
    return missing

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--root',type=Path,default=Path('.'))
    ap.add_argument('--audit',action='store_true',help='report missing coverage without blocking record persistence')
    a=ap.parse_args()
    try: run(a.root,audit=a.audit)
    except (ComplianceError,OSError,json.JSONDecodeError) as e:
        print(f'NON_COMPLIANT: {e}',file=sys.stderr); return 1
    return 0

if __name__=='__main__': raise SystemExit(main())
