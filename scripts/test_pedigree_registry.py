"""血統調査台帳の受入回帰テスト。外部ネットワーク不要。"""
import datetime as dt
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pedigree_registry import Registry, RegistryError, file_blob_sha, hash_object, now


class PedigreeRegistryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "data" / "pedigree"
        self.reg = Registry(self.root)
        self.earlier = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=2)).isoformat()
        self.future = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=10)).isoformat()
        self.register("root001", "テスト馬", external="001")
        self.register("sire001", "父A", external="002")
        self.register("dam0001", "母A", external="003")
        self.register("damsire1", "母父A", external="004")

    def register(self, key, name, external=None, status="RESOLVED"):
        evidence = {"status": status, "names": [name], "birth_year": 2020,
                    "country": "JP", "external_ids": []}
        if external:
            evidence["external_ids"].append({"provider": "TEST", "id": external})
        if status == "RESOLVED":
            evidence.update(identity_evidence="出所との同定照合", identity_checked_at=self.earlier)
        return self.reg.register({"horse_key": key, "identity": evidence})

    def add(self, horse, field, value, source=None, verified=True, previous=None):
        token = source or horse + "." + field + "." + value
        claim = {
            "horse_key": horse, "field": field, "value": value,
            "verification": "VERIFIED" if verified else "UNVERIFIED",
            "first_observed_at": self.earlier, "captured_at": self.earlier,
            "source": {"provider_record_key": "TEST/" + token,
                       "source_class": "BREEDING_DB",
                       "origin_group": "TEST_MASTER",
                       "acquisition_method": "MANUAL_REVIEW",
                       "record_sha256": hashlib.sha256(token.encode()).hexdigest()}
        }
        if verified:
            claim["verification_evidence"] = {
                "checked_by": "test-fixture", "method": "元資料照合", "checked_at": self.earlier}
        if previous:
            claim["previous_revision_id"] = previous
            claim["correction_reason"] = "公式の訂正を確認"
        return self.reg.add_fact(claim, file_blob_sha(self.reg.path(horse)))

    def request(self, **kwargs):
        data = {"horse": {"horse_key": "root001"}, "data_cutoff": self.future, "mode": "FORWARD"}
        data.update(kwargs)
        return self.reg.query(data)

    def test_registration_readback_and_external_identity(self):
        self.assertEqual(self.reg.resolve({"provider": "TEST", "external_id": "001"})["horse_key"],
                         "root001")
        with self.assertRaises(RegistryError):
            self.register("other001", "別馬", external="001")
        self.assertEqual(self.reg.read_horse("root001")["revisions"], [])

    def test_missing_only_parent_research(self):
        self.add("root001", "parent.sire", "sire001")
        result = self.request(fields=["sire", "dam_sire"])
        self.assertEqual(result["reused"]["sire"]["value"], "sire001")
        self.assertEqual([x["item"] for x in result["missing"]], ["dam_sire"])
        self.assertEqual(result["external_queries"], 0)
        self.add("root001", "parent.dam", "dam0001")
        self.add("dam0001", "parent.sire", "damsire1")
        self.assertFalse(self.request(fields=["sire", "dam_sire"])["missing"])

    def test_two_horses_share_ancestor_without_duplicate_facts(self):
        self.register("root002", "テスト馬B", external="005")
        self.add("root001", "parent.sire", "sire001")
        self.add("root002", "parent.sire", "sire001")
        self.add("sire001", "attribute.training_country", "USA")
        a = self.reg.query({"horse": {"horse_key": "root001"}, "fields": ["training_country@S"],
                            "data_cutoff": self.future})
        b = self.reg.query({"horse": {"horse_key": "root002"}, "fields": ["training_country@S"],
                            "data_cutoff": self.future})
        self.assertEqual(a["reused"]["training_country@S"]["revision_id"],
                         b["reused"]["training_country@S"]["revision_id"])
        self.assertEqual(len(self.reg.read_horse("sire001")["revisions"]), 1)

    def test_identical_name_never_auto_merges(self):
        self.register("other002", "テスト馬", external="009")
        self.assertEqual(self.reg.resolve({"name": "テスト馬"})["status"], "IDENTITY_UNRESOLVED")
        self.assertEqual(self.reg.query({"horse": {"name": "テスト馬"},
                                         "data_cutoff": self.future})["missing"][0]["item"], "identity")

    def test_unresolved_identity_never_reused(self):
        self.register("other003", "血統不明", status="UNRESOLVED")
        self.assertEqual(self.reg.resolve({"horse_key": "other003"})["status"], "IDENTITY_UNRESOLVED")

    def test_unknown_is_not_absence(self):
        r = self.request(contains=[{"ancestor_key": "damsire1", "depth": 5}])
        self.assertEqual(r["missing"][0]["status"], "UNKNOWN")
        self.add("root001", "parent.sire", "sire001")
        self.add("root001", "parent.dam", "dam0001")
        r = self.request(contains=[{"ancestor_key": "sire001", "depth": 1}])
        self.assertEqual(r["reused"]["contains:sire001:1"]["status"], "PRESENT")
        r = self.request(contains=[{"ancestor_key": "damsire1", "depth": 1}])
        self.assertEqual(r["reused"]["contains:damsire1:1"]["status"], "ABSENT_WITHIN_SCOPE")
        r = self.request(contains=[{"ancestor_key": "damsire1", "depth": 2}])
        self.assertEqual(r["missing"][0]["status"], "UNKNOWN")
        self.add("dam0001", "parent.sire", "damsire1")
        self.assertEqual(self.request(contains=[{"ancestor_key": "damsire1", "depth": 2}])[
            "reused"]["contains:damsire1:2"]["paths"], ["DS"])

    def test_taxonomy_recalculation_without_source_fetch(self):
        self.add("root001", "parent.sire", "sire001")
        for ver, founders in [("v1", ["sire001"]), ("v2", ["damsire1"])]:
            self.reg.taxonomies.mkdir(parents=True, exist_ok=True)
            (self.reg.taxonomies / (ver + ".json")).write_text(json.dumps({
                "schema_version": "pedigree-taxonomy-v1", "version": ver,
                "lines": {"test_line": founders}}), encoding="utf-8")
        first = self.request(lines=[{"name": "test_line"}], taxonomy_version="v1")
        second = self.request(lines=[{"name": "test_line"}], taxonomy_version="v2")
        self.assertEqual(first["reused"]["line:test_line@"]["status"], "PRESENT")
        self.assertEqual(second["missing"][0]["status"], "UNKNOWN")
        self.assertEqual(len(self.reg.read_horse("root001")["revisions"]), 1)

    def test_source_conflict_and_corrected_revision(self):
        one = self.add("root001", "attribute.training_country", "USA")
        two = self.add("root001", "attribute.training_country", "JP", source="other-provider")
        result = self.request(fields=["training_country@"])
        self.assertEqual(result["missing"][0]["status"], "CONFLICT")
        # 互いに競合するrevisionを両方明示訂正して初めて一意になる
        a = self.add("root001", "attribute.training_country", "JP", source="official-fix",
                     previous=one["revision_id"])
        r = self.request(fields=["training_country@"])
        self.assertEqual(r["reused"]["training_country@"]["value"], "JP")
        self.assertEqual(len(self.reg.read_horse("root001")["revisions"]), 3)
        self.assertNotEqual(a["revision_id"], one["revision_id"])

    def test_replay_and_forward_cutoff_safety(self):
        self.add("root001", "parent.sire", "sire001")
        past_cutoff = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1)).isoformat()
        forward = self.reg.query({"horse": {"horse_key": "root001"},
                                  "fields": ["sire"], "data_cutoff": past_cutoff})
        replay = self.reg.query({"horse": {"horse_key": "root001"},
                                 "fields": ["sire"], "data_cutoff": past_cutoff, "mode": "REPLAY"})
        self.assertEqual(forward["missing"][0]["status"], "PARTIAL")
        self.assertEqual(replay["reused"]["sire"]["value"], "sire001")
        self.assertEqual(replay["mode"], "REPLAY")

    def test_idempotent_revision_and_stale_blob(self):
        first = self.add("root001", "parent.sire", "sire001")
        second = self.add("root001", "parent.sire", "sire001")
        self.assertEqual(first["revision_id"], second["revision_id"])
        self.assertEqual(second["status"], "REUSED")
        with self.assertRaises(RegistryError):
            self.reg.add_fact({"horse_key": "root001"}, "ABSENT")

    def test_source_hash_conflict_rejected(self):
        self.add("root001", "attribute.training_country", "USA", source="source-fixed")
        with self.assertRaises(RegistryError):
            self.add("root001", "attribute.training_country", "JPN", source="source-fixed")

    def test_research_plan_receipt_and_retry_error(self):
        request = {"request_id": "research01", "horse": {"horse_key": "root001"},
                   "fields": ["dam_sire"], "data_cutoff": self.future}
        first = self.reg.plan(request)
        self.assertEqual(first["receipt"]["status"], "PERSIST_VERIFIED")
        second = self.reg.plan(request)
        self.assertEqual(len(list(self.reg.research.glob("*.json"))), 1)
        self.assertEqual(second["receipt"]["status"], "PERSIST_VERIFIED")
        self.assertEqual(second["result"]["missing"][0]["item"], "dam_sire")
        attempt = self.reg.attempt({"request_id": "research01", "item": "dam_sire",
                                    "source": "JRA-VAN", "status": "NOT_FOUND"})
        self.assertEqual(attempt["attempt"]["status"], "NOT_FOUND")
        with self.assertRaises(RegistryError):
            self.reg.attempt({"request_id": "research01", "item": "dam_sire",
                              "source": "JRA-VAN", "status": "SOURCE_ERROR"})

    def test_validation_rejects_unverified_as_verified(self):
        self.add("root001", "attribute.training_country", "USA", verified=False)
        result = self.request(fields=["training_country@"])
        self.assertEqual(result["missing"][0]["status"], "UNVERIFIED")

    def test_index_is_candidate_only(self):
        self.register("other004", "テスト馬", external="010")
        built = self.reg.reindex()
        self.assertEqual(built["receipt"]["status"], "PERSIST_VERIFIED")
        candidates = json.loads((self.root / "aliases.json").read_text())["aliases"]["テスト馬"]
        self.assertEqual(len(candidates), 2)
        self.assertEqual(self.reg.resolve({"name": "テスト馬"})["status"], "IDENTITY_UNRESOLVED")


    def test_verified_and_unverified_disagreement_is_conflict(self):
        self.add("root001", "attribute.training_country", "USA")
        self.add("root001", "attribute.training_country", "JP", source="unverified-claim",
                 verified=False)
        result = self.request(fields=["training_country@"])
        self.assertEqual(result["missing"][0]["status"], "CONFLICT")
        self.assertEqual(len(result["missing"][0]["candidates"]), 2)

    def test_cross_only_verified_paths(self):
        self.add("root001", "parent.sire", "sire001")
        self.add("root001", "parent.dam", "dam0001")
        self.add("sire001", "parent.sire", "damsire1")
        self.add("dam0001", "parent.sire", "damsire1")
        r = self.request(crosses=[{"ancestor_key": "damsire1", "depth": 2}])
        self.assertEqual(r["reused"]["cross:damsire1:2"]["status"], "PRESENT")
        self.assertEqual(r["reused"]["cross:damsire1:2"]["generation_cross"], "2x2")
        r2 = self.request(crosses=[{"ancestor_key": "damsire1", "depth": 1}])
        self.assertEqual(r2["reused"]["cross:damsire1:1"]["status"],
                         "ABSENT_WITHIN_SCOPE")

    def test_incomplete_cross_never_absent(self):
        r = self.request(crosses=[{"ancestor_key": "damsire1", "depth": 5}])
        self.assertEqual(r["missing"][0]["status"], "UNKNOWN")


