"""拒否、原本不変、commit固定読戻し、競合と冪等性の合成試験。"""
import hashlib
import json
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

    def write(self, branch, path, body, expected_blob_sha, *,
              append_receipt=False, previous_body=None):
        if append_receipt:
            if self.content != previous_body or expected_blob_sha != "b" * 40:
                raise PersistenceError("CAS preimage changed", kind="conflict")
        if self.failures:
            error = self.failures.pop(0)
            if error:
                raise error
        self.writes.append((body, expected_blob_sha))
        self.content = body
        return dict(branch=branch, path=path, commit_sha=SHA)


class PersistenceTest(unittest.TestCase):
    def setUp(self):
        self.race_id = "2026-10-18-TOKYO-11"
        self.date = "2026-10-18"
        self.post = "2026-10-18T15:15:00+09:00"
        self.name = "20261018-TOKYO-11-FINAL-S01"
        self.snapshot_path = "docs/validation/snapshots/2026-10-18/" + self.name + ".json"
        self.payload = self.fixed(self.snapshot_path, {
            "schema_version": "prediction-snapshot-v2",
            "snapshot_id": self.name, "race_id": self.race_id,
            "race_date_jst": self.date, "working_branch": "prediction/" + self.date,
            "scheduled_post_time_jst": self.post})
        self.clock = lambda stage: {
            "status": "PRE_SCHEDULED", "remaining_seconds": 30,
            "race_id": self.race_id, "race_date": self.date,
            "scheduled_post_jst": self.post,
            "official_source": "cycle04_official_schedule_chain"}

    def fixed(self, path, data):
        return FixedPayload("eda-hub/horse-man", "prediction/2026-10-18", path,
                            (json.dumps(data, ensure_ascii=False) + "\n").encode("utf-8"))

    def evidence_chain(self):
        """正式推奨の各固定原本。全パスを独立した新規保存として検証する。"""
        p = "docs/validation/"
        date, race, name = self.date, self.race_id, self.name
        rec_id = "20261018-TOKYO-11-REC-S01"
        rec_path = p + "recommendations/" + date + "/" + rec_id + ".json"
        intent_path = p + "recommendation-intents/" + date + "/tokyo-11-final.json"
        pred_ref = {"artifact_path": self.snapshot_path, "artifact_id": name,
                    "sha256": "a" * 64}
        def row(path, content):
            return (path, (json.dumps(content, ensure_ascii=False) + "\n").encode())
        return [
            row(p + "persistence-intents/" + date + "/tokyo-11-final.json", {
                "schema_version": "prediction-persistence-intent-v1",
                "race_date_jst": date, "working_branch": "prediction/" + date,
                "snapshot_id": name, "required_race_ids": [race],
                "artifact_path": self.snapshot_path, "deadline_jst": self.post}),
            (self.snapshot_path, self.payload.body),
            row(p + "fix-manifests/" + date + "/" + name + ".json", {
                "schema_version": "prediction-fix-manifest-v1",
                "snapshot_id": name, "artifact_path": self.snapshot_path,
                "fixed_content_sha256": self.payload.digest}),
            row(intent_path, {
                "schema_version": "recommendation-persistence-intent-v1",
                "race_date_jst": date, "race_id": race,
                "recommendation_id": rec_id, "artifact_path": rec_path,
                "prediction_ref": pred_ref, "deadline_jst": self.post}),
            row(rec_path, {
                "schema_version": "recommendation-snapshot-v1",
                "race_id": race, "race_date_jst": date, "recommendation_id": rec_id,
                "working_branch": "prediction/" + date,
                "scheduled_post_time_jst": self.post, "prediction_ref": pred_ref}),
            row(p + "recommendation-prediction-gates/" + date + "/" + rec_id + ".json", {
                "schema_version": "prediction-compliance-v2",
                "race_id": race, "race_date_jst": date,
                "working_branch": "prediction/" + date,
                "scheduled_post_time_jst": self.post}),
            (p + "persistence-receipts/" + date + "-tokyo-11-final.md",
             ('```persistence-receipt-v1\n' + json.dumps({
                 "receipt_id": rec_id + "-R01", "artifact_id": rec_id,
                 "race_id": race, "artifact_path": rec_path,
                 "scheduled_post_time_jst": self.post}) + '\n```\n').encode()),
            row(p + "recommendation-gates/" + date + "/" + race + ".json", {
                "schema_version": "recommendation-compliance-v1",
                "race_id": race, "race_date_jst": date, "recommendation_id": rec_id,
                "intent_path": intent_path, "prediction_ref": pred_ref,
                "evidence_ref": {"artifact_path": rec_path}}),
        ]

    def test_full_recommendation_chain_persists_and_readbacks(self):
        stored_paths = []
        for path, raw in self.evidence_chain():
            with self.subTest(path=path):
                transport = MemoryGitHub()
                payload = FixedPayload(self.payload.repository, self.payload.branch, path, raw)
                result = persist_fixed(payload, transport, self.clock,
                                       operation_id=path, race_id=self.race_id)
                self.assertEqual(result.write_state, "WRITTEN")
                self.assertEqual(result.readback_state, "MATCH")
                self.assertEqual(transport.writes, [(raw, None)])
                stored_paths.append(path)
        self.assertEqual(len(stored_paths), 8)
        self.assertTrue(any("recommendation-intents/" in p for p in stored_paths))
        self.assertTrue(any("recommendation-gates/" in p for p in stored_paths))

    def test_11r_payload_with_12r_clock_is_never_written(self):
        transport = MemoryGitHub()
        wrong_clock = lambda stage: dict(self.clock(stage), race_id="2026-10-18-TOKYO-12")
        result = persist_fixed(self.payload, transport, wrong_clock,
                               operation_id="wrong-clock", race_id=self.race_id)
        self.assertEqual(result.timing_state, "UNDETERMINED")
        self.assertEqual(transport.writes, [])

    def test_11r_payload_with_12r_command_is_rejected_before_remote_access(self):
        transport = MemoryGitHub()
        with self.assertRaisesRegex(ValueError, "race"):
            persist_fixed(self.payload, transport, self.clock,
                          operation_id="wrong-race", race_id="2026-10-18-TOKYO-12")
        self.assertEqual(transport.writes, [])

    def test_date_post_path_and_referenced_race_mismatch_are_rejected(self):
        cases = [
            (self.snapshot_path.replace("2026-10-18", "2026-10-17"),
             json.loads(self.payload.body), "date"),
            (self.snapshot_path.replace("TOKYO-11", "TOKYO-12"),
             json.loads(self.payload.body), "race"),
            (self.snapshot_path,
             dict(json.loads(self.payload.body), race_date_jst="2026-10-17"), "date"),
            (self.snapshot_path,
             dict(json.loads(self.payload.body), race_id="2026-10-18-TOKYO-12"), "race"),
            (self.snapshot_path,
             dict(json.loads(self.payload.body),
                  scheduled_post_time_jst="2026-10-18T15:25:00+09:00"), "post"),
        ]
        for path, obj, kind in cases:
            with self.subTest(kind=kind, path=path):
                transport = MemoryGitHub()
                payload = self.fixed(path, obj)
                if kind == "post":
                    result = persist_fixed(payload, transport, self.clock,
                                           operation_id="wrong-post", race_id=self.race_id)
                    self.assertEqual(result.timing_state, "UNDETERMINED")
                else:
                    with self.assertRaises(ValueError):
                        persist_fixed(payload, transport, self.clock,
                                      operation_id="mismatch", race_id=self.race_id)
                self.assertEqual(transport.writes, [])

    def test_multi_race_intent_cannot_use_later_race_deadline(self):
        path = "docs/validation/persistence-intents/2026-10-18/morning.json"
        obj = {"schema_version": "prediction-persistence-intent-v1",
               "race_date_jst": self.date, "working_branch": "prediction/" + self.date,
               "snapshot_id": "20261018-MORNING-S01",
               "artifact_path": "docs/validation/snapshots/2026-10-18.md",
               "required_race_ids": [self.race_id, "2026-10-18-TOKYO-12"],
               "deadline_jst": self.post}
        payload = self.fixed(path, obj)
        transport = MemoryGitHub()
        result = persist_fixed(payload, transport, self.clock, operation_id="morning",
                               race_id=self.race_id)
        self.assertEqual(result.readback_state, "MATCH")
        self.assertEqual(len(transport.writes), 1)
        wrong_clock = lambda stage: dict(self.clock(stage),
                                         race_id="2026-10-18-TOKYO-12",
                                         scheduled_post_jst="2026-10-18T15:30:00+09:00")
        other_transport = MemoryGitHub()
        late = persist_fixed(payload, other_transport, wrong_clock,
                             operation_id="morning-later", race_id="2026-10-18-TOKYO-12")
        self.assertEqual(late.timing_state, "UNDETERMINED")
        self.assertEqual(other_transport.writes, [])

    def test_prediction_and_recommendation_id_must_match_target_basename(self):
        for path, raw in self.evidence_chain():
            if "/snapshots/" in path or "/recommendations/" in path or "/fix-manifests/" in path:
                with self.subTest(path=path):
                    changed = path.replace(".json", "-new.json")
                    transport = MemoryGitHub()
                    with self.assertRaisesRegex(ValueError, "ID differs"):
                        persist_fixed(FixedPayload(self.payload.repository,
                                                  self.payload.branch, changed, raw),
                                      transport, self.clock,
                                      operation_id="different-file", race_id=self.race_id)
                    self.assertEqual(transport.writes, [])

    def test_reference_to_another_race_is_rejected_before_write(self):
        intent_path, raw = self.evidence_chain()[3]
        obj = json.loads(raw)
        obj["prediction_ref"]["artifact_path"] = obj["prediction_ref"]["artifact_path"].replace(
            "TOKYO-11", "TOKYO-12")
        transport = MemoryGitHub()
        with self.assertRaisesRegex(ValueError, "reference race"):
            persist_fixed(self.fixed(intent_path, obj), transport, self.clock,
                          operation_id="wrong-prediction-ref", race_id=self.race_id)
        self.assertEqual(transport.writes, [])

    def test_recommendation_gate_other_date_or_venue_is_not_approved(self):
        gate_path, raw = self.evidence_chain()[-1]
        for path in (gate_path.replace("2026-10-18", "2026-10-17"),
                     gate_path.replace("TOKYO-11", "KYOTO-11"),
                     "docs/validation/recommendation-gates/not-date/" + self.race_id + ".json",
                     "docs/validation/recommendation-gates/2026-10-18/../../x.json"):
            with self.subTest(path=path):
                with self.assertRaises(ValueError):
                    persist_fixed(FixedPayload(self.payload.repository,
                                               self.payload.branch, path, raw),
                                  MemoryGitHub(), self.clock,
                                  operation_id="unsafe-gate", race_id=self.race_id)

    def test_cli_rejects_mismatched_race_before_initializing_github(self):
        from contextlib import redirect_stdout
        from io import StringIO
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from unittest.mock import patch
        from prediction_persistence_io import main
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "fixed.json"
            path.write_bytes(self.payload.body)
            with patch.dict("os.environ", {"GITHUB_TOKEN": "test-token"}), \
                 patch("prediction_persistence_io.GitHubContentsTransport") as github, \
                 redirect_stdout(StringIO()) as out:
                result = main(["--date", self.date,
                               "--race-id", "2026-10-18-TOKYO-12",
                               "--path", self.snapshot_path, "--payload-file", str(path),
                               "--operation-id", "wrong-race", "--write"])
            self.assertEqual(result, 1)
            github.assert_not_called()
            self.assertIn("race", out.getvalue())

    def test_existing_short_race_id_is_accepted(self):
        from prediction_persistence_io import verify_payload_binding
        legacy = "20261018-TOK-11"
        info = verify_payload_binding(self.payload, legacy)
        self.assertEqual(info["race_date"], self.date)
        result = persist_fixed(self.payload, MemoryGitHub(), self.clock,
                               operation_id="existing-id", race_id=legacy)
        self.assertEqual(result.readback_state, "MATCH")
        for venue, expected in (("KYO", "KYOTO"), ("NII", "NIIGATA")):
            with self.subTest(venue=venue):
                from prediction_persistence_io import _race_parts
                self.assertEqual(_race_parts("20261018-" + venue + "-11", self.date)[0],
                                 expected)

    def test_legacy_id_resolves_the_registered_official_scope_key(self):
        from pathlib import Path
        from unittest.mock import patch
        from prediction_persistence_io import resolve_official_race_key
        official = "2026-10-18-TOKYO-11"
        with patch("cycle04_schedule_change.registered_row",
                   side_effect=lambda root, race, date: {} if race == official else None):
            self.assertEqual(resolve_official_race_key(Path("."), self.date,
                             "20261018-TOK-11"), official)
        with patch("cycle04_schedule_change.registered_row",
                   side_effect=lambda root, race, date: {} if race in
                   {"20261018-TOK-11", official} else None):
            with self.assertRaisesRegex(ValueError, "multiple official scope"):
                resolve_official_race_key(Path("."), self.date, "20261018-TOK-11")
        with patch("cycle04_schedule_change.registered_row", return_value=None):
            self.assertEqual(resolve_official_race_key(Path("."), self.date,
                             "20261018-TOK-11"), "20261018-TOK-11")

    def test_short_id_rejects_other_race_and_date(self):
        from prediction_persistence_io import verify_payload_binding
        for short in ("20261018-TOK-12", "20261017-TOK-11",
                      "20261018-KYO-11", "20261018-NII-11"):
            with self.subTest(short=short), self.assertRaises(ValueError):
                verify_payload_binding(self.payload, short)

    def shared_receipts(self):
        path = "docs/validation/persistence-receipts/" + self.date + ".md"
        recid = "20261018-TOKYO-11-REC-S01"
        recpath = "docs/validation/recommendations/" + self.date + "/" + recid + ".json"
        def record(id, *, race=None, artifact=None, previous=None, verified=False):
            result = {"receipt_id": id, "artifact_id": artifact or recid,
                      "race_id": race or self.race_id,
                      "artifact_path": recpath,
                      "scheduled_post_time_jst": self.post,
                      "content_sha256": "e" * 64,
                      "artifact_persist_status": "PERSIST_VERIFIED",
                      "receipt_persist_status": ("RECEIPT_VERIFIED" if verified
                                                 else "RECEIPT_READBACK_PENDING"),
                      "timing_eligibility": "PRE_RACE_ELIGIBLE",
                      "persist_verified_at_jst": "2026-10-18T15:11:00+09:00"}
            if previous:
                result["previous_receipt_ref"] = previous
                result["receipt_verified_at_jst"] = "2026-10-18T15:12:00+09:00"
            return result
        def block(r):
            return ("\n\n```persistence-receipt-v1\n" +
                    json.dumps(r, ensure_ascii=False, indent=2) + "\n```\n").encode()
        other = record("20261018-TOKYO-10-S01-R01",
                       race="2026-10-18-TOKYO-10", artifact="20261018-TOKYO-10-S01")
        old = record(recid + "-R01")
        new = record(recid + "-R02", previous=recid + "-R01", verified=True)
        prefix = b"# shared daily receipt\n" + block(other) + block(old)
        return path, prefix, prefix + block(new), recid

    def test_shared_receipt_r02_append_preserves_original_bytes(self):
        path, old, candidate, recid = self.shared_receipts()
        payload = FixedPayload(self.payload.repository, self.payload.branch, path, candidate)
        transport = MemoryGitHub(initial=old)
        result = persist_fixed(payload, transport, self.clock,
                               operation_id="r02", race_id="20261018-TOK-11",
                               append_receipt=True)
        self.assertEqual(result.readback_state, "MATCH")
        self.assertEqual(result.write_state, "WRITTEN")
        self.assertEqual(transport.content, candidate)
        self.assertTrue(transport.content.startswith(old))
        self.assertEqual(transport.writes, [(candidate, "b" * 40)])
        # recommendation.py --sealが参照するのと同じ日次共有receipt形式。
        from prediction_persistence_io import _json_or_receipt
        records = _json_or_receipt(payload, "persistence-receipts")
        self.assertEqual(sum(r["receipt_id"] == recid + "-R02" for r in records), 1)
        self.assertEqual(records[-1]["receipt_persist_status"], "RECEIPT_VERIFIED")
        again = persist_fixed(payload, transport, self.clock,
                              operation_id="r02-again", race_id=self.race_id,
                              append_receipt=True)
        self.assertEqual(again.write_state, "ALREADY_PRESENT")
        self.assertEqual(len(transport.writes), 1)

    def test_receipt_append_rejects_rewrite_duplicate_and_wrong_previous(self):
        path, old, candidate, recid = self.shared_receipts()
        original = self.payload
        cases = [candidate.replace(b"# shared daily receipt", b"# modified history"),
                 old + candidate[len(old):] + candidate[len(old):],
                 candidate.replace((recid + "-R01").encode(),
                                   b"NO-EXISTING-RECEIPT")]
        for data in cases:
            with self.subTest(length=len(data)):
                transport = MemoryGitHub(initial=old)
                result = persist_fixed(FixedPayload(original.repository, original.branch,
                                                  path, data),
                                       transport, self.clock, race_id=self.race_id,
                                       operation_id="append-invalid", append_receipt=True)
                self.assertEqual(result.failure_category, "conflict")
                self.assertEqual(transport.content, old)
                self.assertEqual(transport.writes, [])
        no_flag = persist_fixed(FixedPayload(original.repository, original.branch,
                                            path, candidate), MemoryGitHub(initial=old),
                                self.clock, race_id=self.race_id, operation_id="no-append")
        self.assertEqual(no_flag.failure_category, "conflict")

    def test_restored_incident_from_generator_is_storable_after_post(self):
        from prediction_persistence_io import verify_payload_binding
        import datetime
        failure = PersistenceError("refused", kind="safety_refusal", api_reached=False)
        transport = MemoryGitHub(failures=[failure])
        prior = persist_fixed(self.payload, transport, self.clock, operation_id="failed",
                              race_id="20261018-TOK-11")
        self.assertEqual(prior.failure_category, "safety_refusal")
        data = incident_record(self.payload, prior, observed_at="2026-10-18T16:00:00+09:00")
        path = "docs/validation/persistence-incidents/" + self.date + "/tokyo-11-failed.json"
        payload = self.fixed(path, data)
        verify_payload_binding(payload, "20261018-TOK-11")
        late_clock = lambda stage: dict(self.clock(stage), status="SCHEDULE_REACHED",
                                        remaining_seconds=-1800)
        saved = persist_fixed(payload, MemoryGitHub(), late_clock,
                              operation_id="incident-recovery",
                              race_id="20261018-TOK-11")
        self.assertEqual(saved.readback_state, "MATCH")
        self.assertEqual(saved.timing_state, "SCHEDULE_REACHED")
        self.assertFalse(saved.completion_verified)
        self.assertFalse(data["remote_persistence_certified"])

    def test_receipt_r02_modified_hash_or_time_is_rejected(self):
        path, old, candidate, _ = self.shared_receipts()
        target = FixedPayload(self.payload.repository, self.payload.branch, path, candidate)
        from prediction_persistence_io import _json_or_receipt
        original = _json_or_receipt(target, "persistence-receipts")[-1]
        for field_name, change in (("content_sha256", "d" * 64),
                                   ("receipt_verified_at_jst", "2026-10-18T15:30:00+09:00"),
                                   ("persist_verified_at_jst", "2026-10-18T15:10:00+09:00"),
                                   ("receipt_persist_status", "RECEIPT_READBACK_PENDING")):
            with self.subTest(field=field_name):
                changed = dict(original, **{field_name: change})
                prefix = candidate[:candidate.rfind(b"\n\n```persistence-receipt-v1")]
                raw = prefix + ("\n\n```persistence-receipt-v1\n" +
                                json.dumps(changed) + "\n```\n").encode()
                transport = MemoryGitHub(initial=old)
                result = persist_fixed(FixedPayload(self.payload.repository,
                                                    self.payload.branch, path, raw),
                                       transport, self.clock, operation_id=field_name,
                                       race_id=self.race_id, append_receipt=True)
                self.assertEqual(result.failure_category, "conflict")
                self.assertEqual(transport.writes, [])

    def test_cli_shared_receipt_append_uses_existing_sha(self):
        from contextlib import redirect_stdout
        from io import StringIO
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from unittest.mock import patch
        from prediction_persistence_io import main
        path, old, candidate, _ = self.shared_receipts()
        with TemporaryDirectory() as temporary:
            filepath = Path(temporary) / "whole-receipt.md"
            filepath.write_bytes(candidate)
            transport = MemoryGitHub(initial=old)
            with patch.dict("os.environ", {"GITHUB_TOKEN": "synthetic-token"}), \
                 patch("prediction_persistence_io.GitHubContentsTransport",
                       return_value=transport) as github, \
                 patch("prediction_clock.observed_assessment",
                       side_effect=lambda *a: self.clock("before_write")), \
                 patch("cycle04_schedule_change.registered_row", return_value=None), \
                 redirect_stdout(StringIO()):
                code = main(["--date", self.date, "--race-id", "20261018-TOK-11",
                             "--path", path, "--payload-file", str(filepath),
                             "--operation-id", "append-r02", "--append-receipt",
                             "--write"])
            self.assertEqual(code, 0)
            github.assert_called_once()
            self.assertEqual(transport.content, candidate)
            self.assertEqual(transport.writes[-1][1], "b" * 40)

    def test_cli_restored_incident_after_deadline_is_only_log_saved(self):
        from contextlib import redirect_stdout
        from io import StringIO
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from unittest.mock import patch
        from prediction_persistence_io import main
        failed = persist_fixed(self.payload, MemoryGitHub(failures=[
            PersistenceError("refused", kind="safety_refusal")]), self.clock,
            operation_id="failed-for-cli", race_id=self.race_id)
        record = incident_record(self.payload, failed)
        with TemporaryDirectory() as temporary:
            filepath = Path(temporary) / "incident.json"
            filepath.write_text(json.dumps(record) + "\n", encoding="utf-8")
            transport = MemoryGitHub()
            late = dict(self.clock("before_write"), status="SCHEDULE_REACHED",
                        remaining_seconds=-600)
            with patch.dict("os.environ", {"GITHUB_TOKEN": "synthetic-token"}), \
                 patch("prediction_persistence_io.GitHubContentsTransport",
                       return_value=transport), \
                 patch("prediction_clock.observed_assessment", return_value=late), \
                 patch("cycle04_schedule_change.registered_row", return_value=None), \
                 redirect_stdout(StringIO()) as output:
                code = main(["--date", self.date, "--race-id", "20261018-TOK-11",
                             "--path", "docs/validation/persistence-incidents/" +
                             self.date + "/tokyo-11-refusal.json",
                             "--payload-file", str(filepath),
                             "--operation-id", "incident-after-race", "--write"])
            self.assertEqual(code, 0)
            self.assertIn("障害記録のみ", output.getvalue())
            self.assertEqual(transport.content, filepath.read_bytes())
            self.assertIn("正式receiptの認証ではありません", output.getvalue())

    def test_direct_adapter_append_requires_verified_cas(self):
        from prediction_persistence_io import GitHubContentsTransport
        from unittest.mock import patch
        path, old, candidate, _ = self.shared_receipts()
        transport = GitHubContentsTransport.__new__(GitHubContentsTransport)
        transport.repository = self.payload.repository
        transport.branch = self.payload.branch
        transport._base = "https://api.github.com/repos/eda-hub/horse-man"
        with patch.object(transport, "read", return_value={
            "content": old, "blob_sha": "b" * 40, "commit_sha": SHA,
            "branch": transport.branch, "path": path}), patch.object(
                transport, "_call", return_value={"commit": {"sha": SHA}}) as call:
            result = transport.write(transport.branch, path, candidate, "b" * 40,
                                     append_receipt=True, previous_body=old)
            self.assertEqual(result["commit_sha"], SHA)
            self.assertEqual(call.call_args.args[0], "PUT")
            self.assertEqual(call.call_args.args[2]["sha"], "b" * 40)
        with patch.object(transport, "read", return_value={
            "content": old + b"x", "blob_sha": "c" * 40}), patch.object(
                transport, "_call") as call:
            with self.assertRaises(PersistenceError):
                transport.write(transport.branch, path, candidate, "b" * 40,
                                append_receipt=True, previous_body=old)
            call.assert_not_called()

    def test_new_file_write_and_exact_commit_readback(self):
        transport = MemoryGitHub()
        r = persist_fixed(self.payload, transport, self.clock, operation_id="R", race_id=self.race_id)
        self.assertEqual((r.write_state, r.readback_state, r.commit_sha),
                         ("WRITTEN", "MATCH", SHA))
        self.assertFalse(r.completion_verified)
        self.assertEqual(transport.writes[0][0], self.payload.body)

    def test_existing_exact_bytes_idempotent(self):
        transport = MemoryGitHub(initial=self.payload.body)
        r = persist_fixed(self.payload, transport, self.clock, operation_id="R", race_id=self.race_id)
        self.assertEqual(r.write_state, "ALREADY_PRESENT")
        self.assertEqual(r.readback_state, "MATCH")
        self.assertEqual(transport.writes, [])

    def test_different_existing_content_refuses_overwrite(self):
        transport = MemoryGitHub(initial=b"different")
        r = persist_fixed(self.payload, transport, self.clock, operation_id="R", race_id=self.race_id)
        self.assertEqual(r.failure_category, "conflict")
        self.assertEqual(transport.writes, [])

    def test_allow_update_never_overwrites_fixed_snapshot(self):
        transport = MemoryGitHub(initial=b"different")
        r = persist_fixed(self.payload, transport, self.clock, operation_id="R", race_id=self.race_id,
                          allow_update=True)
        self.assertEqual(r.failure_category, "conflict")
        self.assertEqual(r.readback_state, "NOT_ATTEMPTED")
        self.assertEqual(transport.content, b"different")
        self.assertEqual(transport.writes, [])

    def test_all_fixed_evidence_paths_reject_different_bytes(self):
        self.assertIsNotNone(self.payload.digest)
        for path, body in self.evidence_chain():
            with self.subTest(path=path):
                fixed = FixedPayload(self.payload.repository, self.payload.branch, path, body)
                transport = MemoryGitHub(initial=b"old")
                result = persist_fixed(fixed, transport, self.clock,
                                       operation_id="fixed", race_id=self.race_id,
                                       allow_update=True)
                self.assertEqual(result.failure_category, "conflict")
                self.assertEqual(transport.writes, [])
                self.assertEqual(transport.content, b"old")

    def test_safety_refusal_stops_without_other_route(self):
        error = PersistenceError("tool blocked: Bearer secretvalue",
                                 kind="safety_refusal", api_reached=False, tool="host")
        primary = MemoryGitHub(failures=[error])
        alternate = MemoryGitHub()
        r = persist_fixed(self.payload, primary, self.clock, operation_id="R", race_id=self.race_id,
                          alternative=alternate, alternative_authorized=True)
        self.assertEqual(r.failure_category, "safety_refusal")
        self.assertEqual(r.write_state, "NOT_ATTEMPTED")
        self.assertEqual(primary.writes, [])
        self.assertEqual(alternate.writes, [])
        self.assertFalse(r.retry_allowed)
        self.assertNotIn("secretvalue", str(incident_record(self.payload, r)))

    def test_transient_retry_preserves_bytes(self):
        primary = MemoryGitHub(failures=[PersistenceError("timeout", kind="timeout", api_reached=None)])
        r = persist_fixed(self.payload, primary, self.clock, operation_id="R", race_id=self.race_id)
        self.assertEqual(r.readback_state, "MATCH")
        self.assertEqual(primary.writes, [(self.payload.body, None)])

    def test_independent_route_only_for_allowed_transient(self):
        primary = MemoryGitHub(failures=[PersistenceError("temporary", kind="transport")])
        alternate = MemoryGitHub()
        r = persist_fixed(self.payload, primary, self.clock, operation_id="R", race_id=self.race_id,
                          alternative=alternate, alternative_authorized=True)
        self.assertEqual(r.readback_state, "MATCH")
        self.assertEqual(alternate.content, self.payload.body)

    def test_timeout_after_write_reconciled_without_duplicate(self):
        class TimeoutAfterWrite(MemoryGitHub):
            def write(self, branch, path, body, expected_blob_sha):
                super().write(branch, path, body, expected_blob_sha)
                raise PersistenceError("timed out after commit", kind="timeout")
        transport = TimeoutAfterWrite()
        r = persist_fixed(self.payload, transport, self.clock, operation_id="R", race_id=self.race_id)
        self.assertEqual(r.write_state, "ALREADY_PRESENT")
        self.assertEqual(len(transport.writes), 1)
        self.assertIsNone(r.failure_category)
        self.assertFalse(r.retry_allowed)

    def test_no_write_at_or_after_or_unknown_deadline(self):
        for status in ("SCHEDULE_REACHED", "UNDETERMINED"):
            transport = MemoryGitHub()
            r = persist_fixed(self.payload, transport,
                              lambda stage: dict(self.clock(stage), status=status),
                              operation_id="R", race_id=self.race_id)
            self.assertEqual(r.timing_state, status)
            self.assertEqual(transport.writes, [])

    def test_wrong_commit_contents_not_completed(self):
        transport = MemoryGitHub(mismatched=True)
        r = persist_fixed(self.payload, transport, self.clock, operation_id="R", race_id=self.race_id)
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
        self.assertEqual(classify_failure(kind="branch_policy",http_status=403,api_reached=True), "branch_policy")

    def test_readback_missing_at_fixed_commit_is_reported(self):
        class MissingAtCommit(MemoryGitHub):
            def read(self, branch, path, ref=None):
                if ref is not None:
                    raise FileNotFoundError(path)
                return super().read(branch, path, ref)
        transport = MissingAtCommit()
        result = persist_fixed(self.payload, transport, self.clock, operation_id="R", race_id=self.race_id)
        self.assertEqual(result.write_state, "WRITTEN")
        self.assertNotEqual(result.readback_state, "MATCH")
        self.assertEqual(result.failure_category, "unknown")

    def test_clock_error_before_write_is_undetermined(self):
        transport = MemoryGitHub()
        def clock(stage):
            raise ValueError("clock source unavailable")
        result = persist_fixed(self.payload, transport, clock, operation_id="R", race_id=self.race_id)
        self.assertEqual(result.timing_state, "UNDETERMINED")
        self.assertEqual(transport.writes, [])

    def test_clock_error_after_readback_preserves_bytes_without_eligibility(self):
        transport = MemoryGitHub()
        def clock(stage):
            if stage == "readback":
                raise ValueError("clock lost")
            return dict(self.clock(stage), remaining_seconds=20)
        result = persist_fixed(self.payload, transport, clock, operation_id="R", race_id=self.race_id)
        self.assertEqual(result.write_state, "WRITTEN")
        self.assertEqual(result.readback_state, "MATCH")
        self.assertEqual(result.timing_state, "UNDETERMINED")
        self.assertFalse(result.completion_verified)

    def test_transport_requires_existing_date_branch(self):
        from unittest.mock import patch
        from prediction_persistence_io import GitHubContentsTransport
        with patch.object(GitHubContentsTransport, '_call', return_value={'commit': {'sha': SHA}}) as call:
            obj = GitHubContentsTransport('eda-hub/horse-man', 'prediction/2026-10-18', 'synthetic-not-a-secret')
            self.assertEqual(obj.branch, 'prediction/2026-10-18')
            self.assertIn('/branches/prediction%2F2026-10-18', call.call_args.args[1])
        with self.assertRaises(ValueError):
            GitHubContentsTransport('eda-hub/horse-man', 'main', 'token')

    def test_transport_direct_write_rejects_existing_blob_sha(self):
        from unittest.mock import patch
        from prediction_persistence_io import GitHubContentsTransport
        transport = GitHubContentsTransport.__new__(GitHubContentsTransport)
        transport.repository = self.payload.repository
        transport.branch = self.payload.branch
        with patch.object(transport, "_call") as github_api:
            with self.assertRaises(PersistenceError) as failure:
                transport.write(self.payload.branch, self.payload.path, b"new", "b" * 40)
            self.assertEqual(failure.exception.kind, "conflict")
            github_api.assert_not_called()

    def test_transport_exact_commit_ref(self):
        import base64
        from unittest.mock import patch
        from prediction_persistence_io import GitHubContentsTransport
        obj = GitHubContentsTransport.__new__(GitHubContentsTransport)
        obj.repository = 'eda-hub/horse-man'
        obj.branch = 'prediction/2026-10-18'
        obj._base = 'https://api.github.com/repos/eda-hub/horse-man'
        with patch.object(obj, '_call', return_value={'type':'file','encoding':'base64',
                          'content':base64.b64encode(self.payload.body).decode(),
                          'sha':'b'*40}) as call:
            r = obj.read(obj.branch,self.payload.path,SHA)
            self.assertEqual(r['content'],self.payload.body)
            self.assertEqual(r['commit_sha'],SHA)
            self.assertIn('ref='+SHA,call.call_args.args[1])

    def test_initialization_403_generates_local_incident(self):
        from contextlib import redirect_stdout
        from io import StringIO
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from unittest.mock import patch
        import json
        from prediction_persistence_io import main
        with TemporaryDirectory() as tmp:
            original = Path(tmp) / "fixed.json"
            record = Path(tmp) / "incident.json"
            original.write_bytes(self.payload.body)
            error = PersistenceError("branch denied Authorization: Bearer not-a-token",
                                     http_status=403, api_reached=True,
                                     request_id="req-branch-403", tool="github_contents_rest")
            with patch.dict("os.environ", {"GITHUB_TOKEN": "private-token"}), \
                 patch("prediction_persistence_io.GitHubContentsTransport", side_effect=error), \
                 redirect_stdout(StringIO()):
                code = main(["--date", "2026-10-18", "--race-id", "20261018-TOK-11",
                             "--path", self.payload.path, "--payload-file", str(original),
                             "--operation-id", "fixture", "--local-incident", str(record), "--write"])
            self.assertEqual(code, 1)
            incident = json.loads(record.read_text(encoding="utf-8"))
            self.assertEqual(incident["failure_category"], "authorization")
            self.assertFalse(incident["remote_persistence_certified"])
            self.assertEqual(incident["target"]["sha256"], self.payload.digest)
            event = incident["operations"][0]
            self.assertEqual(event["operation"], "transport_initialize")
            self.assertEqual(event["http_status"], 403)
            self.assertEqual(event["request_id"], "req-branch-403")
            self.assertEqual(event["api_reached"], True)
            self.assertNotIn("private-token", record.read_text(encoding="utf-8"))
            self.assertNotIn("not-a-token", record.read_text(encoding="utf-8"))

    def test_initialization_refusal_without_http_is_preserved(self):
        from contextlib import redirect_stdout
        from io import StringIO
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from unittest.mock import patch
        import json
        from prediction_persistence_io import main
        with TemporaryDirectory() as tmp:
            original = Path(tmp) / "fixed.json"
            incident_path = Path(tmp) / "incident.json"
            original.write_bytes(self.payload.body)
            blocked = PersistenceError("tool safety refusal", kind="safety_refusal",
                                       api_reached=False, request_id="policy-ref",
                                       tool="host-check")
            with patch.dict("os.environ", {"GITHUB_TOKEN": "test-token"}), \
                 patch("prediction_persistence_io.GitHubContentsTransport", side_effect=blocked), \
                 redirect_stdout(StringIO()):
                code = main(["--date", "2026-10-18", "--race-id", "20261018-TOK-11",
                             "--path", self.payload.path, "--payload-file", str(original),
                             "--operation-id", "blocked", "--local-incident", str(incident_path),
                             "--write"])
            self.assertEqual(code, 1)
            event = json.loads(incident_path.read_text(encoding="utf-8"))
            self.assertEqual(event["failure_category"], "safety_refusal")
            self.assertEqual(event["operations"][0]["request_id"], "policy-ref")
            self.assertFalse(event["retry_allowed"])

    def test_cli_allow_update_rejected_without_network_call(self):
        from contextlib import redirect_stdout
        from io import StringIO
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from unittest.mock import patch
        from prediction_persistence_io import main
        with TemporaryDirectory() as tmp:
            original = Path(tmp) / "fixed.json"
            original.write_bytes(self.payload.body)
            with patch.dict("os.environ", {"GITHUB_TOKEN": "test-token"}), \
                 patch("prediction_persistence_io.GitHubContentsTransport") as transport, \
                 redirect_stdout(StringIO()):
                status = main(["--date", "2026-10-18", "--race-id", "20261018-TOK-11",
                               "--path", self.payload.path, "--payload-file", str(original),
                               "--operation-id", "no-rewrite", "--allow-update", "--write"])
            self.assertEqual(status, 1)
            transport.assert_not_called()

    def test_redaction(self):
        self.assertNotIn("topsecret", sanitized("Authorization: Bearer topsecret"))
        self.assertNotIn("abcd123", sanitized("token=abcd123"))


if __name__ == "__main__":
    unittest.main()
