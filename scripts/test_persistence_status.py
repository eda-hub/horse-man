import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

from persistence_status import describe_persistence, render_persistence, main


class PersistenceStatusTests(unittest.TestCase):
    def report(self, **evidence):
        return describe_persistence('京都10Rの予想', **evidence)

    def test_not_attempted_does_not_claim_failure_or_completion(self):
        r = self.report()
        self.assertEqual(r['status_code'], 'NOT_ATTEMPTED')
        self.assertFalse(r['complete'])
        self.assertEqual(r['checks']['書込'], '未実施')
        self.assertNotIn('失敗', r['message'])

    def test_failed_write_is_not_unattempted(self):
        r = self.report(write_attempted=True, write_succeeded=False)
        self.assertEqual(r['status_code'], 'WRITE_FAILED')
        self.assertEqual(r['checks']['書込'], '失敗')
        self.assertFalse(r['complete'])

    def test_readback_mismatch_does_not_mark_body_verified(self):
        r = self.report(write_attempted=True, write_succeeded=True, readback_matches=False)
        self.assertEqual(r['status_code'], 'READBACK_MISMATCH')
        self.assertIn('一致しません', r['message'])
        self.assertFalse(r['complete'])

    def test_readback_success_without_individual_check_is_incomplete(self):
        r = self.report(write_attempted=True, write_succeeded=True, readback_matches=True)
        self.assertEqual(r['status_code'], 'BODY_SAVED_UNVERIFIED')
        self.assertIn('保存済み', r['message'])
        self.assertIn('未実施', r['message'])
        self.assertFalse(r['complete'])

    def test_all_three_successes_are_required_for_completion(self):
        r = self.report(write_attempted=True, write_succeeded=True, readback_matches=True,
                        verification_succeeded=True)
        self.assertEqual(r['status_code'], 'COMPLETE')
        self.assertTrue(r['complete'])
        self.assertEqual(set(r['checks'].values()), {'成功'})

    def test_unchecked_readback_is_not_a_mismatch_or_verified_save(self):
        r = self.report(write_attempted=True, write_succeeded=True)
        self.assertEqual(r['status_code'], 'BODY_SAVED_UNVERIFIED')
        self.assertIn('書込済み', r['message'])
        self.assertNotIn('保存済み', r['message'])
        self.assertEqual(r['checks']['読戻し一致'], '未実施')

    def test_failed_individual_check_is_not_called_unperformed(self):
        r = self.report(write_attempted=True, write_succeeded=True, readback_matches=True,
                        verification_succeeded=False)
        self.assertEqual(r['checks']['個別完了確認'], '失敗')
        self.assertNotIn('未実施', r['message'])
        self.assertFalse(r['complete'])

    def test_unknown_write_result_cannot_be_invented_as_failure(self):
        with self.assertRaisesRegex(ValueError, '書込結果が未確認'):
            self.report(write_attempted=True)

    def test_contradictory_stage_results_are_rejected(self):
        for evidence in ({'write_succeeded': True},
                         {'write_attempted': True, 'write_succeeded': False, 'readback_matches': True},
                         {'write_attempted': True, 'write_succeeded': True,
                          'readback_matches': False, 'verification_succeeded': True}):
            with self.subTest(evidence=evidence), self.assertRaises(ValueError):
                self.report(**evidence)

    def test_strings_and_numbers_cannot_be_truthy_success(self):
        for value in ('false', 1, [], {}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.report(write_attempted=True, write_succeeded=value)

    def test_user_output_has_target_cause_impact_next_and_no_internal_code(self):
        r = describe_persistence('推奨買い目', write_attempted=True, write_succeeded=True,
                                 readback_matches=True)
        text = render_persistence(r)
        for label in ('対象：推奨買い目', '原因：', '影響：', '次の確認：'):
            self.assertIn(label, text)
        self.assertNotIn(r['status_code'], text)

    def test_audit_result_cannot_stand_in_for_individual_completion(self):
        with self.assertRaises(TypeError):
            describe_persistence('予想', audit_succeeded=True)

    def test_cli_default_is_japanese_and_json_is_explicit(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'evidence.json'
            path.write_text(json.dumps({'target': '予想'}), encoding='utf-8')
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                self.assertEqual(main(['--evidence', str(path)]), 0)
            self.assertIn('保存は未試行', stdout.getvalue())
            self.assertNotIn('NOT_ATTEMPTED', stdout.getvalue())
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                self.assertEqual(main(['--evidence', str(path), '--json']), 0)
            self.assertEqual(json.loads(stdout.getvalue())['status_code'], 'NOT_ATTEMPTED')

    def test_invalid_cli_evidence_fails_without_a_success_message(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'evidence.json'
            path.write_text('{', encoding='utf-8')
            stdout, stderr = io.StringIO(), io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                self.assertEqual(main(['--evidence', str(path)]), 1)
            self.assertEqual(stdout.getvalue(), '')
            self.assertIn('保存状態を判定できません', stderr.getvalue())


if __name__ == '__main__':
    unittest.main()
