import hashlib
import io
import json
import sys
import unittest
from contextlib import redirect_stdout, redirect_stderr
from unittest.mock import patch

import test_recommendation as fixtures
from task_completion import prediction_completion, recommendation_completion, render_completion
from verify_prediction_persistence import main as prediction_main
from recommendation import main as recommendation_main
from check_prediction_compliance import receipt_records
from test_check_prediction_compliance import write_receipts


class TaskCompletionTests(unittest.TestCase):
    def fixture(self, pending_shadow=False):
        helper = fixtures.RecommendationTest()
        self.addCleanup(helper.doCleanups)
        root, gate, prediction = helper.root()
        if pending_shadow:
            gate['kpi_eligibility']['shadow'] = 'PENDING'
            gate['shadow_items'] = [{'item_id': 'test-shadow', 'state': 'NOT_STARTED',
                                     'kpi_eligibility': 'PENDING'}]
            (root / f'docs/validation/execution-gates/{fixtures.DATE}/{fixtures.RACE}.json').write_text(json.dumps(gate))
        rec_gate, rec_path = helper.artifacts(root, gate, prediction)
        receipt_path = f'docs/validation/persistence-receipts/{fixtures.DATE}.md'
        records = receipt_records(root / receipt_path)
        for record in records:
            record.setdefault('receipt_verified_at_jst', record['persist_verified_at_jst'])
        write_receipts(root, receipt_path, records)
        pred_path = prediction['snapshot_id']
        pred_hash = hashlib.sha256((root / f'docs/validation/snapshots/{fixtures.DATE}/{pred_path}.json').read_bytes()).hexdigest()
        rec_hash = hashlib.sha256((root / rec_path).read_bytes()).hexdigest()
        return root, prediction, pred_hash, rec_gate, rec_path, rec_hash

    def prediction(self, root, prediction, digest=None, **kwargs):
        return prediction_completion(root, fixtures.DATE, prediction['snapshot_id'], intent_id='first',
                                     fixed_content_sha256=digest, **kwargs)

    def test_complete_prediction_checks_real_intent_receipt_hash_and_gate(self):
        root, prediction, digest, _, _, _ = self.fixture()
        r = self.prediction(root, prediction, digest)
        self.assertTrue(r['complete'])
        self.assertEqual(r['checks']['shadow']['result'], 'NOT_APPLICABLE')
        self.assertIsNone(r['checks']['audit']['result'])

    def test_audit_success_does_not_complete_an_unchecked_target(self):
        root, prediction, _, _, _, _ = self.fixture()
        r = self.prediction(root, prediction, audit_succeeded=True)
        self.assertFalse(r['complete'])
        self.assertTrue(r['checks']['artifact']['result'])
        self.assertTrue(r['checks']['receipt']['result'])
        self.assertIsNone(r['checks']['individual_check']['result'])
        self.assertIn('未実施', render_completion(r))

    def test_receipt_missing_does_not_erase_saved_prediction(self):
        root, prediction, digest, _, _, _ = self.fixture()
        (root / f'docs/validation/persistence-receipts/{fixtures.DATE}.md').unlink()
        r = self.prediction(root, prediction, digest)
        self.assertTrue(r['checks']['artifact']['result'])
        self.assertFalse(r['checks']['receipt']['result'])
        self.assertFalse(r['complete'])
        self.assertNotIn('WRITE_FAILED', render_completion(r))

    def test_wrong_fix_hash_is_a_readback_mismatch(self):
        root, prediction, _, _, _, _ = self.fixture()
        r = self.prediction(root, prediction, '0' * 64)
        self.assertFalse(r['checks']['content_match']['result'])
        self.assertEqual(r['persistence']['status_code'], 'READBACK_MISMATCH')
        self.assertFalse(r['complete'])

    def test_gate_missing_is_independent_of_individual_persistence(self):
        root, prediction, digest, _, _, _ = self.fixture()
        (root / f'docs/validation/execution-gates/{fixtures.DATE}/{fixtures.RACE}.json').unlink()
        r = self.prediction(root, prediction, digest)
        self.assertTrue(r['checks']['individual_check']['result'])
        self.assertFalse(r['checks']['execution_gate']['result'])
        self.assertIsNone(r['checks']['shadow']['result'])
        self.assertFalse(r['complete'])

    def test_pending_applicable_shadow_only_blocks_that_component(self):
        root, prediction, digest, _, _, _ = self.fixture(pending_shadow=True)
        r = self.prediction(root, prediction, digest)
        self.assertTrue(r['checks']['individual_check']['result'])
        self.assertTrue(r['checks']['execution_gate']['result'])
        self.assertFalse(r['checks']['shadow']['result'])
        self.assertEqual(r['missing'], ['shadow'])

    def test_completed_ineligible_shadow_requires_actual_saved_evidence(self):
        root, prediction, digest, _, _, _ = self.fixture()
        path = root / f'docs/validation/execution-gates/{fixtures.DATE}/{fixtures.RACE}.json'
        gate = json.loads(path.read_text())
        shadow = f'docs/validation/shadow/{fixtures.DATE}/test.json'
        (root / shadow).parent.mkdir(parents=True)
        (root / shadow).write_text(json.dumps({'artifact_id': 'test-shadow'}))
        gate['shadow_items'] = [{'item_id': 'test-shadow', 'state': 'COMPLETE',
                                 'kpi_eligibility': 'INELIGIBLE',
                                 'evidence_ref': {'artifact_path': shadow, 'artifact_id': 'test-shadow'}}]
        path.write_text(json.dumps(gate))
        r = self.prediction(root, prediction, digest)
        self.assertTrue(r['complete'])
        self.assertTrue(r['checks']['shadow']['result'])
        (root / shadow).unlink()
        r = self.prediction(root, prediction, digest)
        self.assertFalse(r['complete'])
        self.assertEqual(r['missing'], ['shadow'])

    def test_missing_shadow_scope_cannot_be_assumed_not_applicable(self):
        root, prediction, digest, _, _, _ = self.fixture()
        path = root / f'docs/validation/execution-gates/{fixtures.DATE}/{fixtures.RACE}.json'
        gate = json.loads(path.read_text())
        del gate['shadow_items']
        path.write_text(json.dumps(gate))
        r = self.prediction(root, prediction, digest)
        self.assertTrue(r['checks']['execution_gate']['result'])
        self.assertFalse(r['checks']['shadow']['result'])
        self.assertFalse(r['complete'])

    def test_body_absence_with_successful_audit_cannot_complete(self):
        root, prediction, digest, _, _, _ = self.fixture()
        (root / f'docs/validation/snapshots/{fixtures.DATE}/{prediction["snapshot_id"]}.json').unlink()
        r = self.prediction(root, prediction, digest, audit_succeeded=True)
        self.assertFalse(r['checks']['artifact']['result'])
        self.assertFalse(r['complete'])
        self.assertIsNone(r['persistence'])

    def test_invalid_json_shape_is_reported_as_body_failure(self):
        root, prediction, digest, _, _, _ = self.fixture()
        path = root / f'docs/validation/snapshots/{fixtures.DATE}/{prediction["snapshot_id"]}.json'
        path.write_text('[]')
        r = self.prediction(root, prediction, digest)
        self.assertFalse(r['checks']['artifact']['result'])
        self.assertFalse(r['complete'])
        self.assertIn('不足', render_completion(r))

    def test_missing_recommendation_does_not_block_prediction(self):
        root, prediction, digest, rec_gate, rec_path, rec_hash = self.fixture()
        (root / rec_path).unlink()
        self.assertTrue(self.prediction(root, prediction, digest)['complete'])
        r = recommendation_completion(root, rec_path, rec_gate, fixed_content_sha256=rec_hash)
        self.assertFalse(r['complete'])
        self.assertFalse(r['checks']['artifact']['result'])

    def test_recommendation_without_fix_hash_is_not_individually_complete(self):
        root, _, _, rec_gate, rec_path, _ = self.fixture()
        r = recommendation_completion(root, rec_path, rec_gate, audit_succeeded=True)
        self.assertTrue(r['checks']['artifact']['result'])
        self.assertTrue(r['checks']['receipt']['result'])
        self.assertTrue(r['checks']['execution_gate']['result'])
        self.assertIsNone(r['checks']['individual_check']['result'])
        self.assertFalse(r['complete'])

    def test_complete_recommendation_does_not_inherit_prediction_shadow(self):
        root, _, _, rec_gate, rec_path, digest = self.fixture(pending_shadow=True)
        before = {str(p): p.read_bytes() for p in root.rglob('*') if p.is_file()}
        r = recommendation_completion(root, rec_path, rec_gate, fixed_content_sha256=digest)
        self.assertTrue(r['complete'])
        self.assertEqual(r['checks']['shadow']['result'], 'NOT_APPLICABLE')
        self.assertEqual(before, {str(p): p.read_bytes() for p in root.rglob('*') if p.is_file()})
        self.assertFalse(r['eligibility_promoted'])

    def test_recommendation_gate_missing_still_reports_body_and_receipt(self):
        root, _, _, rec_gate, rec_path, digest = self.fixture()
        (root / rec_gate).unlink()
        r = recommendation_completion(root, rec_path, rec_gate, fixed_content_sha256=digest)
        self.assertTrue(r['checks']['artifact']['result'])
        self.assertTrue(r['checks']['receipt']['result'])
        self.assertFalse(r['checks']['execution_gate']['result'])
        self.assertFalse(r['complete'])

    def test_user_output_omits_internal_diagnostics(self):
        root, prediction, _, _, _, _ = self.fixture()
        r = self.prediction(root, prediction, '0' * 64)
        text = render_completion(r)
        self.assertNotIn('FIX/readback', text)
        self.assertNotIn(prediction['snapshot_id'], text)
        self.assertIn('原因：', text)
        self.assertIn('次の確認：', text)

    def test_both_existing_clis_expose_independent_status_and_failure_exit(self):
        root, prediction, digest, rec_gate, rec_path, rec_hash = self.fixture()
        argv = ['verify_prediction_persistence.py', '--root', str(root), '--date', fixtures.DATE,
                '--snapshot-id', prediction['snapshot_id'], '--completion-status', '--intent-id', 'first',
                '--fixed-content-sha256', digest]
        with patch.object(sys, 'argv', argv), redirect_stdout(io.StringIO()):
            self.assertEqual(prediction_main(), 0)
        argv = ['recommendation.py', '--root', str(root), '--verify', rec_gate, '--completion-status',
                '--completion-artifact-path', rec_path]
        with patch.object(sys, 'argv', argv), redirect_stdout(io.StringIO()):
            self.assertEqual(recommendation_main(), 1)
        with patch.object(sys, 'argv', argv + ['--fixed-content-sha256', rec_hash, '--status-json']), redirect_stdout(io.StringIO()) as out:
            self.assertEqual(recommendation_main(), 0)
            self.assertTrue(json.loads(out.getvalue())['complete'])

    def test_automated_legacy_caller_explicitly_selects_machine_log(self):
        root, prediction, _, _, _, _ = self.fixture()
        argv = ['verify_prediction_persistence.py', '--root', str(root), '--date', fixtures.DATE,
                '--snapshot-id', prediction['snapshot_id']]
        with patch.object(sys, 'argv', argv), redirect_stdout(io.StringIO()) as out:
            self.assertEqual(prediction_main(), 0)
            self.assertNotIn('PERSISTENCE_VERIFIED', out.getvalue())
        with patch.object(sys, 'argv', argv + ['--machine-log']), redirect_stdout(io.StringIO()) as out:
            self.assertEqual(prediction_main(), 0)
            self.assertIn('PERSISTENCE_VERIFIED ', out.getvalue())

    def test_historical_audit_keeps_absence_check_with_both_lookup_protocols(self):
        from audit_20261012_pr78 import require_audit_markers
        rest = '\n20261012-REMAINING-S01\n20261012-TOK-11-WEIGHT-S01: verified pre-race receipt missing'
        for missing in ('20261012-WHOLE-S01: expected one snapshot section, found 0',
                        '20261012-WHOLE-S01: snapshot file missing: docs/validation/snapshots/2026-10-12.md'):
            require_audit_markers(missing + rest)
        for other in ('PERSISTENCE_VERIFIED 20261012-WHOLE-S01',
                      'other-snapshot: snapshot file missing: file.md'):
            with self.subTest(other=other), self.assertRaises(AssertionError):
                require_audit_markers(other + rest)


if __name__ == '__main__':
    unittest.main()
