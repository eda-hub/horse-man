"""拒否、原本不変、commit固定読戻し、競合と冪等性の合成試験。"""
import hashlib
import unittest
from prediction_persistence_io import (
    FixedPayload, PersistenceError, classify_failure, incident_record,
    persist_fixed, sanitized,
)


SHA = "a" * 40


class MemoryGitHub:
    def __init__(self, *, initial=None, failures=None, mismatched=False):
        self.content = initial
        self.failures = list(failures or [])
        self.mismatched = mismatched
        self.writes = []
        self.path = "docs/validation/snapshots/2026-10-18/R.json"

    def read(self, branch, path, ref=None):
        if self.content is None:
            raise FileNotFoundError(path)
        return dict(branch=branch, path=path, content=(b"changed" if self.mismatched and ref else self.content),
                    blob_sha="b" * 40, commit_sha=SHA)

    def write(self, branch, path, body, expected_blob_sha):
        if self.failures:
            error = self.failures.pop(0)
            if error:
                raise error
        self.writes.append((body, expected_blob_sha))
        self.content = body
        return dict(branch=branch, path=path, commit_sha=SHA)


class PersistenceTest(unittest.TestCase):
    def setUp(self):
        self.payload = FixedPayload("eda-hub/horse-man", "prediction/2026-10-18",
                                    "docs/validation/snapshots/2026-10-18/R.json", b'{"fixed":true}\n')
        self.clock = lambda stage: {"status": "PRE_SCHEDULED", "remaining_seconds": 30}

    def test_new_file_write_and_exact_commit_readback(self):
        transport = MemoryGitHub()
        r = persist_fixed(self.payload, transport, self.clock, operation_id="R")
        self.assertEqual((r.write_state, r.readback_state, r.commit_sha),
                         ("WRITTEN", "MATCH", SHA))
        self.assertFalse(r.completion_verified)
        self.assertEqual(transport.writes[0][0], self.payload.body)

    def test_existing_exact_bytes_idempotent(self):
        transport = MemoryGitHub(initial=self.payload.body)
        r = persist_fixed(self.payload, transport, self.clock, operation_id="R")
        self.assertEqual(r.write_state, "ALREADY_PRESENT")
        self.assertEqual(r.readback_state, "MATCH")
        self.assertEqual(transport.writes, [])

    def test_different_existing_content_refuses_overwrite(self):
        transport = MemoryGitHub(initial=b"different")
        r = persist_fixed(self.payload, transport, self.clock, operation_id="R")
        self.assertEqual(r.failure_category, "conflict")
        self.assertEqual(transport.writes, [])

    def test_approved_update_with_sha(self):
        transport = MemoryGitHub(initial=b"different")
        r = persist_fixed(self.payload, transport, self.clock, operation_id="R",
                          allow_update=True)
        self.assertEqual(r.readback_state, "MATCH")
        self.assertEqual(transport.writes[0][1], "b" * 40)

    def test_safety_refusal_stops_without_other_route(self):
        error = PersistenceError("tool blocked: Bearer secretvalue",
                                 kind="safety_refusal", api_reached=False, tool="host")
        primary = MemoryGitHub(failures=[error])
        alternate = MemoryGitHub()
        r = persist_fixed(self.payload, primary, self.clock, operation_id="R",
                          alternative=alternate, alternative_authorized=True)
        self.assertEqual(r.failure_category, "safety_refusal")
        self.assertEqual(r.write_state, "NOT_ATTEMPTED")
        self.assertEqual(primary.writes, [])
        self.assertEqual(alternate.writes, [])
        self.assertFalse(r.retry_allowed)
        self.assertNotIn("secretvalue", str(incident_record(self.payload, r)))

    def test_transient_retry_preserves_bytes(self):
        primary = MemoryGitHub(failures=[PersistenceError("timeout", kind="timeout", api_reached=None)])
        r = persist_fixed(self.payload, primary, self.clock, operation_id="R")
        self.assertEqual(r.readback_state, "MATCH")
        self.assertEqual(primary.writes, [(self.payload.body, None)])

    def test_independent_route_only_for_allowed_transient(self):
        primary = MemoryGitHub(failures=[PersistenceError("temporary", kind="transport")])
        alternate = MemoryGitHub()
        r = persist_fixed(self.payload, primary, self.clock, operation_id="R",
                          alternative=alternate, alternative_authorized=True)
        self.assertEqual(r.readback_state, "MATCH")
        self.assertEqual(alternate.content, self.payload.body)

    def test_timeout_after_write_reconciled_without_duplicate(self):
        class TimeoutAfterWrite(MemoryGitHub):
            def write(self, branch, path, body, expected_blob_sha):
                super().write(branch, path, body, expected_blob_sha)
                raise PersistenceError("timed out after commit", kind="timeout")
        transport = TimeoutAfterWrite()
        r = persist_fixed(self.payload, transport, self.clock, operation_id="R")
        self.assertEqual(r.write_state, "ALREADY_PRESENT")
        self.assertEqual(len(transport.writes), 1)

    def test_no_write_at_or_after_or_unknown_deadline(self):
        for status in ("SCHEDULE_REACHED", "UNDETERMINED"):
            transport = MemoryGitHub()
            r = persist_fixed(self.payload, transport,
                              lambda stage: {"status": status},
                              operation_id="R")
            self.assertEqual(r.timing_state, status)
            self.assertEqual(transport.writes, [])

    def test_wrong_commit_contents_not_completed(self):
        transport = MemoryGitHub(mismatched=True)
        r = persist_fixed(self.payload, transport, self.clock, operation_id="R")
        self.assertEqual(r.failure_category, "conflict")
        self.assertNotEqual(r.readback_state, "MATCH")

    def test_wrong_scope_and_security(self):
        for branch, path in [
            ("main", self.payload.path), ("prediction/2026-10-18", "../x"),
            ("prediction/2026-10-18", "scripts/check_cycle04.py")]:
            with self.assertRaises(ValueError):
                FixedPayload("eda-hub/horse-man", branch, path, b"x")

    def test_http_error_not_misclassified_as_safety(self):
        self.assertEqual(classify_failure(http_status=403, api_reached=True), "authorization")
        self.assertEqual(classify_failure(http_status=409, api_reached=True), "conflict")
        self.assertEqual(classify_failure(http_status=500, api_reached=True), "server_unavailable")
        self.assertEqual(classify_failure(http_status=403, api_reached=False), "unknown")

    def test_redaction(self):
        self.assertNotIn("topsecret", sanitized("Authorization: Bearer topsecret"))
        self.assertNotIn("abcd123", sanitized("token=abcd123"))


if __name__ == "__main__":
    unittest.main()