class PedigreeBackfillTests(unittest.TestCase):
    def test_backfill_manifest_and_source_lines_are_traceable(self):
        from migrate_pedigree_notes import collect
        repo = Path(__file__).resolve().parents[1]
        data = repo / "data/pedigree"
        seed = json.loads((data / "research/backfill-2026-10-09.json").read_text(encoding="utf-8"))
        manifest = json.loads((data / "migration_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(seed["schema_version"], "pedigree-backfill-v1")
        self.assertEqual(manifest["scanned_file_count"], len(seed["scanned_files"]))
        self.assertEqual(manifest["extracted_count"], len(seed["records"]))
        self.assertEqual(manifest["verified_count"], 0)
        self.assertFalse(manifest["conflicts_assessed"])
        self.assertEqual(len({c["claim_id"] for c in seed["records"]}), len(seed["records"]))
        for claim in seed["records"]:
            raw = (repo / claim["source_path"]).read_text(encoding="utf-8").splitlines()[
                claim["source_line"] - 1]
            self.assertEqual(raw.strip(), claim["raw_text"])
            self.assertEqual(hashlib.sha256(raw.encode()).hexdigest(),
                             claim["source_text_sha256"])
            self.assertEqual(claim["source_commit"], manifest["source_commit"])
            self.assertEqual(claim["status"], "UNVERIFIED")
        recreated, checked = collect(repo, manifest["source_commit"], seed["generated_at"])
        self.assertEqual({c["claim_id"] for c in recreated["records"]},
                         {c["claim_id"] for c in seed["records"]})
        self.assertEqual(checked["extracted_count"], manifest["extracted_count"])
        self.assertEqual(checked["scanned_files"], manifest["scanned_files"])

    def test_legacy_search_never_claims_verified(self):
        repo = Path(__file__).resolve().parents[1]
        registry = Registry(repo / "data/pedigree")
        result = registry.legacy_search("血統")
        self.assertEqual(result["status"], "UNVERIFIED_CANDIDATES")
        self.assertGreater(result["count"], 0)
        self.assertTrue(all(r["status"] == "UNVERIFIED" for r in result["records"]))


if __name__ == "__main__":
    unittest.main()
