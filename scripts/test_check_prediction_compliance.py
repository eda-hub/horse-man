import json, tempfile, unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))
from check_prediction_compliance import ComplianceError, coverage_summary, run

README='# manual\n- **現行リリース**: `v1.6.1`\n'

def write(root,rel,content):
    p=root/rel; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(content,encoding='utf-8'); return p

def receipt_record(receipt_id, artifact_id, artifact_path, timing='PRE_RACE_ELIGIBLE', verified='2026-09-26T10:00:00+09:00', post='2026-09-26T10:10:00+09:00'):
    return {
      'receipt_id':receipt_id,'artifact_id':artifact_id,'artifact_path':artifact_path,
      'timing_eligibility':timing,'artifact_persist_status':'PERSIST_VERIFIED',
      'receipt_persist_status':'RECEIPT_VERIFIED','persist_verified_at_jst':verified,
      'scheduled_post_time_jst':post
    }

def write_receipts(root, rel, records):
    fence='`'*3
    body='\n'.join(fence+'persistence-receipt-v1\n'+json.dumps(x,ensure_ascii=False)+'\n'+fence for x in records)
    return write(root,rel,body+'\n')

def add_vertical_evidence(root, ticket, probability_low=0.1, odds=15.0, scenario_id='s2', evidence_race_id='20260926-NAK-01'):
    evidence_id='BET-EVIDENCE-01'; artifact_rel='docs/validation/betting-evidence/2026-09-26/NAK-01.json'
    receipt_rel='docs/validation/persistence-receipts/2026-09-26.md'; receipt_id=evidence_id+'-R01'
    evidence={
      'schema_version':'betting-evidence-v1','evidence_id':evidence_id,'race_id':evidence_race_id,
      'prices':[{'type':ticket['type'],'horses':ticket['horses'],'odds':odds,'source_url':'https://example.invalid/odds','observed_at_jst':'2026-09-26T09:58:00+09:00'}],
      'probabilities':[{'type':ticket['type'],'horses':ticket['horses'],'scenario_id':scenario_id,'probability_low':probability_low,'method_ref':'prediction-v1','fixed_at_jst':'2026-09-26T09:57:00+09:00'}]
    }
    write(root,artifact_rel,json.dumps(evidence,ensure_ascii=False))
    write_receipts(root,receipt_rel,[receipt_record(receipt_id,evidence_id,artifact_rel)])
    ticket['vertical_exception']={
      'reason_code':'INDEPENDENT_POSITIVE_EV','scenario_id':scenario_id,
      'probability_low':probability_low,'odds':odds,'ev_low':probability_low*odds,
      'evidence_ref':{'artifact_path':artifact_rel,'artifact_id':evidence_id,'receipt_path':receipt_rel,'receipt_id':receipt_id,'timing_eligibility':'PRE_RACE_ELIGIBLE','persist_verified_at_jst':'2026-09-26T10:00:00+09:00'}
    }
    return ticket
def decisions(selected=('QUINELLA',)):
    out={}
    for kind in ('WIN','PLACE','QUINELLA','WIDE','EXACTA','TRIO','TRIFECTA'):
        out[kind]={'status':'SELECTED' if kind in selected else 'UNAVAILABLE','reason':'test'}
    return out

def gate(date='2026-09-26',race='20260926-NAK-01',mode='FORWARD'):
    return {
      'schema_version':'prediction-compliance-v1','race_id':race,'race_date_jst':date,'mode':mode,
      'working_branch':f'prediction/{date}','manual_release':'v1.6.1','manual_ref_commit':'a'*40,
      'scheduled_post_time_jst':f'{date}T10:10:00+09:00',
      'timing_route':'SNAPSHOT_CANDIDATE' if mode=='FORWARD' else 'LATE_PRESERVATION',
      'production':{'baseline_forecast_id':race+'-P001','marks':{'honmei':5,'taikou':2,'tanana':6},'fixed_at_jst':f'{date}T09:55:00+09:00'},
      'kpi_eligibility':{'production':'INELIGIBLE','betting':'INELIGIBLE','shadow':'INELIGIBLE'},
      'shadow_items':[{'item_id':'E-11','state':'PENDING_RULE_CONFLICT','kpi_eligibility':'PENDING'}],
      'betting':{'status':'NOT_REQUIRED'},'review':{'status':'NOT_STARTED'}
    }

