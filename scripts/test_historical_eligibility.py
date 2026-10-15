"""過去の適格宣言を別記録で訂正しても、発走前証跡は生まれない。"""
import copy
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout

from check_prediction_compliance import ComplianceError, run
from historical_eligibility import CorrectionError, days_at, effective, load, report
from test_check_cycle03 import example, fenced

DAY = "2026-09-26"
RACE = "20260926-NAK-01"
FILE = f"docs/validation/records/{DAY}.md"
OVERLAY = "docs/validation/historical-corrections"
README = "# manual\n- **現行リリース**: " + chr(96) + "v1.6.1" + chr(96) + "\n"

def invoke(root, *args):
    env = dict(os.environ, GIT_AUTHOR_NAME="監査テスト", GIT_AUTHOR_EMAIL="test@example.invalid",
               GIT_COMMITTER_NAME="監査テスト", GIT_COMMITTER_EMAIL="test@example.invalid")
    return subprocess.check_output(["git", "-C", str(root), *args], env=env).decode().strip()

def write(root, path, content):
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target

class HistoricalEligibilityTests(unittest.TestCase):
    def setUp(self):
        work = tempfile.TemporaryDirectory()
        self.addCleanup(work.cleanup)
        self.root = Path(work.name)
        self.day = example(DAY, RACE)
        production = self.day["kpis"]["production"]
        production["eligible_ids"], production["pending_ids"] = [RACE], []
        production["evidence_refs"] = {RACE: {
            "snapshot_id": "historic-01", "receipt_id": "historic-r02",
            "working_branch": "prediction/" + DAY}}
        write(self.root, FILE, fenced("cycle03-day-v1", self.day))
        write(self.root, "docs/manual/README.md", README)
        invoke(self.root, "init", "-q")
        invoke(self.root, "add", FILE)
        invoke(self.root, "commit", "-qm", "当時の日別台帳を固定")
        self.original = {"path": FILE, "status": "ELIGIBLE",
                         "commit_sha": invoke(self.root, "rev-parse", "HEAD"),
                         "blob_sha": invoke(self.root, "rev-parse", f"HEAD:{FILE}")}

    def correction(self, **updates):
        obj = {
            "schema_version": "historical-eligibility-correction-v1",
            "correction_id": "original-r1",
            "race_date_jst": DAY, "race_id": RACE, "kpi": "production",
            "revision": 1, "previous_record_sha256": None,
            "original": copy.deepcopy(self.original),
            "before": "ELIGIBLE", "after": "PENDING",
            "reason": "当時のexecution gate原票が存在しないため判断保留",
            "basis": [{**{k:v for k,v in self.original.items() if k != "status"},
                       "role": "原台帳の適格宣言"}],
            "owner": "回顧担当", "reviewed_by": "監査確認者",
            "reviewed_at_jst": "2026-10-14T11:00:00+09:00",
            "affected_aggregates": ["cycle03:production"]
        }
        obj.update(updates)
        return obj

    def install(self, obj):
        return write(self.root, f"{OVERLAY}/{obj['correction_id']}.json",
                     json.dumps(obj, ensure_ascii=False, indent=2) + "\n")

    def test_unapproved_original_still_fails_normal_and_audit_only_reports(self):
        with self.assertRaisesRegex(ComplianceError, "lacks execution gate"):
            run(self.root)
        with redirect_stdout(io.StringIO()) as output:
            missing = run(self.root, audit=True)
        self.assertEqual(len(missing), 1)
        self.assertIn("ORIGINAL_DECLARATION_CONFLICT", output.getvalue())
        self.assertEqual(load(self.root, days_at(self.root)), {})

    def test_approved_demotion_keeps_original_independent(self):
        obj = self.correction()
        self.install(obj)
        corrections = load(self.root, days_at(self.root))
        self.assertEqual(effective(corrections, DAY, RACE, "production", "ELIGIBLE"), "PENDING")
        self.assertEqual(report(days_at(self.root), corrections)["original_claim_counts"][DAY]["production"]["ELIGIBLE"], 1)
        self.assertEqual(report(days_at(self.root), corrections)["corrected_claim_counts"][DAY]["production"]["ELIGIBLE"], 0)
        with redirect_stdout(io.StringIO()) as output:
            self.assertEqual(run(self.root), [])
        self.assertIn("ORIGINAL_DECLARATION_CONFLICT", output.getvalue())
        self.assertIn(RACE, (self.root / FILE).read_text(encoding="utf-8"))
        self.assertEqual(invoke(self.root, "rev-parse", f"HEAD:{FILE}"), self.original["blob_sha"])

    def test_demotion_does_not_whitelist_unrelated_races(self):
        other = "20260926-NAK-02"
        self.day["initial_scope"].append(other)
        self.day["unreviewed_scope"].append(other)
        production = self.day["kpis"]["production"]
        for key in ("target_ids", "eligible_ids"):
            production[key].append(other)
        production["evidence_refs"][other] = {"snapshot_id": "other", "receipt_id": "other-r02",
                                              "working_branch": "prediction/" + DAY}
        write(self.root, FILE, fenced("cycle03-day-v1", self.day))
        self.install(self.correction())
        # Original anchor is still valid for race 1; race 2 remains uncorrected.
        self.assertEqual(len(load(self.root, days_at(self.root))), 1)
        with self.assertRaisesRegex(ComplianceError, "lacks execution gate"):
            run(self.root)

    def test_existing_cycle_reference_settlement_remains_separate(self):
        repo = Path(__file__).resolve().parents[1]
        days = days_at(repo)
        view = report(days, load(repo, days))
        self.assertEqual(view["original_claim_counts"]["2026-09-26"]["production"]["ELIGIBLE"], 3)
        self.assertEqual(view["fixed_settlement_reference_total"],
                         {"stake_yen": 220000, "return_yen": 191750})
        self.assertIsNone(view["split_betting_performance"]["2026-09-27"]["original_formal"]["roi_pct"])

    def test_unlinked_legacy_gate_cannot_certify_different_ledger_id(self):
        from test_check_prediction_compliance import gate, receipt_record, write_receipts
        prod = self.day["kpis"]["production"]
        prod["eligible_ids"], prod["pending_ids"], prod["evidence_refs"] = [], [RACE], {}
        write(self.root, FILE, fenced("cycle03-day-v1", self.day))
        separate = "20260926-NAK-02"
        g = gate(date=DAY, race=separate)
        g["kpi_eligibility"]["production"] = "ELIGIBLE"
        artifact = "docs/validation/snapshots/2026-09-26.md"
        receipt = "docs/validation/persistence-receipts/2026-09-26.md"
        aid, rid = "20260926-NAK-02-S01", "20260926-NAK-02-R02"
        write(self.root, artifact, "snapshot_id: " + aid + "\n")
        write_receipts(self.root, receipt, [receipt_record(rid, aid, artifact)])
        g["production"]["evidence_ref"] = {
            "artifact_path": artifact, "artifact_id": aid, "receipt_path": receipt,
            "receipt_id": rid, "timing_eligibility": "PRE_RACE_ELIGIBLE",
            "persist_verified_at_jst": "2026-09-26T10:00:00+09:00"
        }
        write(self.root, f"docs/validation/execution-gates/{DAY}/{separate}.json",
              json.dumps(g, ensure_ascii=False))
        with self.assertRaisesRegex(ComplianceError, "UNLINKED_GATE_CLAIM"):
            run(self.root)

    def test_refused_cross_race_kpi_and_original_hash(self):
        for patch in ({"race_id": "20260926-NAK-99"},
                      {"kpi": "shadow", "affected_aggregates": ["cycle03:shadow"]},
                      {"original": {**self.original, "blob_sha": "a"*40}},
                      {"original": {**self.original, "commit_sha": "f"*40}}):
            with self.subTest(patch=patch):
                self.install(self.correction(**patch))
                with self.assertRaises(CorrectionError):
                    load(self.root, days_at(self.root))

    def test_no_empty_basis_future_approval_or_self_certification(self):
        future = "2999-01-01T00:00:00+09:00"
        for patch in ({"basis": []}, {"reviewed_at_jst": future},
                      {"after": "ELIGIBLE"}, {"reviewed_by": ""},
                      {"affected_aggregates": ["cycle03:betting"]},
                      {"basis": [{**self.original, "role": "wrong", "blob_sha": "b"*40}]}):
            with self.subTest(patch=patch):
                self.install(self.correction(**patch))
                with self.assertRaises(CorrectionError):
                    load(self.root, days_at(self.root))

    def test_revision_hash_and_rollback(self):
        first = self.correction()
        first_file = self.install(first)
        second = self.correction(correction_id="original-r2", revision=2,
                                 before="PENDING", after="INELIGIBLE",
                                 reviewed_at_jst="2026-10-15T09:00:00+09:00",
                                 previous_record_sha256=hashlib.sha256(first_file.read_bytes()).hexdigest())
        second_file = self.install(second)
        self.assertEqual(load(self.root, days_at(self.root))[(DAY, RACE, "production")]["effective"], "INELIGIBLE")
        second["previous_record_sha256"] = "0"*64
        self.install(second)
        with self.assertRaisesRegex(CorrectionError, "hash"):
            load(self.root, days_at(self.root))
        second["previous_record_sha256"] = hashlib.sha256(first_file.read_bytes()).hexdigest()
        second["before"] = "ELIGIBLE"
        self.install(second)
        with self.assertRaisesRegex(CorrectionError, "rollback"):
            load(self.root, days_at(self.root))
        second_file.unlink()
        branched = self.correction(correction_id="parallel-r1", after="INELIGIBLE")
        self.install(branched)
        with self.assertRaisesRegex(CorrectionError, "branch"):
            load(self.root, days_at(self.root))

if __name__ == "__main__":
    unittest.main()
