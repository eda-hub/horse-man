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

    def test_existing_verified_gate_survives_approved_demotion(self):
        # The old gate is a historical artifact, never rewritten to INELIGIBLE.
        from test_check_prediction_compliance import gate, receipt_record, write_receipts
        g = gate(date=DAY, race=RACE)
        g["kpi_eligibility"]["production"] = "ELIGIBLE"
        artifact = f"docs/validation/snapshots/{DAY}.md"
        receipt = f"docs/validation/persistence-receipts/{DAY}.md"
        aid, rid = RACE + "-P001-S01", RACE + "-R02"
        write(self.root, artifact, "snapshot_id: " + aid + "\n")
        write_receipts(self.root, receipt, [receipt_record(rid, aid, artifact)])
        g["production"]["evidence_ref"] = {
            "artifact_path": artifact, "artifact_id": aid,
            "receipt_path": receipt, "receipt_id": rid,
            "timing_eligibility": "PRE_RACE_ELIGIBLE",
            "persist_verified_at_jst": "2026-09-26T10:00:00+09:00"
        }
        gate_path = f"docs/validation/execution-gates/{DAY}/{RACE}.json"
        write(self.root, gate_path, json.dumps(g, ensure_ascii=False))
        with redirect_stdout(io.StringIO()):
            self.assertEqual(run(self.root), [])
        original_gate = (self.root / gate_path).read_bytes()

        self.install(self.correction(after="INELIGIBLE"))
        with redirect_stdout(io.StringIO()) as out:
            self.assertEqual(run(self.root), [])
        self.assertIn("HISTORICAL_EFFECTIVE_STATE", out.getvalue())
        self.assertEqual((self.root / gate_path).read_bytes(), original_gate)
        view = report(days_at(self.root), load(self.root, days_at(self.root)), root=self.root)
        self.assertEqual(view["corrected_claim_counts"][DAY]["production"]["INELIGIBLE"], 1)

        # An actual pre-existing discrepancy is still an error, not forgiven.
        g["kpi_eligibility"]["production"] = "PENDING"
        write(self.root, gate_path, json.dumps(g, ensure_ascii=False))
        with self.assertRaisesRegex(ComplianceError, "gate state mismatch"):
            run(self.root)

    def create_split_betting(self):
        from check_betting_performance import snapshot_tickets, tickets_hash
        race = RACE
        artifact = f"docs/validation/snapshots/{DAY}.md"
        source_path = f"docs/validation/betting-sources/{DAY}/source.json"
        original_path = f"docs/validation/betting-sources/{DAY}/original.json"
        aid = "fixed-01"
        write(self.root, artifact, (
            f"## 固定計画\nsnapshot_id: {aid}\n"
            "ticket_purpose: OFFICIAL_VIRTUAL\n"
            "### 検証用仮想購入（正式帳簿）\n"
            "- 馬連 1-2: 10,000円\n"))
        tickets = snapshot_tickets(self.root, artifact, aid)
        fixed_at = "2026-09-26T09:50:00+09:00"
        original_bytes = json.dumps({
            "race_id": race, "source_sent_at_jst": fixed_at,
            "tickets": tickets
        }, ensure_ascii=False).encode()
        target = self.root / original_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(original_bytes)
        ref = {
            "source_type": "GIT_PRE_RACE_SNAPSHOT",
            "source_ref": "https://github.com/eda-hub/horse-man/blob/" + "a" * 40 + "/" + artifact,
            "source_path": source_path,
            "working_branch": "prediction/" + DAY
        }
        source = {**ref, "schema_version": "fixed-plan-source-v1",
                  "race_id": race, "verification_status": "VERIFIED",
                  "source_sent_at_jst": fixed_at,
                  "scheduled_post_time_jst": "2026-09-26T10:10:00+09:00",
                  "result_checked_at_jst": "2026-09-26T11:00:00+09:00",
                  "original_path": original_path,
                  "original_sha256": hashlib.sha256(original_bytes).hexdigest(),
                  "snapshot_path": artifact, "snapshot_id": aid,
                  "tickets_sha256": tickets_hash(tickets),
                  "verified_by": "監査担当", "verification_note": "事前出所と買い目を確認"}
        write(self.root, source_path, json.dumps(source, ensure_ascii=False))
        day = copy.deepcopy(self.day)
        day["kpi_contract"] = "betting-kpi-split-v1"
        day["purchase_candidates"] = [race]
        day["kpis"]["betting"] = {
            "target_ids": [race], "eligible_ids": [race],
            "pending_ids": [], "ineligible_ids": [], "evidence_refs": {race: ref},
            "stake_yen": 10000, "return_yen": 16000
        }
        day["fixed_plan_settlement"] = {
            "stake_yen": 10000, "return_yen": 16000,
            "races": {race: {"snapshot_path": artifact, "snapshot_id": aid,
                             "stake_yen": 10000, "return_yen": 16000,
                             "source_verification": "VERIFIED"}}
        }
        return day, ref, source_path

    def test_formal_roi_requires_real_verified_source(self):
        day, ref, source_path = self.create_split_betting()
        valid = report({DAY: day}, {}, root=self.root)
        entry = valid["split_betting_performance"][DAY]
        self.assertEqual(entry["original_formal"]["roi_pct"], 160)
        self.assertIsNone(entry["original_formal"]["reason"])
        self.assertEqual(entry["fixed_settlement_reference"]["return_yen"], 16000)

        # A nonexistent provenance path is not a certified 160% result.
        ref["source_path"] = "docs/validation/betting-sources/missing.json"
        invalid = report({DAY: day}, {}, root=self.root)["split_betting_performance"][DAY]
        for view in ("original_formal", "corrected_formal"):
            self.assertIsNone(invalid[view]["roi_pct"])
            self.assertIsNone(invalid[view]["stake_yen"])
            self.assertIsNone(invalid[view]["return_yen"])
            self.assertIn("UNVERIFIED_SOURCE", invalid[view]["reason"])
        self.assertEqual(invalid["fixed_settlement_reference"], entry["fixed_settlement_reference"])

        # Existing but tampered provenance is equally untrusted.
        ref["source_path"] = source_path
        doc = json.loads((self.root / source_path).read_text(encoding="utf-8"))
        doc["original_sha256"] = "0" * 64
        write(self.root, source_path, json.dumps(doc, ensure_ascii=False))
        damaged = report({DAY: day}, {}, root=self.root)["split_betting_performance"][DAY]
        self.assertIsNone(damaged["original_formal"]["roi_pct"])
        self.assertIn("hash mismatch", damaged["original_formal"]["reason"])

    def test_formal_roi_after_demotion_and_unmatched_settlement(self):
        day, _, _ = self.create_split_betting()
        corrected = {(DAY, RACE, "betting"): {
            "original": "ELIGIBLE", "effective": "INELIGIBLE"}}
        item = report({DAY: day}, corrected, root=self.root)["split_betting_performance"][DAY]
        self.assertEqual(item["original_formal"]["roi_pct"], 160)
        self.assertIsNone(item["corrected_formal"]["roi_pct"])
        self.assertEqual(item["corrected_formal"]["reason"], "NO_ELIGIBLE_RACES")
        self.assertEqual(item["fixed_settlement_reference"]["stake_yen"], 10000)

        # Identical provenance, but a mismatched settlement identity,
        # must not produce a numeric formal ROI.
        day["fixed_plan_settlement"]["races"][RACE]["snapshot_id"] = "wrong-id"
        broken = report({DAY: day}, {}, root=self.root)["split_betting_performance"][DAY]
        self.assertIsNone(broken["original_formal"]["roi_pct"])
        self.assertIn("snapshot identity mismatch", broken["original_formal"]["reason"])

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
