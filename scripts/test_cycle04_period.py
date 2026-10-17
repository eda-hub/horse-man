"""期間延長の登録・開催場・全日終了・JST境界を合成台帳で確認する。"""
import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import check_cycle04 as checker
import cycle04_workflow as workflow
import class_transition_shadow as shadow
from check_prediction_compliance import ComplianceError
import test_cycle04_workflow as fixtures

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = ['2026-10-17', '2026-10-18', '2026-10-24', '2026-10-25', '2026-10-31', '2026-11-01']


class ExtendedPeriod(unittest.TestCase):
    def test_registration_and_summary_accept_all_six_days(self):
        fixture = fixtures.OperationalWorkflow()
        fixture.addCleanup = self.addCleanup
        fixture.setUp()
        for date in EXPECTED:
            scope = copy.deepcopy(fixture.scope)
            scope['race_date_jst'] = date
            scope['observed_at_jst'] = date + 'T09:30:00+09:00'
            scope['races'] = [{'race_id': date.replace('-', '') + '-' + venue + '-01',
                               'scheduled_post_time_jst': date + 'T10:30:00+09:00'}
                              for venue in checker.VENUES_BY_DATE[date]]
            workflow.register_scope(fixture.root, scope,
                                    now=datetime.fromisoformat(date + 'T09:38:00+09:00'))
        report = workflow.summary(fixture.root)
        self.assertEqual(report['expected_dates'], EXPECTED)
        self.assertEqual(report['recorded_dates'], EXPECTED)
        self.assertEqual(report['initial_races'], 16)
        self.assertEqual(report['reviewed_races'], 0)

    def test_added_days_reject_niigata_and_outside_dates_without_write(self):
        fixture = fixtures.OperationalWorkflow()
        fixture.addCleanup = self.addCleanup
        fixture.setUp()
        for date in ('2026-10-31', '2026-11-01', '2026-10-30', '2026-11-07'):
            scope = copy.deepcopy(fixture.scope)
            scope['race_date_jst'] = date
            scope['observed_at_jst'] = date + 'T09:30:00+09:00'
            scope['races'] = [{'race_id': date.replace('-', '') + '-NII-01',
                               'scheduled_post_time_jst': date + 'T10:30:00+09:00'}]
            with self.subTest(date=date), self.assertRaises(ComplianceError):
                workflow.register_scope(fixture.root, scope,
                                        now=datetime.fromisoformat(date + 'T09:38:00+09:00'))
            self.assertFalse((fixture.root / workflow.DIRECTORY / (date + '.json')).exists())

    def test_complete_requires_six_days_stages_and_saved_summary(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = root / workflow.DIRECTORY
            directory.mkdir(parents=True)
            days = {}
            def check():
                with patch.object(checker, 'check_preparation', return_value={'status': 'ACTIVE'}), \
                     patch.object(checker, 'validate_day', side_effect=lambda root, path, contract: days[path.stem]), \
                     redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                    return checker.main(['--root', str(root), '--require-complete'])
            for date in EXPECTED[:4]:
                (directory / (date + '.json')).write_text('{}')
                days[date] = {'race_date_jst': date, 'initial_scope': ['race'], 'reviewed_scope': ['race']}
            self.assertEqual(check(), 1)
            for date in EXPECTED[4:]:
                (directory / (date + '.json')).write_text('{}')
                days[date] = {'race_date_jst': date, 'initial_scope': ['race'], 'reviewed_scope': ['race']}
            # 6日登録・回顧集合だけでは正常一巡/集計Git読戻しを満たさない。
            self.assertEqual(check(), 1)
            with patch('cycle04_completion.evaluate_days', return_value={
                    'normal_cycle_complete': True, 'issues': [],
                    'state': '正常一巡完了', 'summary_git_readback_verified': True}):
                self.assertEqual(check(), 0)
            days[EXPECTED[-1]]['reviewed_scope'] = []
            self.assertEqual(check(), 1)

    def test_all_schedule_contracts_match_and_launch_has_no_measured_data(self):
        self.assertEqual(checker.DATES, EXPECTED)
        self.assertEqual(shadow.DATES, EXPECTED)
        for path in ('contracts/cycle_04.json', 'class-transition/forward-plan.json'):
            data = json.loads((ROOT / 'docs/validation' / path).read_text())
            self.assertEqual(data['race_dates'], EXPECTED)
        self.assertFalse((ROOT / 'docs/validation/contracts/cycle04-launch.json').exists())

    def test_period_ends_after_november_first_in_japan(self):
        plan = json.loads((ROOT / 'docs/validation/class-transition/forward-plan.json').read_text())
        for instant in ('2026-10-25T15:01:00+00:00', '2026-11-01T14:59:59+00:00'):
            self.assertFalse(shadow.collection(ROOT, [], plan, as_of=instant)['period_complete'])
        self.assertTrue(shadow.collection(ROOT, [], plan, as_of='2026-11-01T15:00:00+00:00')['period_complete'])

    def test_comparison_rejects_niigata_on_added_days(self):
        plan = json.loads((ROOT / 'docs/validation/class-transition/forward-plan.json').read_text())
        for date in EXPECTED[-2:]:
            for venue in ('NII', 'NIIGATA'):
                gate = {'mode': 'FORWARD', 'race_date_jst': date,
                        'race_id': date.replace('-', '') + '-' + venue + '-01',
                        'kpi_eligibility': {'production': 'ELIGIBLE', 'shadow': 'ELIGIBLE'}}
                with self.subTest(date=date, venue=venue), \
                     patch.object(shadow, 'validate_gate', return_value=gate), \
                     self.assertRaisesRegex(ComplianceError, '開催日・開催場'):
                    shadow.verified_pair(ROOT, {'gate_path': 'synthetic-gate.json'}, plan,
                                         datetime.fromisoformat(date + 'T18:00:00+09:00'))