def next_gate(date='2026-10-13',race='20261013-TOK-01',mode='FORWARD'):
    ranking=[5,2,6,4,1,3]
    probabilities=[
      {'horse_no':5,'win_probability':0.22,'top2_probability':0.39,'top3_probability':0.53},
      {'horse_no':2,'win_probability':0.18,'top2_probability':0.34,'top3_probability':0.49},
      {'horse_no':6,'win_probability':0.14,'top2_probability':0.29,'top3_probability':0.43},
    ]
    evidence_items=[
      {'horse_no':horse,'factor':'ability','fact':f'test fact {horse}','source_ref':'test-source',
       'observed_at_jst':f'{date}T09:40:00+09:00','direction':'plus','strength':'medium'}
      for horse in ranking[:3]
    ]
    return {
      'schema_version':'prediction-compliance-v2','race_id':race,'race_date_jst':date,'mode':mode,
      'working_branch':f'prediction/{date}','manual_release':'v1.7.0','manual_ref_commit':'b'*40,
      'scheduled_post_time_jst':f'{date}T10:10:00+09:00',
      'timing_route':'SNAPSHOT_CANDIDATE' if mode=='FORWARD' else 'LATE_PRESERVATION',
      'production':{
        'baseline_forecast_id':race+'-P001',
        'ranking':ranking,
        'marks':{'honmei':5,'taikou':2,'tanana':6,'renka':[4,1,3]},
        'probabilities':probabilities,
        'prediction_confidence':'B',
        'evidence_items':evidence_items,
        'fixed_at_jst':f'{date}T09:55:00+09:00'
      },
      'kpi_eligibility':{'production':'INELIGIBLE','shadow':'INELIGIBLE'},
      'shadow_items':[],
      'review':{'status':'NOT_STARTED'}
    }

