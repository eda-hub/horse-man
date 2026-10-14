"""第3の運用欠陥を再現する合成受入。実レース・前向き性能は認証しない。"""
import copy
import json
import tempfile
import unittest
from unittest.mock import patch
from datetime import datetime
from pathlib import Path

from check_prediction_compliance import ComplianceError, contract_state
from check_cycle04 import (SCHEMA, DATES, validate_day, check_preparation, require_active)
from cycle04_operations import (BET_TYPES, fingerprint, validate_inputs, validate_market,
                               validate_selection, validate_ticket_comparison, ticket_event)
from seal_prediction import seal
from selection_history import digest
from test_next_prediction_compliance import receipt_record, write, write_contract_state
import test_recommendation as fixtures
from test_recommendation import DATE, RACE, POST


class Cycle04Acceptance(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def artifact(self, ident, path, payload, at='09:40', readback=None):
        raw = json.dumps(payload, ensure_ascii=False, indent=2) + '\n'
        write(self.root, path, raw)
        rp = f'docs/validation/persistence-receipts/{DATE}.md'
        r = receipt_record(ident + '-receipt', ident, path, verified=DATE + 'T' + at + ':00+09:00', post=POST)
        r['receipt_verified_at_jst'] = DATE + 'T' + (readback or at) + ':00+09:00'
        r['content_sha256'] = fingerprint(raw.encode())
        prior = (self.root / rp).read_text() if (self.root / rp).exists() else ''
        write(self.root, rp, prior + '\n```persistence-receipt-v1\n' + json.dumps(r) + '\n```\n')
        return {'artifact_id': ident, 'artifact_path': path, 'path': path,
                'receipt_path': rp, 'receipt_id': r['receipt_id'], 'sha256': r['content_sha256']}

    def input(self, horses=(5, 2, 6, 4), cutoff=None):
        c = cutoff or DATE + 'T09:50:00+09:00'
        data = {'schema_version': 'race-input-coverage-v1', 'race_id': RACE,
                'data_cutoff': c, 'horse_numbers': list(horses)}
        for field in ('body_weight', 'recent_five_runs'):
            data[field] = [{'horse_no': h, 'status': 'MISSING', 'reason': '公式取得未完了', 'value': None}
                           for h in horses]
        return data

    def inputs(self, data):
        return validate_inputs(data, race_id=RACE, horses=data['horse_numbers'],
                               cutoff=data['data_cutoff'], post=POST)

    def market(self):
        return {'status': 'NOT_ATTEMPTED', 'decision': 'NOT_EVALUATED', 'reason': '任意市場は依頼なし',
                'odds': None, 'expected_value': None, 'attempted_at_jst': None}

    def history(self):
        h = {'schema_version': 'selection-history-v1', 'scheduled_posts': {RACE: POST}, 'events': []}
        for action in ('SELECT', 'BUY'):
            core = {'revision': len(h['events']) + 1, 'previous_sha256':
                    digest({k: v for k, v in h['events'][-1].items() if k != 'evidence'}) if h['events'] else None,
                    'race_id': RACE, 'purpose': 'RECOMMENDATION', 'action': action,
                    'at': DATE + 'T09:42:00+09:00', 'reason': '価格不要の最終推奨対象'}
            if action == 'BUY':
                core.update(selection_revision=1, plan_id='r1', tickets=[{'type': 'WIDE', 'horses': [5, 2]}])
            ref = self.artifact('event-' + action, f'events/{action}.json', core, at='09:43')
            h['events'].append({**core, 'evidence': ref})
        return h

    def comparison(self):
        return [{'type': kind, 'status': 'MISSING', 'reason': '同時率未校正', 'tickets': []}
                for kind in BET_TYPES]

    def complete_day(self):
        f = fixtures.RecommendationTest()
        # 合成ACTIVE環境だけで正常系を確認。リポジトリの未定版を切り替えない。
        f.addCleanup = self.addCleanup
        root, gate, pred = f.root()
        self.root = root
        for horse, win, top2, top3 in [(4,.18,.36,.56),(1,.16,.34,.52),(3,.12,.28,.47)]:
            gate['production']['probabilities'].append({'horse_no':horse,'win_probability':win,
                                                       'top2_probability':top2,'top3_probability':top3})
            fact = copy.deepcopy(gate['production']['evidence_items'][0]);fact['horse_no']=horse
            gate['production']['evidence_items'].append(fact)
        from test_next_prediction_compliance import add_next_production_snapshot
        pred = add_next_production_snapshot(root, gate)
        write(root, f'docs/validation/execution-gates/{DATE}/{RACE}.json', json.dumps(gate))
        rec_path, _ = f.artifacts(root, gate, pred)
        ref = gate['production']['evidence_ref']
        raw = (root / ref['artifact_path']).read_bytes()
        from check_prediction_compliance import receipt_records
        receipts = receipt_records(root / ref['receipt_path'])
        r = [r for r in receipts if r['receipt_id'] == ref['receipt_id']][0]
        r['content_sha256'] = fingerprint(raw)
        r['receipt_verified_at_jst'] = r['persist_verified_at_jst']
        from test_next_prediction_compliance import write_receipts
        write_receipts(root, ref['receipt_path'], receipts)
        # 元fixtureの本体receiptはhashを持つ。FIX前独立証跡を追加する。
        p_ref = {**ref, 'sha256': fingerprint(raw)}
        intent_path = f'docs/validation/persistence-intents/{DATE}/first.json'
        intent = json.loads((root / intent_path).read_text())
        i_ref = self.artifact('intent-final', intent_path, intent, at='09:39')
        manifest = {'schema_version': 'prediction-fix-manifest-v1', 'snapshot_id': pred['snapshot_id'],
                    'artifact_path': ref['artifact_path'], 'fixed_content_sha256': fingerprint(raw),
                    'fixed_at_jst': pred['fixed_at_jst'], 'intent_ref': i_ref}
        fix_ref = self.artifact('fix', f'docs/validation/fix-manifests/{DATE}/p.json', manifest, at='09:56')
        data = self.input(tuple(x['horse_no'] for x in pred['probabilities']), gate['data_cutoff'])
        input_ref = self.artifact('inputs', 'inputs.json', data)
        history_ref = self.artifact('history', 'history.json', self.history(), at='09:44')
        operation = {'prediction_ref': p_ref, 'intent_ref': i_ref, 'fix_ref': fix_ref,
                     'inputs_ref': input_ref, 'selection_ref': history_ref,
                     'horse_numbers': data['horse_numbers'], 'frames': {},
                     'ticket_comparison': self.comparison()}
        d = {'schema_version': SCHEMA, 'cycle_id': 'cycle_04', 'race_date_jst': DATE,
             'initial_scope': [RACE], 'selected_scope': [RACE], 'final_scope': [RACE],
             'reviewed_scope': [], 'unfinished_reasons': {}, 'kpis': {},
             'races': {RACE: {'mode': 'FORWARD', 'prediction_gate_path':
                        f'docs/validation/execution-gates/{DATE}/{RACE}.json',
                        'scheduled_post_time_jst': POST,
                        'recommendation_gate_path': rec_path, 'operations': operation,
                        'input_complete': False, 'input_gap_reason': '全頭馬体重/近走未取得',
                        'uncertainty_effect': '状態評価は未判定として明示', 'market': self.market()}}}
        for name in ('production', 'recommendation', 'shadow', 'market', 'actual_purchase'):
            eligible = [RACE] if name in ('production', 'recommendation') else []
            d['kpis'][name] = {'target_ids': eligible, 'eligible_ids': eligible,
                                'ineligible_ids': [], 'pending_ids': [],
                                'reasons': {RACE: '独立証跡照合'} if eligible else {}}
        contract = {'status': 'ACTIVE', 'next_release': 'v1.7.0', 'effective_race_date': '2026-10-13'}
        return d, contract

    def day(self, d, c):
        p = self.root / f'{DATE}.json'
        p.write_text(json.dumps(d))
        return validate_day(self.root, p, c)

    def test_end_to_end_prediction_recommendation_input_gap_no_price(self):
        d, c = self.complete_day()
        self.assertEqual(self.day(d, c), d)

    def test_fix_manifest_must_reference_the_same_intent_and_fixed_time(self):
        for field, value in [('intent_ref', {}), ('fixed_at_jst', DATE+'T09:54:00+09:00')]:
            d, c = self.complete_day()
            op = d['races'][RACE]['operations']
            manifest = json.loads((self.root/op['fix_ref']['artifact_path']).read_text())
            manifest[field] = value
            op['fix_ref'] = self.artifact('changed-fix', f'docs/validation/fix-manifests/{DATE}/changed.json',
                                          manifest, at='09:56')
            with self.subTest(field=field), self.assertRaisesRegex(ComplianceError, 'FIX manifest mismatch'):
                self.day(d, c)

    def test_intent_path_and_deadline_must_match_the_fixed_prediction(self):
        for field, value in [('artifact_path', f'docs/validation/snapshots/{DATE}/another.json'),
                             ('deadline_jst', DATE+'T10:11:00+09:00')]:
            d, c = self.complete_day(); op = d['races'][RACE]['operations']
            intent = json.loads((self.root/op['intent_ref']['artifact_path']).read_text())
            intent[field] = value
            op['intent_ref'] = self.artifact('changed-intent', f'intents/{field}.json', intent, at='09:39')
            manifest = json.loads((self.root/op['fix_ref']['artifact_path']).read_text())
            manifest['intent_ref'] = op['intent_ref']
            op['fix_ref'] = self.artifact('new-fix', f'docs/validation/fix-manifests/{DATE}/new.json', manifest, at='09:56')
            with self.subTest(field=field), self.assertRaisesRegex(ComplianceError, 'predeclaration scope/path/deadline'):
                self.day(d, c)

    def test_row_scheduled_post_cannot_differ_from_gate_or_race_day(self):
        for value in (DATE+'T10:11:00+09:00', '2026-10-18T10:10:00+09:00'):
            d, c = self.complete_day(); d['races'][RACE]['scheduled_post_time_jst'] = value
            with self.subTest(value=value), self.assertRaisesRegex(ComplianceError, 'scheduled post'):
                self.day(d, c)

    def test_opponent_level_requires_information_available_by_cutoff(self):
        d = self.input()
        row = d['recent_five_runs'][0]
        row.update(status='ACQUIRED', prior_start_count=1, provider='OFFICIAL', source_ref='official',
                   observed_at_jst=DATE+'T09:00:00+09:00', acquired_at_jst=DATE+'T09:10:00+09:00',
                   readback_at_jst=DATE+'T09:12:00+09:00', value=[{
                       'race_at_jst': '2026-09-20T15:00:00+09:00', 'source_ref': 'official', 'class': '3歳限定',
                       'opponent_level': {'status': 'ACQUIRED', 'value': '古馬OP相当', 'source_ref': 'official',
                                          'observed_at_jst': DATE+'T11:00:00+09:00'}}])
        with self.assertRaisesRegex(ComplianceError, 'opponent level uses future'):
            self.inputs(d)
        opponent = row['value'][0]['opponent_level']
        opponent['observed_at_jst'] = DATE+'T09:00:00+09:00'
        self.inputs(d)
        opponent.pop('observed_at_jst')
        with self.assertRaises(ComplianceError): self.inputs(d)

    def test_acquired_runs_with_missing_opponent_level_are_not_complete(self):
        d = self.input()
        for field in ('body_weight', 'recent_five_runs'):
            for row in d[field]:
                row.update(status='ACQUIRED', provider='OFFICIAL', source_ref='official',
                           observed_at_jst=DATE+'T09:00:00+09:00', acquired_at_jst=DATE+'T09:10:00+09:00',
                           readback_at_jst=DATE+'T09:12:00+09:00')
                if field == 'body_weight': row['value'] = 480
                else:
                    row['prior_start_count'] = 1
                    row['value'] = [{'race_at_jst': '2026-09-20T15:00:00+09:00', 'source_ref': 'official',
                                     'class': '混合1勝', 'opponent_level': {'status': 'MISSING', 'value': None,
                                                                          'reason': '相手格未評価'}}]
        result = self.inputs(d)
        self.assertEqual(result['opponent_level_missing_horses'], sorted(d['horse_numbers']))
        self.assertFalse(result['complete'])

    def test_missing_inputs_remain_unknown_not_zero(self):
        result = self.inputs(self.input())
        self.assertFalse(result['complete'])
        self.assertEqual(result['body_weight']['acquired_count'], 0)

    def test_weight_zero_and_missing_value_are_rejected(self):
        for value in (0, 480):
            d = self.input(); d['body_weight'][0]['value'] = value
            with self.assertRaises(ComplianceError): self.inputs(d)

    def test_all_horse_scope_and_duplicate_detection(self):
        for field in ('body_weight', 'recent_five_runs'):
            d = self.input(); d[field][-1] = d[field][0]
            with self.assertRaises(ComplianceError): self.inputs(d)

    def acquired_weight(self):
        d = self.input()
        d['body_weight'][0].update(status='ACQUIRED', value=480, provider='OFFICIAL', source_ref='official',
                                   observed_at_jst=DATE+'T09:40:00+09:00', acquired_at_jst=DATE+'T09:42:00+09:00',
                                   readback_at_jst=DATE+'T09:43:00+09:00')
        return d

    def test_future_or_reversed_input_is_rejected(self):
        for key in ('observed_at_jst', 'acquired_at_jst', 'readback_at_jst'):
            d = self.acquired_weight(); d['body_weight'][0][key] = DATE+'T10:20:00+09:00'
            with self.assertRaises(ComplianceError): self.inputs(d)

    def test_fallback_requires_failed_official_attempt(self):
        d = self.acquired_weight(); d['body_weight'][0]['provider'] = 'FALLBACK'
        with self.assertRaises(ComplianceError): self.inputs(d)
        d['body_weight'][0]['official_attempt_reason'] = '公式取得タイムアウト'
        self.assertEqual(self.inputs(d)['body_weight']['acquired_count'], 1)

    def test_debut_and_less_than_five_runs(self):
        d = self.input()
        d['recent_five_runs'][0].update(status='NOT_APPLICABLE', prior_start_count=0, source_ref='official')
        self.inputs(d)
        d['recent_five_runs'][1].update(status='ACQUIRED', prior_start_count=2, provider='OFFICIAL', source_ref='official',
                observed_at_jst=DATE+'T09:00:00+09:00', acquired_at_jst=DATE+'T09:10:00+09:00',
                readback_at_jst=DATE+'T09:12:00+09:00', value=[
                    {'race_at_jst': date+'T15:00:00+09:00', 'source_ref': 'official',
                     'class': '3歳限定', 'opponent_level': {'status': 'MISSING', 'value': None,
                                                           'reason': '未評価を明示'}}
                    for date in ('2026-09-20','2026-08-10')])
        self.inputs(d)
        d['recent_five_runs'][1]['value'].pop()
        with self.assertRaises(ComplianceError): self.inputs(d)

    def test_price_missing_cannot_be_ev_skip(self):
        for state in ('NOT_ATTEMPTED', 'FAILED', 'DEADLINE_STOPPED'):
            m = self.market(); m['status'] = state
            if state != 'NOT_ATTEMPTED': m['attempted_at_jst'] = DATE+'T09:40:00+09:00'
            validate_market(m, DATE+'T09:50:00+09:00')
            m['decision'] = 'INSUFFICIENT_EV'
            with self.assertRaises(ComplianceError): validate_market(m, DATE+'T09:50:00+09:00')

    def test_acquired_price_ev_and_nonfinite_rejected(self):
        m = self.market(); m.update(status='ACQUIRED', odds=5, expected_value=-0.1, decision='INSUFFICIENT_EV',
                attempted_at_jst=DATE+'T09:40:00+09:00', acquired_at_jst=DATE+'T09:42:00+09:00', source_ref='official')
        validate_market(m, DATE+'T09:50:00+09:00')
        for value in (float('nan'), float('inf')):
            m['expected_value'] = value
            with self.assertRaises(ComplianceError): validate_market(m, DATE+'T09:50:00+09:00')

    def test_selection_requires_independent_pre_race_receipt(self):
        h = self.history(); validate_selection(self.root, h, {RACE: POST})
        h['events'][1]['evidence'].pop('receipt_id')
        with self.assertRaises(ComplianceError): validate_selection(self.root, h, {RACE: POST})

    def test_price_less_recommendation_cannot_be_actual_purchase(self):
        h = self.history(); h['events'][1]['purpose'] = 'ACTUAL_PURCHASE'
        with self.assertRaises(ValueError): validate_selection(self.root, h, {RACE: POST})

    def test_eight_ticket_comparison_and_missing_probability(self):
        rows = self.comparison()
        self.assertFalse(validate_ticket_comparison(rows, horses={1,2,3}, frames={})['optimality_certified'])
        with self.assertRaises(ComplianceError): validate_ticket_comparison(rows[:-1], horses={1,2,3}, frames={})

    def test_frames_and_ordered_ticket_events(self):
        frames = {1:1, 2:1, 3:2}
        ticket_event({'type':'BRACKET_QUINELLA','frames':[1,1]}, horses={1,2,3}, frames=frames)
        with self.assertRaises(ComplianceError):
            ticket_event({'type':'BRACKET_QUINELLA','frames':[2,2]}, horses={1,2,3}, frames=frames)
        self.assertNotEqual(ticket_event({'type':'EXACTA','horses':[1,2]}, horses={1,2}, frames={}),
                            ticket_event({'type':'EXACTA','horses':[2,1]}, horses={1,2}, frames={}))
        with self.assertRaises(ComplianceError): ticket_event({'type':'TRIO','horses':[1,2,4]}, horses={1,2,3}, frames={})

    def test_uncalibrated_cannot_claim_lower_bound(self):
        rows=self.comparison(); rows[0].update(status='COMPARED',tickets=[{'type':'WIN','horses':[1],
            'probability_method':'UNCALIBRATED','probability':0.5,'calibrated_lower_bound':0.4}])
        with self.assertRaises(ComplianceError): validate_ticket_comparison(rows,horses={1,2,3},frames={})
        rows[0]['tickets'][0]['calibrated_lower_bound']=None
        validate_ticket_comparison(rows,horses={1,2,3},frames={})

    def test_day_rejects_old_schema_outside_day_and_stage(self):
        d,c=self.complete_day()
        for key,value in [('schema_version','cycle03-day-v1'),('race_date_jst','2026-10-12'),
                          ('selected_scope',[]),('initial_scope',[RACE,RACE])]:
            bad=copy.deepcopy(d);bad[key]=value
            with self.assertRaises(ComplianceError): self.day(bad,c)

    def test_day_rejects_overlapping_kpis(self):
        d,c=self.complete_day();d['kpis']['production']['pending_ids']=[RACE]
        with self.assertRaises(ComplianceError): self.day(d,c)

    def test_all_horse_probability_evidence_and_target_omissions(self):
        d,c=self.complete_day()
        gp=self.root/d['races'][RACE]['prediction_gate_path'];g=json.loads(gp.read_text())
        g['production']['probabilities'].pop();gp.write_text(json.dumps(g))
        with self.assertRaises(ComplianceError):self.day(d,c)
        d,c=self.complete_day();d['kpis']['production'].update(target_ids=[],eligible_ids=[],reasons={})
        with self.assertRaises(ComplianceError):self.day(d,c)

    def test_input_evidence_hash_tampering_is_rejected(self):
        d,c=self.complete_day();ref=d['races'][RACE]['operations']['inputs_ref']
        p=self.root/ref['artifact_path'];p.write_text(p.read_text()+'\n')
        with self.assertRaises(ComplianceError):self.day(d,c)

    def test_other_day_append_does_not_change_prediction_hash(self):
        d,c=self.complete_day();before=(self.root/d['races'][RACE]['operations']['prediction_ref']['artifact_path']).read_bytes()
        write(self.root,f'docs/validation/snapshots/{DATE}/other.json','{"snapshot_id":"another"}\n')
        self.day(d,c)
        self.assertEqual((self.root/d['races'][RACE]['operations']['prediction_ref']['artifact_path']).read_bytes(),before)

    def test_actual_purchase_cannot_inherit_recommendation_eligibility(self):
        d,c=self.complete_day()
        d['kpis']['actual_purchase'].update(target_ids=[RACE],eligible_ids=[RACE],reasons={RACE:'購入報告なし'})
        with self.assertRaises(ComplianceError):self.day(d,c)

    def test_reviewed_scope_needs_result_and_preserves_no_future_result(self):
        d,c=self.complete_day();d['reviewed_scope']=[RACE]
        with self.assertRaises(ComplianceError):self.day(d,c)
        row=d['races'][RACE];row['scheduled_post_time_jst']=POST
        result={'status':'OFFICIAL','race_id':RACE,'race_date_jst':DATE,'source_url':'https://example.invalid/official',
                'retrieved_at_jst':DATE+'T11:00:00+09:00','finish_groups':[[5],[2],[6],[4],[1],[3]],'place_places':3}
        path='result.json';write(self.root,path,json.dumps(result))
        row['result_ref']={'artifact_path':path,'sha256':fingerprint((self.root/path).read_bytes())}
        row['review']={'error_classification':'test','non_degradation':'test','next_validation':'test'}
        from recommendation import settle,verify
        row['recommendation_result']=settle(verify(self.root,self.root/row['recommendation_gate_path']),result)
        # 旧来のresult単独保存は正式結果の出所証跡として認証しない。
        with self.assertRaisesRegex(ComplianceError, 'frozen path/hash'):
            self.day(d,c)
        result['retrieved_at_jst']=DATE+'T09:00:00+09:00';write(self.root,path,json.dumps(result))
        row['result_ref']['sha256']=fingerprint((self.root/path).read_bytes())
        with self.assertRaises(ComplianceError):self.day(d,c)

    def test_day_rejects_replay_and_pending_cutover(self):
        d,c=self.complete_day();d['races'][RACE]['mode']='REPLAY'
        with self.assertRaises(ComplianceError):self.day(d,c)
        d['races'][RACE]['mode']='FORWARD';c['status']='PREPARED'
        with self.assertRaises(ComplianceError):self.day(d,c)

    def test_false_input_complete_and_late_independent_hash_fail(self):
        d,c=self.complete_day();d['races'][RACE]['input_complete']=True
        with self.assertRaises(ComplianceError):self.day(d,c)
        d['races'][RACE]['input_complete']=False
        rp=self.root/f'docs/validation/persistence-receipts/{DATE}.md'
        rp.write_text(rp.read_text().replace(DATE+'T09:56:00+09:00',DATE+'T10:10:00+09:00'))
        with self.assertRaises(ComplianceError):self.day(d,c)

    def test_independent_hash_then_body_immutable_retry(self):
        draft={'schema_version':'prediction-snapshot-v2','snapshot_id':'p1','race_id':RACE,
               'scheduled_post_time_jst':POST,'working_branch':'prediction/'+DATE,'fixed_at_jst':DATE+'T09:50:00+09:00'}
        draft_path=self.root/'draft.json';draft_path.write_text(json.dumps(draft))
        body=f'docs/validation/snapshots/{DATE}/p1.json';fix=f'docs/validation/fix-manifests/{DATE}/p1.json'
        intent={'schema_version':'prediction-persistence-intent-v1','snapshot_id':'p1','required_race_ids':[RACE],
                'artifact_path':body,'deadline_jst':POST}
        ref=self.artifact('intent','intent.json',intent)
        now=datetime.fromisoformat(DATE+'T09:52:00+09:00')
        seal(self.root,draft_path,body,fix,ref,now=now)
        self.assertFalse((self.root/body).exists())
        manifest=json.loads((self.root/fix).read_text());fref=self.artifact('fix',fix,manifest,at='09:51')
        seal(self.root,draft_path,body,fix,ref,fref,now=now)
        seal(self.root,draft_path,body,fix,ref,fref,now=now)
        before=(self.root/body).read_bytes()
        draft['extra']='changed';draft_path.write_text(json.dumps(draft))
        with self.assertRaises(ComplianceError):seal(self.root,draft_path,body,fix,ref,fref,now=now)
        self.assertEqual((self.root/body).read_bytes(),before)
        with self.assertRaises(ComplianceError):seal(self.root,draft_path,body,fix,ref,now=datetime.fromisoformat(POST))

    def test_undecided_release_stays_pending_and_cannot_activate(self):
        write(self.root,'docs/manual/README.md','現行リリース: `v1.6.1`\n')
        p=write_contract_state(self.root)
        s=json.loads(p.read_text());s['next_release']=None;p.write_text(json.dumps(s))
        self.assertIsNone(contract_state(self.root)['next_release'])
        with self.assertRaises(ComplianceError):require_active(self.root,{'status':'PREPARED'})
        s['status']='ACTIVE';p.write_text(json.dumps(s))
        with self.assertRaises(ComplianceError):contract_state(self.root)

    def test_preparation_rejects_stale_acceptance_and_live_claim(self):
        import check_cycle04
        root=Path(__file__).resolve().parents[1]
        original_load=check_cycle04.load
        report=original_load(root/'docs/validation/reviews/cycle_04/acceptance.json')
        # 合成fixture。全ソースhashを現在のbytesへ揃えた準備正常系と、劣化を独立確認。
        for item in report['source_manifest']:
            item['sha256']=fingerprint((root/item['path']).read_bytes())
        def fixture_load(path):
            return copy.deepcopy(report) if path.name=='acceptance.json' else original_load(path)
        with patch('check_cycle04.load',side_effect=fixture_load):
            check_preparation(root)
            report['source_manifest'][0]['sha256']='0'*64
            with self.assertRaises(ComplianceError):check_preparation(root)
            report['source_manifest'][0]['sha256']=fingerprint((root/report['source_manifest'][0]['path']).read_bytes())
            report['live_race_count']=144
            with self.assertRaises(ComplianceError):check_preparation(root)

    def test_preparation_requires_all_individual_dispositions(self):
        import check_cycle04
        root=Path(__file__).resolve().parents[1];original_load=check_cycle04.load
        decisions=original_load(root/'docs/validation/reviews/cycle_03/decisions.json')
        decisions['changes'].pop()
        with patch('check_cycle04.load',side_effect=lambda p: decisions if p.name=='decisions.json' else original_load(p)):
            with self.assertRaises(ComplianceError):check_preparation(root)


if __name__=='__main__':unittest.main()
