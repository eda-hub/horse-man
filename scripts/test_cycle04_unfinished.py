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
        self.unsealed_path = self.root / payload['unsealed_decision_path']

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

    def unsealed(self):
        return json.loads(self.unsealed_path.read_text(encoding='utf-8'))

    def rewrite_unsealed(self, data):
        self.unsealed_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n',
                                      encoding='utf-8')

    def test_kyoto10_carries_late_reference_without_formal_promotion(self):
        index = self.data()
        row = next(r for r in index['races'] if r['race_id'] == '2026-10-17-KYOTO-10')
        self.assertEqual(row['recommendation']['status'],
                         'UNSEALED_LATE_PRESERVATION_CANDIDATE')
        decisions = self.unsealed()['decisions']
        candidate = next(x['recorded_candidate'] for x in decisions
                         if x['race_id'] == '2026-10-17-KYOTO-10')
        self.assertEqual(candidate, {'type': 'WIDE', 'horse_numbers': [6, 7],
                                     'points': 1, 'official_recommendation': False})
        report = check(self.root, self.MANIFEST)
        self.assertEqual(report['recommendation_states']
                         ['UNSEALED_LATE_PRESERVATION_CANDIDATE'], 1)
        self.assertFalse(report['formal_kpi_certified'])

    def test_kyoto08_transcribed_horses_differ_from_original(self):
        data = self.unsealed()
        item = next(x for x in data['decisions']
                    if x['race_id'] == '2026-10-17-KYOTO-08')
        item['recorded_candidate']['horse_numbers'] = [1, 2]
        self.rewrite_unsealed(data)
        with self.assertRaisesRegex(UnfinishedIndexError, '券種・馬番・点数'):
            check(self.root, self.MANIFEST)

    def test_kyoto10_transcribed_horses_differ_from_original(self):
        data = self.unsealed()
        item = next(x for x in data['decisions']
                    if x['race_id'] == '2026-10-17-KYOTO-10')
        item['recorded_candidate']['horse_numbers'] = [1, 2]
        self.rewrite_unsealed(data)
        with self.assertRaisesRegex(UnfinishedIndexError, '券種・馬番・点数'):
            check(self.root, self.MANIFEST)

    def test_kyoto10_transcribed_ticket_type_or_points_differ(self):
        for key, value in [('type', 'QUINELLA'), ('points', 2)]:
            with self.subTest(key=key):
                data = self.unsealed()
                item = next(x for x in data['decisions']
                            if x['race_id'] == '2026-10-17-KYOTO-10')
                original = item['recorded_candidate'][key]
                item['recorded_candidate'][key] = value
                self.rewrite_unsealed(data)
                with self.assertRaisesRegex(UnfinishedIndexError, '券種・馬番・点数'):
                    check(self.root, self.MANIFEST)
                item['recorded_candidate'][key] = original
                self.rewrite_unsealed(data)

    def test_pinned_source_modified_without_hash_change(self):
        data = self.unsealed()
        item = next(x for x in data['decisions']
                    if x['race_id'] == '2026-10-17-KYOTO-08')
        source = self.root / item['source_path']
        source.write_text(source.read_text(encoding='utf-8').replace(
                          '3 アンムート－6 カレンハウ、1点',
                          '1 アンムート－2 カレンハウ、1点'), encoding='utf-8')
        with self.assertRaisesRegex(UnfinishedIndexError, 'SHA-256'):
            check(self.root, self.MANIFEST)

    def test_niigata11_study_candidate_mismatch(self):
        data = self.unsealed()
        item = next(x for x in data['decisions']
                    if x['race_id'] == '2026-10-17-NIIGATA-11')
        item['recorded_candidate']['horse_numbers'] = [6, 5]
        self.rewrite_unsealed(data)
        with self.assertRaisesRegex(UnfinishedIndexError, '券種・馬番・点数'):
            check(self.root, self.MANIFEST)

    def test_missing_late_preservation_reference_rejected(self):
        data = self.unsealed()
        data['decisions'] = [x for x in data['decisions']
                             if x['race_id'] != '2026-10-17-KYOTO-10']
        self.rewrite_unsealed(data)
        with self.assertRaisesRegex(UnfinishedIndexError, '参照対応'):
            check(self.root, self.MANIFEST)

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
