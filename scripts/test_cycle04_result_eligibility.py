"""公式結果の標準入口が単独の結果自己申告を受け入れないことを検査する。"""
import copy
import json
import unittest

import cycle04_workflow as workflow
from check_prediction_compliance import ComplianceError
from test_next_prediction_compliance import write
from test_recommendation import DATE, RACE
import test_cycle04_workflow as operations


class FormalResultRegression(unittest.TestCase):
    def setUp(self):
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
