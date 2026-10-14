"""公式結果の標準入口が単独の結果自己申告を受け入れないことを検査する。"""
import copy
from datetime import datetime
import json
import unittest

import cycle04_workflow as workflow
from check_prediction_compliance import ComplianceError
from test_next_prediction_compliance import write
from cycle04_operations import fingerprint
from chat_fact_capture import normalize as normalize_capture
from chat_result_conversion import normalize_result
import test_chat_fact_capture as facts
from test_recommendation import POST
from test_recommendation import DATE, RACE



def make_result_entry(case, *, scratched=(), mode='FORWARD'):
    """合成fixtureから照合manifestを独立保存。実測成績ではない。"""
    root = case.root
    row = workflow.read_day(root, DATE)[0]['races'][RACE]
    horses = row.get('operations', {}).get('horse_numbers', [5, 2, 6, 4, 1, 3])
    ordered = [h for h in (5, 2, 6, 4, 1, 3) if h in horses and h not in scratched]
    lines = ['確定結果', '発売開始時 6頭']
    rows = []
    for position, h in enumerate(ordered, 1):
        line = str(position) + '着 ' + str(h) + '番'
        lines.append(line)
        rows.append((h, 'FINISHED', position, line))
    for h in scratched:
        line = '取消 ' + str(h) + '番'
        lines.append(line)
        rows.append((h, 'SCRATCHED', None, line))
    lines.append('2026年10月17日 東京 1レース 発走時刻10時10分')
    req = facts.request()
    req.update(purpose='RESULT', scheduled_post_time_jst=POST,
               data_cutoff=DATE + 'T10:30:00+09:00',
               horse_numbers=list(horses))
    capture = facts.capture()
    capture.update(text='\n'.join(lines), mode=mode,
                   retrieval_kind='SYNTHETIC_PAGE_TEXT' if mode == 'SYNTHETIC' else 'PAGE_TEXT',
                   source_updated_at_jst=None,
                   read_started_at_jst=DATE + 'T10:15:00+09:00',
                   read_finished_at_jst=DATE + 'T10:16:00+09:00')
    bundle = normalize_capture(req, [capture], datetime.fromisoformat(DATE + 'T10:20:00+09:00'))
    def quote(line):
        start = capture['text'].index(line)
        return {'capture_id': 'c1', 'start': start,
                'end': start + len(line), 'quote': line}
    annotation = {'confirmation': quote(lines[0]), 'race_identity': quote(lines[-1]),
                  'place_basis': {'kind': 'OFFICIAL_SALES_START_COUNT',
                                  'value': 6, 'quotation': quote(lines[1])},
                  'rows': [{'horse_no': h, 'status': status, 'finish_position': position,
                            'quotation': quote(line)} for h, status, position, line in rows]}
    conversion = normalize_result(bundle, annotation)
    result = conversion['result']
    def frozen(path, data):
        raw = (json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode()
        write(root, path, raw.decode())
        return {'artifact_path': path, 'sha256': fingerprint(raw)}
    refs = {key: frozen('result-audit/' + key + '.json', data)
            for key, data in [('capture', bundle), ('conversion', conversion), ('result', result)]}
    history = row.get('prediction_history', [])
    refs['prediction_gate'] = ({'artifact_path': row['prediction_gate_path'],
                                'sha256': history[-1]['prediction_gate_sha256']}
                               if row.get('prediction_gate_path') else None)
    refs['prediction_original'] = copy.deepcopy(history[-1]['prediction_ref']) if history and refs['prediction_gate'] else None
    path = row.get('recommendation_gate_path')
    refs['recommendation_gate'] = ({'artifact_path': path,
                                   'sha256': fingerprint((root / path).read_bytes())} if path else None)
    manifest = frozen('result-audit/manifest.json',
                      {'schema_version': 'cycle04-result-reconciliation-manifest-v1',
                       'refs': refs})
    return {'race_id': RACE, 'result_path': refs['result']['artifact_path'],
            'result_reconciliation_ref': manifest,
            'review': {'error_classification': '検証', 'non_degradation': '保全',
                       'next_validation': '次回比較'}}


class FormalResultRegression(unittest.TestCase):
    def setUp(self):
        import test_cycle04_workflow as operations
        self.case = operations.OperationalWorkflow()
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.root = self.case.root
        self.case.register()
        workflow.record_prediction(self.root, DATE, self.case.entry)

    def entry(self, **overrides):
        result = {'race_id': RACE, 'race_date_jst': DATE, 'status': 'OFFICIAL',
                  'source_url': 'https://www.jra.go.jp/test/result',
                  'retrieved_at_jst': DATE + 'T11:00:00+09:00',
                  'finish_groups': [[5], [2], [6], [4], [1], [3]], 'place_places': 3}
        result.update(overrides)
        write(self.root, 'result.json', json.dumps(result))
        return {'race_id': RACE, 'result_path': 'result.json',
                'review': {'error_classification': '検証', 'non_degradation': '保全',
                           'next_validation': '再確認'}}

    def test_forward_self_asserted_result_without_source_manifest_is_rejected(self):
        path = self.root / workflow.DIRECTORY / (DATE + '.json')
        before = path.read_bytes()
        with self.assertRaises(ComplianceError):
            workflow.review(self.root, DATE, self.entry())
        self.assertEqual(path.read_bytes(), before)

    def test_synthetic_replay_and_mode_removed_do_not_certify_a_review(self):
        for changes in ({'mode': 'SYNTHETIC'}, {'mode': 'REPLAY'}, {}):
            with self.subTest(changes=changes):
                path = self.root / workflow.DIRECTORY / (DATE + '.json')
                before = path.read_bytes()
                with self.assertRaises(ComplianceError):
                    workflow.review(self.root, DATE, self.entry(**changes))
                self.assertEqual(path.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