class T(unittest.TestCase):
  def root(self):
    t=tempfile.TemporaryDirectory(); self.addCleanup(t.cleanup); r=Path(t.name); write(r,'docs/manual/README.md',README); return r
  def root_next(self):
    t=tempfile.TemporaryDirectory(); self.addCleanup(t.cleanup); r=Path(t.name)
    write(r,'docs/manual/README.md','# manual\n- **現行リリース**: `v1.7.0`\n')
    return r
  def put(self,r,g):
    write(r,f"docs/validation/execution-gates/{g['race_date_jst']}/{g['race_id']}.json",json.dumps(g,ensure_ascii=False))
  def test_replay_shadow_eligible_rejected(self):
    r=self.root(); g=gate(mode='REPLAY'); g['kpi_eligibility']['shadow']='ELIGIBLE'; self.put(r,g)
    with self.assertRaisesRegex(ComplianceError,'replay shadow KPI cannot be eligible'): run(r)
  def test_e11_conflict_cannot_be_guessed(self):
    r=self.root(); g=gate(); g['shadow_items'][0]['state']='NOT_APPLICABLE'; self.put(r,g)
    with self.assertRaisesRegex(ComplianceError,'unresolved rule conflict'): run(r)
  def test_non_anchor_pair_requires_exception(self):
    r=self.root(); g=gate(); g['betting']={'status':'FIXED','audit_status':'PASS','budget_kind':'VALIDATION_FIXED','total_stake_yen':10000,'ticket_type_decisions':decisions(),
      'natural_candidates':[{'type':'QUINELLA','horses':[5,2]},{'type':'QUINELLA','horses':[2,6]}], 'rejected_candidates':[],
      'tickets':[{'type':'QUINELLA','horses':[5,2],'amount_yen':7000},{'type':'QUINELLA','horses':[2,6],'amount_yen':3000}]}; self.put(r,g)
    with self.assertRaisesRegex(ComplianceError,'requires vertical_exception'): run(r)
  def test_dependency_reduction_rejected(self):
    r=self.root(); g=gate(); g['betting']={'status':'FIXED','audit_status':'PASS','budget_kind':'VALIDATION_FIXED','total_stake_yen':10000,'ticket_type_decisions':decisions(),
      'natural_candidates':[{'type':'QUINELLA','horses':[5,2]},{'type':'QUINELLA','horses':[2,6]}], 'rejected_candidates':[],
      'tickets':[{'type':'QUINELLA','horses':[5,2],'amount_yen':7000},{'type':'QUINELLA','horses':[2,6],'amount_yen':3000,'vertical_exception':{'reason_code':'DEPENDENCY_REDUCTION','scenario_id':'s2','probability_low':0.1,'odds':15.0,'ev_low':1.5}}]}; self.put(r,g)
    with self.assertRaisesRegex(ComplianceError,'reason_code not allowed'): run(r)
  def test_valid_vertical_exception_passes(self):
    r=self.root(); g=gate()
    vertical=add_vertical_evidence(r,{'type':'QUINELLA','horses':[2,6],'amount_yen':3000})
    g['betting']={'status':'FIXED','audit_status':'PASS','budget_kind':'VALIDATION_FIXED','total_stake_yen':10000,'ticket_type_decisions':decisions(),
      'natural_candidates':[{'type':'QUINELLA','horses':[5,2]},{'type':'QUINELLA','horses':[2,6]}], 'rejected_candidates':[],
      'tickets':[{'type':'QUINELLA','horses':[5,2],'amount_yen':7000},vertical]}; self.put(r,g); run(r)

  def test_unlisted_vertical_reason_rejected(self):
    r=self.root(); g=gate()
    g['betting']={'status':'FIXED','audit_status':'PASS','budget_kind':'VALIDATION_FIXED','total_stake_yen':10000,'ticket_type_decisions':decisions(),
      'natural_candidates':[{'type':'QUINELLA','horses':[5,2]},{'type':'QUINELLA','horses':[2,6]}], 'rejected_candidates':[],
      'tickets':[{'type':'QUINELLA','horses':[5,2],'amount_yen':7000},{'type':'QUINELLA','horses':[2,6],'amount_yen':3000,'vertical_exception':{'reason_code':'OTHER_REASON','scenario_id':'s2','probability_low':0.1,'odds':15.0,'ev_low':1.5}}]}
    self.put(r,g)
    with self.assertRaisesRegex(ComplianceError,'reason_code not allowed'): run(r)

  def test_vertical_price_must_match_pre_race_evidence(self):
    r=self.root(); g=gate()
    vertical=add_vertical_evidence(r,{'type':'QUINELLA','horses':[2,6],'amount_yen':3000},odds=15.0)
    vertical['vertical_exception']['odds']=16.0; vertical['vertical_exception']['ev_low']=1.6
    g['betting']={'status':'FIXED','audit_status':'PASS','budget_kind':'VALIDATION_FIXED','total_stake_yen':10000,'ticket_type_decisions':decisions(),
      'natural_candidates':[{'type':'QUINELLA','horses':[5,2]},{'type':'QUINELLA','horses':[2,6]}], 'rejected_candidates':[],
      'tickets':[{'type':'QUINELLA','horses':[5,2],'amount_yen':7000},vertical]}
    self.put(r,g)
    with self.assertRaisesRegex(ComplianceError,'odds do not match pre-race evidence'): run(r)

  def test_vertical_probability_must_match_pre_race_evidence(self):
    r=self.root(); g=gate()
    vertical=add_vertical_evidence(r,{'type':'QUINELLA','horses':[2,6],'amount_yen':3000},probability_low=0.1)
    vertical['vertical_exception']['probability_low']=0.11; vertical['vertical_exception']['ev_low']=1.65
    g['betting']={'status':'FIXED','audit_status':'PASS','budget_kind':'VALIDATION_FIXED','total_stake_yen':10000,'ticket_type_decisions':decisions(),
      'natural_candidates':[{'type':'QUINELLA','horses':[5,2]},{'type':'QUINELLA','horses':[2,6]}], 'rejected_candidates':[],
      'tickets':[{'type':'QUINELLA','horses':[5,2],'amount_yen':7000},vertical]}
    self.put(r,g)
    with self.assertRaisesRegex(ComplianceError,'probability_low does not match pre-race evidence'): run(r)

  def test_vertical_evidence_race_id_must_match_gate(self):
    r=self.root(); g=gate()
    vertical=add_vertical_evidence(r,{'type':'QUINELLA','horses':[2,6],'amount_yen':3000},evidence_race_id='20260926-NAK-02')
    g['betting']={'status':'FIXED','audit_status':'PASS','budget_kind':'VALIDATION_FIXED','total_stake_yen':10000,'ticket_type_decisions':decisions(),
      'natural_candidates':[{'type':'QUINELLA','horses':[5,2]},{'type':'QUINELLA','horses':[2,6]}], 'rejected_candidates':[],
      'tickets':[{'type':'QUINELLA','horses':[5,2],'amount_yen':7000},vertical]}
    self.put(r,g)
    with self.assertRaisesRegex(ComplianceError,'betting evidence race_id mismatch'): run(r)
  def test_receipt_status_must_be_same_record(self):
    r=self.root(); g=gate(); g['kpi_eligibility']['production']='ELIGIBLE'
    artifact_rel='docs/validation/snapshots/2026-09-26.md'; artifact_id='20260926-NAK-01-P001-S01'
    receipt_rel='docs/validation/persistence-receipts/2026-09-26.md'; rid=artifact_id+'-R01'
    write(r,artifact_rel,'artifact '+artifact_id)
    bad=receipt_record(rid,artifact_id,artifact_rel,timing='READBACK_PENDING')
    good=receipt_record(artifact_id+'-R02',artifact_id,artifact_rel,timing='PRE_RACE_ELIGIBLE')
    write_receipts(r,receipt_rel,[bad,good])
    g['production']['evidence_ref']={'artifact_path':artifact_rel,'artifact_id':artifact_id,'receipt_path':receipt_rel,'receipt_id':rid,'timing_eligibility':'PRE_RACE_ELIGIBLE','persist_verified_at_jst':'2026-09-26T10:00:00+09:00'}
    self.put(r,g)
    with self.assertRaisesRegex(ComplianceError,'receipt timing_eligibility mismatch'): run(r)
  def test_receipt_verified_after_post_rejected(self):
    r=self.root(); g=gate(); g['kpi_eligibility']['production']='ELIGIBLE'
    artifact_rel='docs/validation/snapshots/2026-09-26.md'; artifact_id='20260926-NAK-01-P001-S01'
    receipt_rel='docs/validation/persistence-receipts/2026-09-26.md'; rid=artifact_id+'-R01'
    write(r,artifact_rel,'artifact '+artifact_id)
    late=receipt_record(rid,artifact_id,artifact_rel,verified='2026-09-26T10:11:00+09:00')
    write_receipts(r,receipt_rel,[late])
    g['production']['evidence_ref']={'artifact_path':artifact_rel,'artifact_id':artifact_id,'receipt_path':receipt_rel,'receipt_id':rid,'timing_eligibility':'PRE_RACE_ELIGIBLE','persist_verified_at_jst':'2026-09-26T10:11:00+09:00'}
    self.put(r,g)
    with self.assertRaisesRegex(ComplianceError,'verified at/after post time'): run(r)

  def test_original_plain_markdown_receipt_is_checked(self):
    r=self.root(); g=gate()
    g['kpi_eligibility']['production']='ELIGIBLE'
    artifact='docs/validation/snapshots/2026-09-26.md'; aid='20260926-NAK-01-P001-S01'
    receipt='docs/validation/persistence-receipts/2026-09-26.md'; rid=aid+'-R02'
    write(r,artifact,'snapshot_id: '+aid+'\n')
    record=receipt_record(rid,aid,artifact)
    write(r,receipt,'## persistence_receipt\n\n'+'\n'.join(f'{k}: {v}' for k,v in record.items())+'\n')
    g['production']['evidence_ref']={'artifact_path':artifact,'artifact_id':aid,
        'receipt_path':receipt,'receipt_id':rid,'timing_eligibility':'PRE_RACE_ELIGIBLE',
        'persist_verified_at_jst':'2026-09-26T10:00:00+09:00'}
    self.put(r,g); run(r)

  def test_conflicting_plain_and_structured_receipt_rejected(self):
    r=self.root(); rid='receipt-1'
    good=receipt_record(rid,'artifact-1','snapshot.md')
    bad=dict(good,artifact_id='artifact-2')
    p=write_receipts(r,'receipts.md',[good])
    p.write_text('## persistence_receipt\n\n'+'\n'.join(f'{k}: {v}' for k,v in bad.items())+'\n\n'+p.read_text(),encoding='utf-8')
    from check_prediction_compliance import receipt_records
    with self.assertRaisesRegex(ComplianceError,'structured/plain receipt'): receipt_records(p)
  def test_user_budget_requires_separate_validation_plan(self):
    r=self.root(); g=gate()
    g['betting']={
      'status':'FIXED','audit_status':'PASS','budget_kind':'USER_BUDGET','total_stake_yen':5000,'ticket_type_decisions':decisions(),
      'natural_candidates':[{'type':'QUINELLA','horses':[5,2]}],
      'rejected_candidates':[],
      'tickets':[{'type':'QUINELLA','horses':[5,2],'amount_yen':5000}]
    }
    self.put(r,g)
    with self.assertRaisesRegex(ComplianceError,'requires separate validation_stake_plan'): run(r)

  def test_missing_ticket_type_decisions_rejected(self):
    r=self.root(); g=gate()
    g['betting']={'status':'FIXED','audit_status':'PASS','budget_kind':'VALIDATION_FIXED','total_stake_yen':10000,
      'natural_candidates':[{'type':'QUINELLA','horses':[5,2]}],'rejected_candidates':[],
      'tickets':[{'type':'QUINELLA','horses':[5,2],'amount_yen':10000}]}
    self.put(r,g)
    with self.assertRaisesRegex(ComplianceError,'ticket_type_decisions'): run(r)

  def test_review_timestamp_required(self):
    r=self.root(); g=gate(); g['review']={'status':'COMPLETE','result_sources':[{'url':'https://example.invalid'}], 'kpis':{'production':{'eligibility':'INELIGIBLE','evidence_state':'DETAIL_UNAVAILABLE'}},'counterfactual_check':'UNDETERMINED','non_degradation':{'protect':[],'retest':[],'improve':[]}}; self.put(r,g)
    with self.assertRaisesRegex(ComplianceError,'timestamp required'): run(r)
  def test_eligible_production_requires_verified_receipt(self):
    r=self.root(); g=gate(); g['kpi_eligibility']['production']='ELIGIBLE'; self.put(r,g)
    with self.assertRaisesRegex(ComplianceError,'evidence_ref required'): run(r)

  def test_missing_baseline_cannot_be_declared_eligible(self):
    r=self.root(); g=gate(); g['kpi_eligibility']['production']='ELIGIBLE'
    g['production']['baseline_forecast_id']='MISSING_IN_INITIAL_SNAPSHOT'
    self.put(r,g)
    with self.assertRaisesRegex(ComplianceError,'lacks a fixed baseline_forecast_id'): run(r)

  def test_complete_review_requires_error_classification(self):
    r=self.root(); g=gate()
    g['review']={
      'status':'COMPLETE',
      'result_sources':[{'url':'https://example.invalid','retrieved_at_jst':'2026-09-26T11:00:00+09:00'}],
      'result':{'top3':[1,2,3]},
      'kpis':{'production':{'eligibility':'INELIGIBLE','evidence_state':'DETAIL_UNAVAILABLE'}},
      'counterfactual_check':'UNDETERMINED',
      'layer_assessment':{'prediction':'UNDETERMINED','price':'UNDETERMINED','betting':'UNDETERMINED'},
      'non_degradation':{'protect':[],'retest':[],'improve':[]}
    }
    self.put(r,g)
    with self.assertRaisesRegex(ComplianceError,'error_classification required'): run(r)

  def test_replay_review_kpi_cannot_be_eligible(self):
    r=self.root(); g=gate(mode='REPLAY')
    g['review']={
      'status':'COMPLETE',
      'result_sources':[{'url':'https://example.invalid','retrieved_at_jst':'2026-09-26T11:00:00+09:00'}],
      'result':{'top3':[1,2,3]},
      'error_classification':{'primary':'UNDETERMINED','secondary':[]},
      'kpis':{'production':{'eligibility':'ELIGIBLE','evidence_state':'PRE_RACE_ELIGIBLE'}},
      'counterfactual_check':'UNDETERMINED',
      'layer_assessment':{'prediction':'UNDETERMINED','price':'UNDETERMINED','betting':'UNDETERMINED'},
      'non_degradation':{'protect':[],'retest':[],'improve':[]}
    }
    self.put(r,g)
    with self.assertRaisesRegex(ComplianceError,'replay KPI cannot be eligible'): run(r)

  def test_explicit_snapshot_gate_claim_requires_gate(self):
    r=self.root()
    claim={'race_date_jst':'2026-09-26','race_id':'20260926-NAK-01'}
    write(r,'docs/validation/snapshots/2026-09-26.md',chr(96)*3+'execution-gate-ref-v1\n'+json.dumps(claim)+'\n'+chr(96)*3+'\n')
    with self.assertRaisesRegex(ComplianceError,'snapshot race lacks execution gate'): run(r)

  def test_snapshot_id_is_preserved_without_gate_certification(self):
    r=self.root()
    write(r,'docs/validation/snapshots/2026-09-27.md','snapshot_id: 20260927-NAK-11-P001-S01\n')
    self.assertEqual(run(r),[])

  def test_whole_day_table_is_audited_without_gate_fabrication(self):
    r=self.root()
    write(r,'docs/validation/snapshots/2026-09-27.md',
          'snapshot_type: WHOLE_DAY\n| race | status |\n|---|---|\n| 中山1R | 見送り |\n| 阪神12R | 購入候補 |\n')
    self.assertEqual(run(r),[])

  def test_canonical_race_gate_resolves_snapshot_alias(self):
    r=self.root()
    g=gate(race='202606040811')
    g['snapshot_race_ids']=['20260926-NAK-11']
    self.put(r,g)
    write(r,'docs/validation/snapshots/2026-09-26.md',
          'snapshot_id: 20260926-NAK-11-UNRESOLVED-S01\n')
    run(r)

  def test_ineligible_or_pending_scope_does_not_require_dummy_gate(self):
    r=self.root()
    day={'race_date_jst':'2026-09-27','initial_scope':['race-a']}
    write(r,'docs/validation/records/2026-09-27.md',chr(96)*3+'cycle03-day-v1\n'+json.dumps(day)+'\n'+chr(96)*3+'\n')
    self.assertEqual(run(r),[])

  def test_eligible_claim_requires_gate_on_any_date(self):
    r=self.root()
    day={'race_date_jst':'2026-09-26','initial_scope':['race-a'],
         'kpis':{'production':{'eligible_ids':['race-a']}}}
    body=chr(96)*3+'cycle03-day-v1\n'+json.dumps(day)+'\n'+chr(96)*3+'\n'
    write(r,'docs/validation/records/2026-09-26.md',body)
    with self.assertRaisesRegex(ComplianceError,'ELIGIBLE production lacks execution gate'): run(r)
    self.assertEqual(len(run(r,audit=True)),1)

  def test_coverage_summary_follows_dates_in_files(self):
    r=self.root()
    g=gate(race='20261004-NAK-01',date='2026-10-04'); self.put(r,g)
    write(r,'docs/validation/snapshots/2026-10-04.md',
          'snapshot_id: 20261004-NAK-02-P001-S01\n')
    missing=run(r,audit=True)
    self.assertEqual(missing,[])
    from check_prediction_compliance import snapshot_links
    _,unregistered=snapshot_links(r,{(g['race_date_jst'],g['race_id']):g})
    self.assertEqual(coverage_summary({(g['race_date_jst'],g['race_id']):g},missing,unregistered),
                     {'2026-10-04':{'gates':1,'missing_links':0,'ungated_snapshots':1}})

  def test_legacy_gate_remains_valid_after_manual_release_advances(self):
    r=self.root_next(); g=gate(); self.put(r,g); run(r)

  def test_legacy_schema_rejected_for_next_effective_date(self):
    r=self.root_next(); g=gate(date='2026-10-13',race='20261013-TOK-01'); self.put(r,g)
    with self.assertRaisesRegex(ComplianceError,'legacy contract is not valid'): run(r)

  def test_next_schema_rejected_before_effective_date(self):
    r=self.root(); g=next_gate(date='2026-10-12',race='20261012-TOK-01'); self.put(r,g)
    with self.assertRaisesRegex(ComplianceError,'next contract is not valid before'): run(r)

  def test_next_gate_does_not_require_betting(self):
    r=self.root_next(); g=next_gate(); self.put(r,g); run(r)

  def test_next_gate_ignores_optional_legacy_betting_kpi(self):
    r=self.root_next(); g=next_gate()
    g['kpi_eligibility']['betting']='ELIGIBLE'
    g['betting']={'status':'FIXED'}
    self.put(r,g); run(r)

  def test_next_gate_requires_top3_evidence(self):
    r=self.root_next(); g=next_gate()
    g['production']['evidence_items']=g['production']['evidence_items'][:2]
    self.put(r,g)
    with self.assertRaisesRegex(ComplianceError,'top3 ranking horses require evidence'): run(r)

  def test_next_gate_marks_must_follow_ranking(self):
    r=self.root_next(); g=next_gate()
    g['production']['marks']['honmei']=2
    self.put(r,g)
    with self.assertRaisesRegex(ComplianceError,'marks must follow production ranking'): run(r)

  def test_next_gate_probability_order_is_validated(self):
    r=self.root_next(); g=next_gate()
    g['production']['probabilities'][0]['win_probability']=0.6
    self.put(r,g)
    with self.assertRaisesRegex(ComplianceError,'probability order'): run(r)

  def test_next_gate_evidence_must_be_pre_race(self):
    r=self.root_next(); g=next_gate()
    g['production']['evidence_items'][0]['observed_at_jst']='2026-10-13T10:11:00+09:00'
    self.put(r,g)
    with self.assertRaisesRegex(ComplianceError,'evidence observed at/after post time'): run(r)

  def test_next_replay_cannot_claim_production_eligible(self):
    r=self.root_next(); g=next_gate(mode='REPLAY')
    g['kpi_eligibility']['production']='ELIGIBLE'
    self.put(r,g)
    with self.assertRaisesRegex(ComplianceError,'replay production/shadow KPI cannot be eligible'): run(r)

  def test_unknown_contract_is_rejected(self):
    r=self.root_next(); g=next_gate(); g['manual_release']='v9.9.9'; self.put(r,g)
    with self.assertRaisesRegex(ComplianceError,'unsupported manual_release/schema combination'): run(r)

  def test_next_eligible_production_requires_verified_receipt(self):
    r=self.root_next(); g=next_gate(); g['kpi_eligibility']['production']='ELIGIBLE'; self.put(r,g)
    with self.assertRaisesRegex(ComplianceError,'evidence_ref required'): run(r)

  def test_next_complete_review_needs_prediction_layer_not_betting(self):
    r=self.root_next(); g=next_gate()
    g['review']={
      'status':'COMPLETE',
      'result_sources':[{'url':'https://example.invalid','retrieved_at_jst':'2026-10-13T11:00:00+09:00'}],
      'result':{'top3':[5,2,6]},
      'error_classification':{'primary':'NONE','secondary':[]},
      'layer_assessment':{'prediction':'PASS'},
      'non_degradation':{'protect':[],'retest':[],'improve':[]},
      'kpis':{'production':{'eligibility':'INELIGIBLE'}}
    }
    self.put(r,g); run(r)

if __name__=='__main__': unittest.main()
