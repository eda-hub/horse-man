#!/usr/bin/env python3
"""未完了日索引の正常受入・範囲欠落・改ざんを検証。"""
import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from check_cycle04_unfinished import check, UnfinishedIndexError


class UnfinishedDayTest(unittest.TestCase):
    SOURCE = Path(__file__).resolve().parent.parent
    MANIFEST = 'docs/validation/reconciliations/2026-10-17-day-index.json'

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        payload = json.loads((self.SOURCE / self.MANIFEST).read_text(encoding='utf-8'))
        paths = {self.MANIFEST, payload['source_intent_path'], payload['screening_path'],
                 payload['unsealed_decision_path']}
        for row in payload['races']:
            paths.update(x for x in (
                row['prediction'].get('path'), row['prediction'].get('fix_path'),
                row['prediction'].get('gate_path'), row['recommendation'].get('path'),
            ) if x)
        for name in paths:
            to = self.root / name
            to.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(self.SOURCE / name, to)
        self.manifest_path = self.root / self.MANIFEST

    def data(self):
        return json.loads(self.manifest_path.read_text(encoding='utf-8'))

    def rewrite(self, data):
        self.manifest_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n',
                                      encoding='utf-8')

    def test_36_races_remain_unfinished_not_eligible(self):
        output = check(self.root, self.MANIFEST)
        self.assertEqual(output['verified_race_count'], 36)
        self.assertEqual(output['prediction_states']['PRE_RACE_BODY_ARCHIVED_NOT_CYCLE04_ACCEPTED'], 4)
        self.assertEqual(output['prediction_states']['AFTER_POST_CHAT_PRESERVATION_ONLY'], 2)
        self.assertEqual(output['prediction_states']['NOT_PERSISTED'], 30)
        self.assertFalse(output['formal_kpi_certified'])

    def test_missing_race_rejected(self):
        data = self.data()
        data['races'].pop()
        self.rewrite(data)
        with self.assertRaises(UnfinishedIndexError):
            check(self.root, self.MANIFEST)

    def test_falsely_registered_scope_rejected(self):
        data = self.data()
        data['official_scope_status'] = 'REGISTERED'
        self.rewrite(data)
        with self.assertRaises(UnfinishedIndexError):
            check(self.root, self.MANIFEST)

    def test_tampered_prediction_digest_rejected(self):
        data = self.data()
        item = next(r for r in data['races']
                    if r['prediction']['status'] == 'PRE_RACE_BODY_ARCHIVED_NOT_CYCLE04_ACCEPTED')
        source = self.root / item['prediction']['path']
        source.write_text(source.read_text(encoding='utf-8') + '\n', encoding='utf-8')
        with self.assertRaises(UnfinishedIndexError):
            check(self.root, self.MANIFEST)


if __name__ == '__main__':
    unittest.main()
