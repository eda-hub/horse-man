import copy
import json
import tempfile
import unittest
from pathlib import Path

import test_chat_fact_capture as facts
import test_chat_fact_input as inputs
import test_next_prediction_compliance as receipts
from chat_fact_input import convert
from chat_fact_provenance import consistency, verify_saved
from cycle04_operations import fingerprint


class Provenance(unittest.TestCase):
    def fixture(self):
        b = facts.FactCapture().normalize()
        return b, convert(b, inputs.annotations(), facts.DATE+'T09:45:00+09:00')

    def test_numeric_fact_and_horse_identity_bind_to_exact_source(self):
        b, c = self.fixture()
        self.assertTrue(consistency(b, c)['extraction_consistency_verified'])
        self.assertFalse(consistency(b, c)['formal_kpi_certified'])
        c['input']['body_weight'][0]['value'] = 500
        with self.assertRaises(ValueError): consistency(b, c)
        annotation = inputs.annotations()
        annotation['body_weight'][0].update(value=500, quotations=[{
            'capture_id':'c1','start':0,'end':17,'quote':'1番 480kg\n2番 500kg'}])
        combined = convert(b, annotation, facts.DATE+'T09:45:00+09:00')
        with self.assertRaises(ValueError): consistency(b, combined)

    def test_coverage_metadata_and_extra_binding_cannot_be_changed(self):
        for mutate in [lambda c: c['coverage'].update(complete=True),
                       lambda c: c['input']['body_weight'][0].update(provider='FALLBACK'),
                       lambda c: c['bindings'].append({'field':'wrong','row_index':0})]:
            b, c = self.fixture(); mutate(c)
            with self.assertRaises(ValueError): consistency(b, c)

    def test_recent_run_scalar_coverage_and_source_identity(self):
        from datetime import datetime
        from chat_fact_capture import normalize
        source = facts.capture()
        lines = ['1番 2026-10-11T10:00:00+09:00 1勝 同級',
                 '2番 2026-10-11T10:00:00+09:00 1勝 同級']
        source['text'] += '\n'.join(lines)
        b = normalize(facts.request(), [source], datetime.fromisoformat(facts.DATE+'T09:40:00+09:00'))
        a = inputs.annotations()
        for n, h in enumerate([1, 2]):
            line = lines[n]; start = source['text'].index(line)
            refs = [{'capture_id':'c1','start':start,'end':start+len(line),'quote':line,
                     'value_pointer':p} for p in ['/0/race_at_jst','/0/class','/0/opponent_level/value']]
            a['recent_five_runs'][n] = {'horse_no':h,'status':'ACQUIRED','reason':'本文確認',
                'prior_start_count':1,'quotations':refs,'value':[{
                'race_at_jst':'2026-10-11T10:00:00+09:00','class':'1勝','source_ref':source['source_url'],
                'opponent_level':{'status':'ACQUIRED','value':'同級','source_ref':source['source_url'],
                                  'observed_at_jst':source['source_updated_at_jst']}}]}
        c = convert(b, a, facts.DATE+'T09:45:00+09:00')
        self.assertTrue(consistency(b, c)['coverage']['complete'])
        c['input']['recent_five_runs'][0]['value'][0]['source_ref'] = 'other-source'
        with self.assertRaises(ValueError): consistency(b, c)

    def test_saved_receipts_hash_and_order_are_independent(self):
        b, c = self.fixture(); date = facts.DATE; post = date+'T10:00:00+09:00'
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); rp = 'docs/validation/persistence-receipts/'+date+'.md'
            records, refs = [], []
            for ident, payload, at in [('capture', b, '09:42'), ('conversion', c, '09:46')]:
                path = ident+'.json'; raw = (json.dumps(payload)+'\n').encode(); (root/path).write_bytes(raw)
                rec = receipts.receipt_record(ident+'-receipt', ident, path,
                       verified=date+'T'+at+':00+09:00', post=post)
                rec['content_sha256'] = fingerprint(raw)
                rec['receipt_verified_at_jst'] = rec['persist_verified_at_jst']
                records.append(rec)
                refs.append({'artifact_id':ident,'artifact_path':path,'sha256':fingerprint(raw),
                             'receipt_path':rp,'receipt_id':rec['receipt_id']})
            receipts.write_receipts(root, rp, records)
            self.assertTrue(verify_saved(root, *refs, post)['independent_receipts_verified'])
            (root/'capture.json').write_text('{}')
            with self.assertRaises(ValueError): verify_saved(root, *refs, post)


if __name__ == '__main__': unittest.main()
