import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pedigree_registry import Registry, SCHEMA as PEDIGREE_SCHEMA, digest, read, atomic
from pedigree_stats import (DEFINITION_SCHEMA, INPUT_SCHEMA, RESULT_RULE, audit, main_training_country,
                            select_training_country,
                            compute, run, verify, validate_manifest, validate_definition,
                            inventory)

DATE = "2026-10-05"
CUTOFF = "2026-10-07T12:00:00+09:00"
REPLAY_CUTOFF = "2026-10-06T12:00:00+09:00"
EARLY = "2026-10-01T00:00:00+09:00"
BASE = "2026-09-01T00:00:00+09:00"
DEF_PATH = "data/condition_stats/definitions/sample.json"
INPUT_PATH = "data/condition_stats/inputs/sample.json"


class PedigreeStatsTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.registry = Registry(self.root / "data/pedigree")
        for horse in ("sire-a", "sire-b", "alice", "bob", "unknown", "d", "ancestor"):
            self.save(horse)
        self.fact("sire-a", "attribute:training_country", "US")
        self.fact("sire-b", "attribute:training_country", "GB")
        self.fact("alice", "attribute:training_country", "FR")
        self.fact("alice", "parent:S", "sire-a")
        self.fact("bob", "parent:S", "sire-b")
        self.fact("d", "parent:S", "sire-a")
        self.definition = {
            "schema_version": DEFINITION_SCHEMA,
            "definition_id": "sire-study",
            "mode": "REPLAY",
            "period_start": "2026-10-01", "period_end": "2026-10-07",
            "data_cutoff": CUTOFF, "result_rule": RESULT_RULE,
            "comparison": "NON_MATCH",
            "scope": {"venue": "TOK", "surface": "TURF",
                      "distance_min": 1600, "distance_max": 2000},
            "training_classification": {
                "version": "test-v1", "source": "fixture",
                "first_observed_at": BASE,
                "regions": {"EU": ["FR", "GB"], "US": ["US"]},
            },
            "groups": [
                {"group_id": "sire-a", "axis": "SIRE", "value": "sire-a"},
                {"group_id": "sire-us", "axis": "TRAINING_REGION",
                 "subject": "SIRE", "value": "US"},
                {"group_id": "horse-eu", "axis": "TRAINING_REGION",
                 "subject": "HORSE", "value": "EU"},
            ],
        }
        self.manifest = {
            "schema_version": INPUT_SCHEMA,
            "source_scope": "test-all-jra-entries",
            "all_runners_included": True,
            "races": [
                self.race("R1", DATE, [
                    self.runner("alice", "FINISHED", 1),
                    self.runner("bob", "FINISHED", 1),
                    self.runner("unknown", "FINISHED", 3),
                    self.runner("d", "DNF"),
                ]),
                self.race("R2", "2026-10-06", [
                    self.runner("alice", "FINISHED", 2),
                    self.runner("bob", "FINISHED", 1),
                    self.runner("unknown", "SCRATCHED"),
                    self.runner("d", "DQ"),
                ]),
            ],
        }
        self.persist()

    def save(self, key, facts=None, identity=None):
        current = read(self.registry.path(key))
        candidate = {
            "schema_version": PEDIGREE_SCHEMA, "horse_key": key,
            "identity": identity or {
                "name": key, "aliases": [],
                "status": "RESOLVED", "external_ids": {"fixture": key},
                "identity_evidence": {"source": "fixture", "record_key": key},
            },
            "facts": facts or [],
        }
        with patch("pedigree_registry.stamp",
                   return_value="2026-10-09T01:00:00+00:00" if current else BASE):
            return self.registry.save(candidate, digest(current) if current else None)

    def fact(self, key, field, value, observed=EARLY, captured=None, source_class="BREEDING_DB", extra_source=None):
        item = {
            "field": field, "value": value, "status": "VERIFIED",
            "first_observed_at": observed, "captured_at": captured or observed,
            "source": {"source_class": source_class,
                       "origin_group": "fixture", "acquisition_method":
                       "user-chat" if source_class == "USER_PROVIDED" else "manual-verified",
                       "record_key": key,
                        "record_hash": (
                            __import__("hashlib").sha256(value.encode()).hexdigest()
                            if source_class == "USER_PROVIDED"
                            else digest([key, field, value])),
                        **({"user_reply_text": value} if source_class == "USER_PROVIDED" else {})},
            "verification": {"identity_checked": True, "source_checked": True,
                             "relationship_checked": True, "reviewed_by": "test"},
        }
        item['source'].update(extra_source or {})
        return self.save(key, [item])

    @staticmethod
    def runner(horse, status, finish=None, observed=EARLY):
        return {"horse_key": horse, "status": status,
                "finish_position": finish, "entry_observed_at": observed}

    @staticmethod
    def race(race_id, date, runners, status="OFFICIAL", observed=CUTOFF):
        return {
            "race_id": race_id, "race_date_jst": date, "venue": "TOK",
            "surface": "TURF", "distance_m": 1800,
            "class": "MAIDEN", "going": "GOOD", "race_type": "NORMAL",
            "result_status": status, "result_observed_at": observed,
            "official_source": {"record_key": race_id, "record_hash": digest(race_id)},
            "runners": runners,
        }

    def persist(self):
        atomic(self.root / DEF_PATH, self.definition)
        atomic(self.root / INPUT_PATH, self.manifest)

    def calculate(self):
        self.persist()
        return run(self.root, DEF_PATH, INPUT_PATH)

    def test_01_all_starters_and_rates_use_full_race_field(self):
        path, out = self.calculate()
        self.assertEqual(out["all_runners"]["entries"], 8)
        self.assertEqual(out["all_runners"]["valid_starts"], 7)
        self.assertEqual(out["all_runners"]["wins"], 3)   # R1 tie at 1st, R2 winner
        self.assertEqual(out["all_runners"]["top2"], 4)
        self.assertEqual(out["all_runners"]["top3"], 5)
        group = out["groups"]["sire-a"]
        matching = group["cohorts"]["MATCH"]
        self.assertEqual(matching["entries"], 4)
        self.assertEqual(matching["horses"], 2)
        self.assertEqual(matching["races"], 2)
        self.assertEqual(matching["wins"], 1)
        self.assertEqual(matching["top2"], 2)
        self.assertEqual(matching["top3"], 2)
        self.assertEqual(matching["dnf"], 1)
        self.assertEqual(matching["dq"], 1)
        self.assertEqual(matching["valid_starts"], 4)
        self.assertEqual(matching["win_rate"], 0.25)
        self.assertEqual(group["cohorts"]["NON_MATCH"]["entries"], 2)
        self.assertEqual(group["cohorts"]["UNKNOWN"]["entries"], 2)
        self.assertEqual(group["baseline"]["valid_starts"], 2)
        self.assertEqual(verify(self.root, path)["content_sha256"], out["content_sha256"])

    def test_02_duplicate_input_is_deduplicated_but_same_horse_different_race_counted(self):
        expected = self.calculate()[1]
        self.manifest["races"][0]["runners"].append(
            copy.deepcopy(self.manifest["races"][0]["runners"][0]))
        p, out = self.calculate()
        self.assertEqual(out["duplicates_removed"], 1)
        self.assertEqual(out["all_runners"]["entries"], expected["all_runners"]["entries"])
        self.assertEqual(out["groups"]["sire-a"]["cohorts"]["MATCH"]["valid_starts"], 4)
        self.assertEqual(out["groups"]["sire-a"]["cohorts"]["MATCH"]["horses"], 2)
        self.assertNotEqual(out["content_sha256"], expected["content_sha256"])
        self.assertEqual(verify(self.root, p)["content_sha256"], out["content_sha256"])

    def test_03_conflicting_duplicate_is_rejected(self):
        self.manifest["races"][0]["runners"].append(
            self.runner("alice", "FINISHED", 2))
        with self.assertRaisesRegex(ValueError, "conflicting duplicate"):
            self.calculate()

    def test_04_unknown_and_conflicting_pedigree_never_become_nonmatch(self):
        g = self.calculate()[1]["groups"]["sire-a"]
        self.assertEqual(g["cohorts"]["UNKNOWN"]["entries"], 2)
        self.fact("unknown", "parent:S", "sire-a")
        # Two divergent verified sources cannot silently determine pedigree.
        self.fact("unknown", "parent:S", "sire-b", observed="2026-10-02T00:00:00+09:00")
        g2 = self.calculate()[1]["groups"]["sire-a"]
        self.assertEqual(g2["cohorts"]["CONFLICT"]["entries"], 2)
        self.assertEqual(g2["cohorts"]["NON_MATCH"]["entries"], 2)
        self.assertEqual(g2["cohorts"]["UNKNOWN"]["entries"], 0)

    def test_05_training_region_uses_subject_history_not_birth_country_or_lineage(self):
        self.fact("sire-a", "attribute:birth_country", "FR")
        self.fact("alice", "attribute:birth_country", "US")
        result = self.calculate()[1]
        self.assertEqual(result["groups"]["sire-us"]["cohorts"]["MATCH"]["entries"], 4)
        self.assertEqual(result["groups"]["horse-eu"]["cohorts"]["MATCH"]["entries"], 2)
        self.assertEqual(result["groups"]["horse-eu"]["cohorts"]["UNKNOWN"]["entries"], 6)
        self.assertEqual(result["groups"]["sire-us"]["cohorts"]["NON_MATCH"]["entries"], 2)

    def test_06_multiple_region_training_is_unknown(self):
        self.fact("bob", "attribute:training_country", "US/FR")
        out = self.calculate()[1]
        self.assertEqual(out["horse_trace"]["bob"]["groups"]["horse-eu"]["status"], "UNKNOWN")
        self.assertEqual(out["horse_trace"]["bob"]["groups"]["horse-eu"]["reason"],
                         "MULTI_REGION_CLASSIFICATION_UNDEFINED")

    def test_07_forward_rejects_future_results_and_classification(self):
        self.definition["mode"] = "FORWARD"
        self.definition["data_cutoff"] = "2026-10-06T09:00:00+09:00"
        with self.assertRaisesRegex(ValueError, "after cutoff"):
            self.calculate()
        self.definition["data_cutoff"] = CUTOFF
        self.definition["training_classification"]["first_observed_at"] = "2026-10-09T10:00:00+09:00"
        with self.assertRaisesRegex(ValueError, "future classification"):
            self.calculate()

    def test_08_forward_late_pedigree_remains_unknown_replay_can_use_it(self):
        self.fact("unknown", "parent:S", "sire-a", observed="2026-10-08T00:00:00+09:00")
        self.definition["mode"] = "FORWARD"
        fw = self.calculate()[1]
        self.assertEqual(fw["groups"]["sire-a"]["cohorts"]["UNKNOWN"]["entries"], 2)
        self.definition["mode"] = "REPLAY"
        self.definition["data_cutoff"] = "2026-10-09T10:00:00+09:00"
        rp = self.calculate()[1]
        self.assertEqual(rp["groups"]["sire-a"]["cohorts"]["MATCH"]["entries"], 6)
        self.assertFalse(rp["production_eligible"])
        self.assertEqual(rp["usage"], "RESEARCH_SHADOW_ONLY")

    def test_09_stable_snapshots_revision_and_old_verification(self):
        first_path, first = self.calculate()
        again_path, again = self.calculate()
        self.assertEqual(first_path, again_path)
        self.assertEqual(first, again)
        self.manifest["races"][1]["runners"][0]["finish_position"] = 1
        second_path, second = self.calculate()
        self.assertNotEqual(first_path, second_path)
        self.assertEqual(second["groups"]["sire-a"]["cohorts"]["MATCH"]["wins"], 2)
        # 元manifestが訂正されても、旧版は内容アドレス保存した入力で認証できる。
        self.assertEqual(verify(self.root, first_path)["content_sha256"], first["content_sha256"])
        self.assertEqual(verify(self.root, second_path)["content_sha256"], second["content_sha256"])
        self.assertTrue(audit(self.root))

    def test_10_scope_incomplete_never_reports_complete(self):
        self.manifest["all_runners_included"] = False
        _, out = self.calculate()
        self.assertEqual(out["completeness"], "PARTIAL")
        self.assertTrue(any(x["type"] == "INCOMPLETE_RACE_SCOPE" for x in out["missing"]))

    def test_11_result_pending_not_denominator_and_non_starters_excluded(self):
        self.manifest["races"][1]["result_status"] = "PENDING"
        for r in self.manifest["races"][1]["runners"]:
            if r["status"] not in {"SCRATCHED", "EXCLUDED"}:
                r["status"], r["finish_position"] = "PENDING", None
        _, out = self.calculate()
        self.assertEqual(out["groups"]["sire-a"]["cohorts"]["MATCH"]["valid_starts"], 2)
        self.assertEqual(out["groups"]["sire-a"]["cohorts"]["MATCH"]["pending_results"], 2)
        self.assertEqual(out["groups"]["sire-a"]["cohorts"]["MATCH"]["win_rate"], 0.5)
        self.assertEqual(out["completeness"], "PARTIAL")

    def test_12_empty_denominator_is_null(self):
        self.definition["scope"]["venue"] = "NO_SUCH_COURSE"
        _, out = self.calculate()
        self.assertIsNone(out["all_runners"]["win_rate"])
        self.assertIsNone(out["groups"]["sire-a"]["cohorts"]["MATCH"]["top3_rate"])
        self.assertEqual(out["completeness"], "PARTIAL")

    def test_13_training_lineage_and_ancestor_scope_are_separate(self):
        self.fact("sire-a", "parent:S", "ancestor")
        self.fact("sire-b", "parent:S", "ancestor")
        # Full depth 2 requires horse S,D,SS,SD,DS,DD all confirmed.
        self.definition["groups"].extend([
            {"group_id": "contains", "axis": "ANCESTOR", "value": "ancestor", "depth": 2},
            {"group_id": "cross", "axis": "CROSS", "value": "ancestor",
             "depth": 2, "min_paths": 2},
        ])
        _, out = self.calculate()
        self.assertEqual(out["horse_trace"]["alice"]["groups"]["contains"]["status"], "MATCH")
        self.assertEqual(out["horse_trace"]["alice"]["groups"]["cross"]["status"], "UNKNOWN")

    def test_14_invalid_contract_and_tamper_detected(self):
        path, _ = self.calculate()
        obj = read(path)
        obj["all_runners"]["wins"] = 999
        atomic(path, obj)
        with self.assertRaisesRegex(ValueError, "snapshot content hash mismatch"):
            verify(self.root, path)
        self.assertFalse(audit(self.root))
        self.definition["groups"][0]["axis"] = "UNSUPPORTED"
        with self.assertRaisesRegex(ValueError, "unsupported pedigree axis"):
            self.calculate()

    def test_15_same_horse_can_match_two_overlapping_groups(self):
        self.definition["groups"].append({
            "group_id": "same-sire", "axis": "SIRE", "value": "sire-a",
        })
        _, result = self.calculate()
        self.assertEqual(result["groups"]["same-sire"]["cohorts"]["MATCH"]["entries"], 4)
        self.assertEqual(result["all_runners"]["entries"], 8)
        self.assertEqual(result["groups"]["sire-a"]["cohorts"]["MATCH"]["entries"], 4)

    def test_16_replay_results_at_future_observation_are_explicitly_research_only(self):
        self.manifest["races"][0]["result_observed_at"] = "2026-10-10T11:00:00+09:00"
        p, obj = self.calculate()
        self.assertEqual(obj["mode"], "REPLAY")
        self.assertFalse(obj["production_eligible"])
        self.assertEqual(verify(self.root, p)["usage"], "RESEARCH_SHADOW_ONLY")

    def test_17_official_only_winner_export_is_not_accepted_as_complete(self):
        # 入力の自己申告に依存する境界を明示。全出走一覧を省略した場合は
        # source_scope / all_runners_included をFALSEにする契約。
        self.manifest["all_runners_included"] = False
        self.manifest["races"][0]["runners"] = self.manifest["races"][0]["runners"][:1]
        _, obj = self.calculate()
        self.assertEqual(obj["completeness"], "PARTIAL")

    def test_18_taxonomy_cutoff_and_training_mapping_no_guess(self):
        self.definition["mode"] = "FORWARD"
        self.definition["training_classification"]["regions"] = {"EU": ["FR"], "US": ["US"]}
        _, obj = self.calculate()
        self.assertEqual(obj["horse_trace"]["bob"]["groups"]["sire-us"]["status"], "UNKNOWN")
        self.assertEqual(obj["horse_trace"]["bob"]["groups"]["sire-us"]["reason"],
                         "UNMAPPED_OR_AMBIGUOUS_TRAINING_COUNTRY")


    def test_19_incremental_reuses_unchanged_classification_and_updates_affected(self):
        old_path, old = self.calculate()
        # 未確認馬のみ確認が進んだ。別馬の分類結果とrevision証跡を維持。
        self.fact("unknown", "parent:S", "sire-a")
        self.persist()
        updated_path, updated = run(
            self.root, DEF_PATH, INPUT_PATH,
            previous_path=old_path.relative_to(self.root).as_posix())
        self.assertEqual(updated["groups"]["sire-a"]["cohorts"]["MATCH"]["entries"], 6)
        self.assertEqual(updated["horse_trace"]["alice"], old["horse_trace"]["alice"])
        self.assertNotEqual(updated["horse_trace"]["unknown"], old["horse_trace"]["unknown"])
        cold_path, cold = self.calculate()
        self.assertEqual(cold_path, updated_path)
        self.assertEqual(cold, updated)
        self.assertEqual(verify(self.root, old_path)["content_sha256"], old["content_sha256"])

    def test_20_training_classification_change_invalidates_reused_groups(self):
        old_path, old = self.calculate()
        self.definition["training_classification"]["regions"] = {
            "EU": ["FR", "US"], "US": ["US"]
        }
        # 重複地域所属は分類不能。前のMATCHを再利用せずUNKNOWNになる。
        self.persist()
        path, updated = run(self.root, DEF_PATH, INPUT_PATH,
                            previous_path=old_path.relative_to(self.root).as_posix())
        self.assertNotEqual(path, old_path)
        self.assertEqual(updated["horse_trace"]["alice"]["groups"]["sire-us"]["status"],
                         "UNKNOWN")
        self.assertNotEqual(updated["horse_trace"]["alice"], old["horse_trace"]["alice"])

    def test_21_post_cutoff_revision_does_not_rewrite_forward_asof_fingerprint(self):
        self.definition["mode"] = "FORWARD"
        first_path, first = self.calculate()
        self.fact("alice", "attribute:birth_country", "JP",
                  observed="2026-10-08T00:00:00+09:00")
        self.persist()
        second_path, second = run(
            self.root, DEF_PATH, INPUT_PATH,
            previous_path=first_path.relative_to(self.root).as_posix())
        self.assertEqual(first_path, second_path)
        self.assertEqual(first, second)
        self.assertTrue(audit(self.root))

    def test_22_inventory_keeps_legacy_candidates_unverified(self):
        migration = {
            "schema_version": PEDIGREE_SCHEMA,
            "extracted": 1, "commit": "a" * 40,
            "claims": [{
                "path": "docs/source.md", "status": "UNVERIFIED",
                "identity_status": "IDENTITY_UNRESOLVED",
                "components": [{"kind": "DERIVED_CLAIM", "status": "UNVERIFIED"}]
            }],
        }
        atomic(self.registry.root / "migration.json", migration)
        result = inventory(self.root)
        self.assertEqual(result["candidate_claims"], 1)
        self.assertEqual(result["unverified_claims"], 1)
        self.assertEqual(result["verified_facts"], 6)
        self.assertFalse(result["source_verification_complete"])
        self.assertFalse(result["stats_source_ready"])
        migration["claims"][0]["status"] = "VERIFIED"
        atomic(self.registry.root / "migration.json", migration)
        with self.assertRaisesRegex(ValueError, "may not be automatically promoted"):
            inventory(self.root)



    def test_23_predeclared_stats_and_unaggregated_changed_inputs_fail_audit(self):
        # 定義や元結果だけが保存されても、snapshot不足を発見する。
        self.assertFalse(audit(self.root))
        path, _ = self.calculate()
        self.assertTrue(audit(self.root))
        self.manifest["races"][1]["runners"][0]["finish_position"] = 1
        self.persist()
        self.assertFalse(audit(self.root))
        new_path, _ = self.calculate()
        self.assertNotEqual(path, new_path)
        self.assertTrue(audit(self.root))



    def test_24_backdated_observation_captured_after_cutoff_stays_unknown(self):
        self.definition["mode"] = "FORWARD"
        self.fact("unknown", "parent:S", "sire-a", observed=EARLY,
                  captured="2026-10-08T08:00:00+09:00")
        self.persist()
        _, out = self.calculate()
        status = out["horse_trace"]["unknown"]["groups"]["sire-a"]
        self.assertEqual(status["status"], "UNKNOWN")
        self.assertEqual(status["reason"], "UNVERIFIED")
        self.assertEqual(out["groups"]["sire-a"]["cohorts"]["UNKNOWN"]["entries"], 2)



    def training_starts(self, countries):
        return {"complete": True, "total_starts": len(countries), "starts": [
            {"race_id": f"TRAINING-{i}", "race_date": "2026-09-01",
             "training_country": country, "race_country": "GB",
             "source": {"url": "https://authority.example/starts", "record_hash": digest(i),
                        "captured_at": EARLY}}
            for i, country in enumerate(countries)]}

    def test_26_main_training_country_counts_affiliation_not_race_venue(self):
        history = self.training_starts(["FR", "FR", "GB"])
        self.assertEqual(main_training_country(history, CUTOFF)[0], "FR")
        self.fact("sire-a", "attribute:training_start_history", history)
        self.definition["training_classification"]["country_selection"] = "MOST_STARTS_BY_TRAINING_COUNTRY"
        _, out = self.calculate()
        self.assertEqual(out["groups"]["sire-us"]["cohorts"]["MATCH"]["entries"], 0)
        self.assertEqual(out["groups"]["sire-us"]["cohorts"]["NON_MATCH"]["entries"], 4)
        # The old single-country attribute US must not override the selected method.
        self.assertEqual(out["groups"]["horse-eu"]["cohorts"]["UNKNOWN"]["entries"], 8)

    def test_27_training_start_ties_and_incomplete_history_stay_unknown(self):
        history = self.training_starts(["FR", "US"])
        self.assertEqual(main_training_country(history, CUTOFF)[1],
                         "MAIN_TRAINING_COUNTRY_TIED_USER_INPUT_REQUIRED")
        history["complete"] = False
        self.assertIsNone(main_training_country(history, CUTOFF)[0])
        history["complete"] = True
        history["total_starts"] = 3
        self.assertIsNone(main_training_country(history, CUTOFF)[0])
        history["total_starts"] = 2
        history["starts"][1]["race_id"] = history["starts"][0]["race_id"]
        self.assertIsNone(main_training_country(history, CUTOFF)[0])

    def test_28_training_country_source_cutoff_and_no_birth_country_fallback(self):
        history = self.training_starts(["FR"])
        history["starts"][0].pop("training_country")
        history["starts"][0]["birth_country"] = "FR"
        self.assertIsNone(main_training_country(history, CUTOFF)[0])
        history = self.training_starts(["FR"])
        history["starts"][0]["source"]["captured_at"] = "2026-10-10T00:00:00+09:00"
        self.assertEqual(main_training_country(history, CUTOFF)[1], "TRAINING_SOURCE_AFTER_CUTOFF")
        history["starts"][0]["source"]["captured_at"] = EARLY
        history["starts"][0]["race_date"] = "2026-10-10"
        self.assertEqual(main_training_country(history, CUTOFF)[1], "TRAINING_START_AFTER_CUTOFF")
        history["starts"][0]["race_date"] = "2026-09-01"
        history["starts"][0]["source"].pop("record_hash")
        self.assertEqual(main_training_country(history, CUTOFF)[1], "TRAINING_START_SOURCE_MISSING")


    @staticmethod
    def matched_countries(entries):
        return {
            "schema_version": "training-country-matches-v1",
            "search_completed": True,
            "matches": [
                {"country": country, "last_trained_on": last,
                 "source": {"url": "https://example.org/racing/trainer",
                            "record_hash": digest([country, last, i]),
                            "captured_at": EARLY}}
                for i, (country, last) in enumerate(entries)
            ],
        }

    def test_29_search_single_match_stops_without_legacy_or_full_history(self):
        self.definition["training_classification"]["country_selection"] = "SEARCH_MATCH_PRIORITY_V1"
        self.fact("sire-a", "attribute:training_country_matches",
                  self.matched_countries([("FR", None)]))
        _, result = self.calculate()
        self.assertEqual(result["groups"]["sire-us"]["cohorts"]["NON_MATCH"]["entries"], 4)
        self.assertEqual(result["groups"]["sire-us"]["cohorts"]["MATCH"]["entries"], 0)
        self.assertEqual(select_training_country(
            self.matched_countries([("FR", None)]), CUTOFF),
            ("FR", "VERIFIED_SINGLE_MATCH_TRAINING_COUNTRY"))

    def test_30_multiple_countries_choose_latest_not_most_frequent(self):
        self.definition["training_classification"]["country_selection"] = "SEARCH_MATCH_PRIORITY_V1"
        matches = self.matched_countries([
            ("FR", "2026-01-01"), ("FR", "2026-02-01"), ("US", "2026-09-01")])
        self.fact("sire-a", "attribute:training_country_matches", matches)
        _, result = self.calculate()
        self.assertEqual(result["groups"]["sire-us"]["cohorts"]["MATCH"]["entries"], 4)
        self.assertEqual(select_training_country(matches, CUTOFF),
                         ("US", "VERIFIED_LATEST_MATCH_TRAINING_COUNTRY"))

    def test_31_no_match_requires_user_chat_answer_with_provenance(self):
        self.definition["training_classification"]["country_selection"] = "SEARCH_MATCH_PRIORITY_V1"
        no_matches = self.matched_countries([])
        self.fact("bob", "attribute:training_country_matches", no_matches)
        _, before = self.calculate()
        self.assertEqual(before["horse_trace"]["bob"]["groups"]["horse-eu"]["reason"],
                         "TRAINING_COUNTRY_USER_INPUT_REQUIRED")
        # A chat answer stays separate from previous authoritative training_country facts.
        self.fact("bob", "attribute:training_country_user", "FR", source_class="USER_PROVIDED")
        _, after = self.calculate()
        self.assertEqual(after["horse_trace"]["bob"]["groups"]["horse-eu"]["status"], "MATCH")
        self.assertEqual(after["horse_trace"]["bob"]["groups"]["horse-eu"]["reason"],
                         "USER_PROVIDED_TRAINING_REGION")
        # A legacy source is not a substitute for a response to the no-match task.
        self.fact("d", "attribute:training_country_matches", no_matches)
        _, out = self.calculate()
        self.assertEqual(out["horse_trace"]["d"]["groups"]["horse-eu"]["reason"],
                         "TRAINING_COUNTRY_USER_INPUT_REQUIRED")

    def test_32_multiple_matches_without_dates_or_tied_dates_remain_unknown(self):
        self.definition["training_classification"]["country_selection"] = "SEARCH_MATCH_PRIORITY_V1"
        undated = self.matched_countries([("US", None), ("FR", "2026-05-01")])
        self.assertEqual(select_training_country(undated, CUTOFF)[1],
                         "TRAINING_COUNTRY_RECENT_DATE_REQUIRED")
        tied = self.matched_countries([("US", "2026-05-01"), ("FR", "2026-05-01")])
        self.fact("sire-a", "attribute:training_country_matches", tied)
        _, result = self.calculate()
        self.assertEqual(result["horse_trace"]["alice"]["groups"]["sire-us"]["reason"],
                         "TRAINING_COUNTRY_LATEST_TIED_USER_INPUT_REQUIRED")

    def test_33_search_respects_cutoff_and_requires_source(self):
        matches = self.matched_countries([("US", None)])
        matches["matches"][0]["source"]["captured_at"] = "2026-10-08T00:00:00+09:00"
        self.assertEqual(select_training_country(matches, CUTOFF)[1],
                         "TRAINING_COUNTRY_MATCH_AFTER_CUTOFF")
        matches["matches"][0]["source"]["captured_at"] = EARLY
        matches["matches"][0]["source"].pop("record_hash")
        self.assertEqual(select_training_country(matches, CUTOFF)[1],
                         "TRAINING_COUNTRY_MATCH_SOURCE_MISSING")

    def test_34_user_source_restricted_to_chat_country_attribute(self):
        with self.assertRaisesRegex(ValueError, "user-provided evidence"):
            self.fact("bob", "attribute:birth_country", "FR", source_class="USER_PROVIDED")
        with self.assertRaisesRegex(ValueError, "training country match source"):
            obj = self.matched_countries([("FR", None)])
            obj["matches"][0]["source"].pop("record_hash")
            self.fact("bob", "attribute:training_country_matches", obj)

    def test_35_user_answer_is_independent_of_legacy_training_country(self):
        self.definition["training_classification"]["country_selection"] = "SEARCH_MATCH_PRIORITY_V1"
        self.fact("sire-a", "attribute:training_country_matches", self.matched_countries([]))
        # sire-a already has an old verified US attribute, which must remain intact.
        self.fact("sire-a", "attribute:training_country_user", "FR",
                  source_class="USER_PROVIDED")
        _, out = self.calculate()
        self.assertEqual(out["groups"]["sire-us"]["cohorts"]["NON_MATCH"]["entries"], 4)
        self.assertEqual(self.registry.fact("sire-a", "attribute:training_country", CUTOFF)["value"],
                         "US")
        self.assertEqual(out["horse_trace"]["alice"]["groups"]["sire-us"]["reason"],
                         "USER_PROVIDED_TRAINING_REGION")

    def test_36_corrected_user_answer_requires_append_only_proof(self):
        self.definition["training_classification"]["country_selection"] = "SEARCH_MATCH_PRIORITY_V1"
        self.fact("bob", "attribute:training_country_matches", self.matched_countries([]))
        self.fact("bob", "attribute:training_country_user", "FR",
                  source_class="USER_PROVIDED")
        before = self.registry.fact("bob", "attribute:training_country_user", CUTOFF)
        corrected = {
            "field": "attribute:training_country_user",
            "value": "US", "status": "VERIFIED",
            "first_observed_at": "2026-10-02T00:00:00+09:00",
            "captured_at": "2026-10-02T00:00:00+09:00",
            "source": {
                "source_class": "USER_PROVIDED", "origin_group": "fixture",
                "acquisition_method": "user-chat", "record_key": "corrected-message",
                "user_reply_text": "US",
                "record_hash": __import__("hashlib").sha256(b"US").hexdigest()},
            "verification": {
                "identity_checked": True, "source_checked": True,
                "relationship_checked": True, "reviewed_by": "test"},
            "supersedes": [before["revision_id"]],
            "correction_reason": "ユーザーが前回回答を訂正",
        }
        self.save("bob", [corrected])
        self.assertEqual(self.registry.fact("bob", "attribute:training_country_user", CUTOFF)["value"],
                         "US")
        _, out = self.calculate()
        self.assertEqual(out["horse_trace"]["bob"]["groups"]["horse-eu"]["status"], "NON_MATCH")


    def test_37_explicit_suffix_answer_resolves_undated_multiple_countries(self):
        self.definition['training_classification']['country_selection'] = 'SEARCH_MATCH_PRIORITY_V1'
        self.fact('bob', 'attribute:training_country_matches', self.matched_countries([('US', None), ('FR', None)]))
        self.fact('bob', 'attribute:training_country_user', 'FR', source_class='USER_PROVIDED',
                  extra_source={'resolution_policy': 'USER_CONFIRMED_NAME_SUFFIX_V1', 'subject_name': 'Bob (仏)'})
        _, result = self.calculate()
        self.assertEqual(result['horse_trace']['bob']['groups']['horse-eu']['status'], 'MATCH')
        self.assertEqual(result['horse_trace']['bob']['groups']['horse-eu']['reason'], 'USER_PROVIDED_TRAINING_REGION')

    def test_38_unscoped_answer_does_not_resolve_multiple_countries(self):
        self.definition['training_classification']['country_selection'] = 'SEARCH_MATCH_PRIORITY_V1'
        self.fact('bob', 'attribute:training_country_matches', self.matched_countries([('US', None), ('FR', None)]))
        self.fact('bob', 'attribute:training_country_user', 'FR', source_class='USER_PROVIDED')
        _, result = self.calculate()
        self.assertEqual(result['horse_trace']['bob']['groups']['horse-eu']['status'], 'UNKNOWN')

    def test_39_suffix_country_mismatch_rejected(self):
        with self.assertRaisesRegex(ValueError, 'suffix policy/name/country mismatch'):
            self.fact('bob', 'attribute:training_country_user', 'US', source_class='USER_PROVIDED',
                      extra_source={'resolution_policy': 'USER_CONFIRMED_NAME_SUFFIX_V1', 'subject_name': 'Bob (仏)'})

    def test_40_suffix_mapping_and_non_country_parentheses(self):
        from pedigree_registry import country_name_suffix
        self.assertEqual(country_name_suffix('Horse（USA）'), 'US')
        self.assertEqual(country_name_suffix('Horse (米)'), 'US')
        self.assertIsNone(country_name_suffix('Horse (未確認)'))
        self.assertIsNone(country_name_suffix('Horse'))

    def test_41_explicit_direct_answer_resolves_undated_multiple_countries(self):
        self.definition['training_classification']['country_selection'] = 'SEARCH_MATCH_PRIORITY_V1'
        self.fact('bob', 'attribute:training_country_matches', self.matched_countries([('US', None), ('GB', None)]))
        item = {'field': 'attribute:training_country_user', 'value': 'GB', 'status': 'VERIFIED',
                'first_observed_at': EARLY, 'captured_at': EARLY,
                'source': {'source_class': 'USER_PROVIDED', 'origin_group': 'USER_CHAT',
                           'acquisition_method': 'user-chat', 'record_key': 'bob',
                           'user_reply_text': 'bobはイギリス',
                           'record_hash': __import__('hashlib').sha256('bobはイギリス'.encode()).hexdigest(),
                           'resolution_policy': 'USER_EXPLICIT_COUNTRY_V1', 'subject_name': 'bob'},
                'verification': {'identity_checked': True, 'source_checked': True, 'relationship_checked': True, 'reviewed_by': 'test'}}
        self.save('bob', [item])
        _, result = self.calculate()
        self.assertEqual(result['horse_trace']['bob']['groups']['horse-eu']['status'], 'MATCH')
        self.assertEqual(result['horse_trace']['bob']['groups']['horse-eu']['reason'], 'USER_PROVIDED_TRAINING_REGION')
        self.assertEqual(self.registry.fact('bob', 'attribute:training_country_user', BASE)['status'], 'NOT_FOUND')
        item['value'] = 'US'
        with self.assertRaisesRegex(ValueError, 'explicit user name/country/reply mismatch'):
            self.save('bob', [item])

    def test_42_explicit_country_parser_does_not_fill_unlisted_horses(self):
        from pedigree_registry import explicit_user_countries
        self.assertEqual(explicit_user_countries("Flatterはアメリカ\nMagic Albertはオーストラリア\n所感：検索先が偏り過ぎている"),
                         {'Flatter': 'US', 'Magic Albert': 'AU'})
        with self.assertRaisesRegex(ValueError, 'conflicting explicit'):
            explicit_user_countries('Flatterはアメリカ\nFlatterはイギリス')

    def test_shared_ancestor_expansion_keeps_each_condition_and_depth(self):
        definition = copy.deepcopy(self.definition)
        definition['groups'] = [
            {'group_id': 'present', 'axis': 'ANCESTOR', 'value': 'sire-a', 'depth': 2},
            {'group_id': 'absent', 'axis': 'ANCESTOR', 'value': 'ancestor', 'depth': 2},
            {'group_id': 'cross', 'axis': 'CROSS', 'value': 'sire-a', 'depth': 2, 'min_paths': 2},
            {'group_id': 'short', 'axis': 'ANCESTOR', 'value': 'sire-a', 'depth': 1},
        ]
        from pedigree_stats import Resolver
        resolver = Resolver(self.registry, CUTOFF, definition)
        with patch.object(self.registry, 'derive', wraps=self.registry.derive) as derive:
            result = resolver.all_groups('alice')
            self.assertEqual(derive.call_count, 2)
            self.assertEqual(result['groups']['present']['status'], 'MATCH')
            self.assertEqual(result['groups']['absent']['status'], 'UNKNOWN')
            self.assertEqual(result['groups']['cross']['status'], 'UNKNOWN')
            self.assertEqual(result['groups']['short']['status'], 'MATCH')
            first = derive.call_args_list[0].args
            self.assertEqual(set(first[1]), {'sire-a', 'ancestor'})
            # 別個体の依存集合へ前の馬のcacheを流用しない。
            other = resolver.all_groups('bob')
            self.assertEqual(derive.call_count, 4)
            self.assertNotIn('alice', other['dependencies'])


if __name__ == "__main__":
    unittest.main()

