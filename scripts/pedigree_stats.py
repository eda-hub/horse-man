#!/usr/bin/env python3
"""版付きcondition_stat_snapshot: 全出走母数・血統確認状態・公式結果を分離して集計する。

入力はPhase 2で検証/保存した出走結果manifest。API取得、血統確認、
Production加点は行わない。古いsnapshotは再計算で上書きしない。
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys

from pedigree_registry import Registry, atomic, digest, dt, read, safe

DEFINITION_SCHEMA = "pedigree-condition-stat-definition-v1"
INPUT_SCHEMA = "official-runners-manifest-v1"
SNAPSHOT_SCHEMA = "condition-stat-snapshot-v1"
CALCULATOR = "pedigree-condition-stats-v1"
RESULT_RULE = "official-finish-position-v1"
AXES = {"SIRE", "DAM_SIRE", "SIRE_LINE", "DAM_SIRE_LINE",
        "ANCESTOR", "CROSS", "TRAINING_REGION"}
RESULT_STATES = {"FINISHED", "DNF", "DQ", "SCRATCHED", "EXCLUDED", "PENDING"}
NON_START = {"SCRATCHED", "EXCLUDED"}
UNRESOLVED = {"UNKNOWN", "CONFLICT"}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def read_object(path):
    data = read(path)
    require(isinstance(data, dict), f"{path}: JSON object required")
    return data


def filehash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def iso(value, label):
    require(isinstance(value, str), f"{label}: offset-aware timestamp required")
    try:
        return dt(value)
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError(f"{label}: invalid offset-aware timestamp") from exc


def day(value, label):
    require(isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value),
            f"{label}: YYYY-MM-DD required")
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError(f"{label}: invalid date") from exc


def validate_definition(definition):
    require(definition.get("schema_version") == DEFINITION_SCHEMA, "definition schema mismatch")
    safe(definition["definition_id"])
    start, end = day(definition.get("period_start"), "period_start"), day(
        definition.get("period_end"), "period_end")
    require(start <= end, "reversed period")
    cutoff = iso(definition.get("data_cutoff"), "data_cutoff")
    require(definition.get("mode") in {"FORWARD", "REPLAY"}, "mode required")
    require(definition.get("result_rule") == RESULT_RULE, "result_rule unsupported")
    require(definition.get("comparison") in {"ALL", "NON_MATCH"}, "comparison required")
    require(isinstance(definition.get("scope"), dict), "scope required")
    allowed = {"venue", "surface", "class", "going", "race_type"}
    scope = definition["scope"]
    require(set(scope).issubset(allowed | {"distance_min", "distance_max"}),
            "unknown race condition")
    for key, value in scope.items():
        if key.startswith("distance_"):
            require(type(value) is int and value > 0, "distance must be positive integer")
        else:
            require(isinstance(value, str) and value, "scope value required")
    if "distance_min" in scope and "distance_max" in scope:
        require(scope["distance_min"] <= scope["distance_max"], "distance limits reversed")
    groups = definition.get("groups")
    require(isinstance(groups, list) and groups, "one or more pedigree groups required")
    identifiers = set()
    for g in groups:
        require(isinstance(g, dict), "group must be object")
        ident = safe(g.get("group_id"))
        require(ident not in identifiers, "duplicate group_id")
        identifiers.add(ident)
        axis = g.get("axis")
        require(axis in AXES, "unsupported pedigree axis")
        value = g.get("value")
        require(isinstance(value, str) and value, "group value required")
        if axis in {"SIRE", "DAM_SIRE", "ANCESTOR", "CROSS"}:
            safe(value)
        if axis in {"ANCESTOR", "CROSS", "SIRE_LINE", "DAM_SIRE_LINE"}:
            require(type(g.get("depth")) is int and 1 <= g["depth"] <= 10,
                    "pedigree depth 1..10 required")
        if axis == "CROSS":
            require(type(g.get("min_paths")) is int and g["min_paths"] >= 2,
                    "cross min_paths >=2 required")
        if axis in {"SIRE_LINE", "DAM_SIRE_LINE"}:
            if "line_root_key" in g:
                safe(g["line_root_key"])
                require(value == g["line_root_key"], "line root/value mismatch")
                require(g.get("line_rule") == "exact-sire-chain-within-depth-v1",
                        "explicit line path rule required")
                require(g["depth"] >= (1 if axis == "SIRE_LINE" else 2),
                        "line depth shorter than subject path")
            else:
                require(isinstance(definition.get("taxonomy_version"), str) and
                        definition["taxonomy_version"], "line taxonomy_version required")
        if axis == "TRAINING_REGION":
            require(g.get("subject") in {"HORSE", "SIRE", "DAM_SIRE", "ANCESTOR"},
                    "training region requires explicit subject")
            if g["subject"] == "ANCESTOR":
                safe(g.get("ancestor_key"))
                require(type(g.get("depth")) is int and 1 <= g["depth"] <= 10,
                        "ancestor depth required")
            t = definition.get("training_classification")
            require(isinstance(t, dict) and t.get("version") and t.get("source") and
                    isinstance(t.get("regions"), dict) and t["regions"],
                    "explicit training-region classification required")
            require(value in t["regions"], "undefined training region")
            require(t.get("country_selection", "VERIFIED_COUNTRY") in
                    {"VERIFIED_COUNTRY", "MOST_STARTS_BY_TRAINING_COUNTRY",
                     "SEARCH_MATCH_PRIORITY_V1"},
                    "unsupported training country selection")
            require(all(isinstance(v, list) and v and
                        all(isinstance(x, str) and x for x in v)
                        for v in t["regions"].values()), "invalid training regions")
            require(iso(t.get("first_observed_at"), "training classification first_observed_at")
                    <= cutoff if definition["mode"] == "FORWARD" else True,
                    "future classification forbidden in FORWARD")
    return definition


def race_matches(race, definition):
    d = day(race.get("race_date_jst"), "race_date_jst")
    if not day(definition["period_start"], "period_start") <= d <= day(
            definition["period_end"], "period_end"):
        return False
    conditions = definition["scope"]
    if any(race.get(k) != v for k, v in conditions.items() if not k.startswith("distance_")):
        return False
    distance = race.get("distance_m")
    if "distance_min" in conditions and (type(distance) is not int or
                                          distance < conditions["distance_min"]):
        return False
    if "distance_max" in conditions and (type(distance) is not int or
                                          distance > conditions["distance_max"]):
        return False
    return True


def validate_manifest(manifest, definition):
    require(manifest.get("schema_version") == INPUT_SCHEMA, "runner manifest schema mismatch")
    require(manifest.get("source_scope") and isinstance(manifest["source_scope"], str),
            "source_scope required")
    require(type(manifest.get("all_runners_included")) is bool,
            "all_runners_included flag required")
    require(isinstance(manifest.get("races"), list), "races list required")
    rows, seen, duplicate_count, included_races = [], {}, 0, set()
    for race in manifest["races"]:
        require(isinstance(race, dict) and race.get("race_id") and race.get("race_date_jst"),
                "race ID/date required")
        day(race["race_date_jst"], "race date")
        if not race_matches(race, definition):
            continue
        require(race["race_id"] not in included_races, "duplicate race entry; merge runners first")
        included_races.add(race["race_id"])
        require(race.get("result_status") in {"OFFICIAL", "PENDING"},
                "official result status required")
        require(isinstance(race.get("official_source"), dict) and
                race["official_source"].get("record_key") and
                re.fullmatch("[0-9a-f]{64}",
                             race["official_source"].get("record_hash", "")),
                "official source record_key/hash required")
        obs = iso(race.get("result_observed_at"), "result_observed_at")
        if definition["mode"] == "FORWARD":
            require(obs <= iso(definition["data_cutoff"], "data_cutoff"),
                    "FORWARD cannot use results observed after cutoff")
            require(day(race["race_date_jst"], "race date") <=
                    iso(definition["data_cutoff"], "data_cutoff").date(),
                    "FORWARD cannot use future races")
        runners = race.get("runners")
        require(isinstance(runners, list) and runners,
                "all entered horses required; result winners alone are invalid")
        for runner in runners:
            require(isinstance(runner, dict) and
                    isinstance(runner.get("horse_key"), str), "horse_key required")
            safe(runner["horse_key"])
            status = runner.get("status")
            require(status in RESULT_STATES, "unsupported runner status")
            pos = runner.get("finish_position")
            require((type(pos) is int and pos > 0) if status == "FINISHED" else pos is None,
                    "FINISHED needs official finish_position; others require null")
            require(race["result_status"] == "OFFICIAL" or status == "PENDING" or
                    status in NON_START, "pending race cannot have settled runner")
            observed = iso(runner.get("entry_observed_at"), "entry observed")
            if definition["mode"] == "FORWARD":
                require(observed <= iso(definition["data_cutoff"], "data_cutoff"),
                        "FORWARD cannot use entries observed after cutoff")
            # Same horse/race may repeat identically in joined source exports.
            key = (race["race_id"], runner["horse_key"])
            signature = digest(runner)
            if key in seen:
                require(seen[key] == signature, "conflicting duplicate race/horse entry")
                duplicate_count += 1
                continue
            seen[key] = signature
            rows.append((race, runner))
    rows.sort(key=lambda item: (item[0]["race_date_jst"], item[0]["race_id"],
                                item[1]["horse_key"]))
    return rows, included_races, duplicate_count


def main_training_country(history, cutoff):
    """全出走の調教所属国で最多国を選ぶ。開催国・出生国は参照しない。"""
    if not isinstance(history, dict) or history.get("complete") is not True:
        return None, "TRAINING_START_HISTORY_INCOMPLETE"
    rows, total = history.get("starts"), history.get("total_starts")
    if not isinstance(rows, list) or type(total) is not int or total <= 0 or len(rows) != total:
        return None, "TRAINING_START_HISTORY_COUNT_MISMATCH"
    counts, seen = {}, set()
    for row in rows:
        if not isinstance(row, dict):
            return None, "TRAINING_START_HISTORY_INVALID"
        race, country, source = row.get("race_id"), row.get("training_country"), row.get("source")
        if not isinstance(race, str) or not race or race in seen:
            return None, "TRAINING_START_HISTORY_DUPLICATE_OR_MISSING_RACE"
        if not isinstance(country, str) or not re.fullmatch(r"[A-Z]{2}", country):
            return None, "TRAINING_START_COUNTRY_UNKNOWN"
        if not isinstance(source, dict) or not source.get("url") or not re.fullmatch(
                r"[a-f0-9]{64}", str(source.get("record_hash", ""))):
            return None, "TRAINING_START_SOURCE_MISSING"
        try:
            if day(row.get("race_date"), "training race date") > iso(cutoff, "cutoff").date():
                return None, "TRAINING_START_AFTER_CUTOFF"
            if iso(source.get("captured_at"), "training source capture") > iso(cutoff, "cutoff"):
                return None, "TRAINING_SOURCE_AFTER_CUTOFF"
        except ValueError:
            return None, "TRAINING_START_HISTORY_INVALID"
        seen.add(race)
        counts[country] = counts.get(country, 0) + 1
    winners = [c for c, n in counts.items() if n == max(counts.values())]
    if len(winners) != 1:
        return None, "MAIN_TRAINING_COUNTRY_TIED_USER_INPUT_REQUIRED"
    return winners[0], "VERIFIED_MOST_STARTS_TRAINING_COUNTRY"

 
def select_training_country(matches, cutoff):
    """検索で1国なら即決、複数国なら最終調教所属日が直近の国。未確認は推測しない。

    出走回数・開催国・生産国は使わない。情報の取得時点は個別に検証する。
    """
    if (not isinstance(matches, dict) or
            matches.get("schema_version") != "training-country-matches-v1" or
            matches.get("search_completed") is not True or
            not isinstance(matches.get("matches"), list)):
        return None, "TRAINING_COUNTRY_SEARCH_INCOMPLETE"
    rows = matches["matches"]
    if not rows:
        return None, "TRAINING_COUNTRY_USER_INPUT_REQUIRED"
    candidates = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("country"), str) or not re.fullmatch(
                r"[A-Z]{2}", row["country"]):
            return None, "TRAINING_COUNTRY_SEARCH_INVALID"
        source = row.get("source")
        if (not isinstance(source, dict) or not (source.get("url") or source.get("record_key")) or
                not re.fullmatch(r"[0-9a-f]{64}", str(source.get("record_hash", "")))):
            return None, "TRAINING_COUNTRY_MATCH_SOURCE_MISSING"
        try:
            if iso(source.get("captured_at"), "training match capture") > iso(cutoff, "cutoff"):
                return None, "TRAINING_COUNTRY_MATCH_AFTER_CUTOFF"
            last = (day(row["last_trained_on"], "training last date")
                    if row.get("last_trained_on") is not None else None)
            if last is not None and last > iso(cutoff, "cutoff").date():
                return None, "TRAINING_COUNTRY_DATE_AFTER_CUTOFF"
        except ValueError:
            return None, "TRAINING_COUNTRY_MATCH_INVALID_DATE"
        candidates.append((row["country"], last))
    countries = {country for country, _ in candidates}
    if len(countries) == 1:
        return next(iter(countries)), "VERIFIED_SINGLE_MATCH_TRAINING_COUNTRY"
    if any(last is None for _, last in candidates):
        return None, "TRAINING_COUNTRY_RECENT_DATE_REQUIRED"
    latest = max(last for _, last in candidates)
    latest_countries = {country for country, last in candidates if last == latest}
    if len(latest_countries) != 1:
        return None, "TRAINING_COUNTRY_LATEST_TIED_USER_INPUT_REQUIRED"
    return next(iter(latest_countries)), "VERIFIED_LATEST_MATCH_TRAINING_COUNTRY"


class Resolver:
    def __init__(self, registry, cutoff, definition):
        self.registry, self.cutoff, self.definition = registry, cutoff, definition
        self.cache = {}
        self.used = set()
        self.derived = {}

    def record(self, key):
        self.used.add(key)
        return read(self.registry.path(key))

    def late_capture(self, f):
        if f.get("status") != "VERIFIED":
            return False
        horse, revision = f.get("horse_key"), f.get("revision_id")
        r = self.record(horse) if horse else None
        found = next((rev for rev in r.get("revisions", [])
                      if rev.get("revision_id") == revision), None) if r else None
        # 事実の観測時刻だけではなく、実際の取得/確認時刻を確認する。
        return (found is None or
                iso(found.get("captured_at"), "pedigree capture") > iso(self.cutoff, "cutoff"))

    def fact(self, key, field):
        self.record(key)
        f = self.registry.fact(key, field, self.cutoff)
        if self.late_capture(f):
            return {"status": "UNVERIFIED", "reason": "CAPTURED_AFTER_CUTOFF"}
        if f.get("value") and field.startswith("parent:"):
            self.record(f["value"])
        return f

    def edge(self, key, path):
        self.record(key)
        # Include every intermediate record in the dependency fingerprint.
        for step in range(1, len(path) + 1):
            f = self.registry.edge(key, path[:step], self.cutoff)
            if self.late_capture(f):
                return {"status": "UNVERIFIED", "reason": "CAPTURED_AFTER_CUTOFF"}
            if f.get("value"):
                self.record(f["value"])
        return self.registry.edge(key, path, self.cutoff)

    def derive(self, key, ancestors, depth, taxonomy=None):
        # 同じ馬・世代・分類版の祖先条件は共通の完全展開を使う。
        # usedはall_groups内では単調増加し、馬を切り替える時にcacheも破棄する。
        cache_key = (key, depth, taxonomy)
        if cache_key in self.derived:
            result = self.derived[cache_key]
            if all(a in result['containment'] for a in ancestors):
                return result
        targets = set(ancestors)
        for group in self.definition['groups']:
            if group.get('depth') != depth:
                continue
            if group['axis'] in {'ANCESTOR', 'CROSS'}:
                targets.add(group['value'])
            elif group['axis'] == 'TRAINING_REGION' and group.get('subject') == 'ANCESTOR':
                targets.add(group['ancestor_key'])
            elif group['axis'] in {'SIRE_LINE', 'DAM_SIRE_LINE'} and group.get('line_root_key'):
                targets.add(group['line_root_key'])
        self.record(key)
        result = self.registry.derive(key, sorted(targets), depth, self.cutoff, taxonomy)
        result["blocked_late_capture"] = False
        for path, fact in result["derived_from"].items():
            if self.late_capture(fact):
                result["blocked_late_capture"] = True
            if fact.get("value"):
                self.record(fact["value"])
        self.derived[cache_key] = result
        return result

    @staticmethod
    def resolution(fact, target):
        status = fact["status"]
        if status == "VERIFIED":
            return ("MATCH" if fact["value"] == target else "NON_MATCH", "VERIFIED")
        return ("CONFLICT" if status == "CONFLICT" else "UNKNOWN", status)

    def classify(self, key, group):
        axis, target = group["axis"], group["value"]
        if axis in {"SIRE", "DAM_SIRE"}:
            return self.resolution(self.edge(key, "S" if axis == "SIRE" else "DS"), target)
        if axis in {"ANCESTOR", "CROSS"}:
            d = self.derive(key, [target], group["depth"])
            if d.get("blocked_late_capture"):
                return "UNKNOWN", "CAPTURED_AFTER_CUTOFF"
            c = d["containment"][target]
            if axis == "ANCESTOR":
                if c["status"] == "PRESENT":
                    return "MATCH", "VERIFIED"
                if c["status"] == "ABSENT_WITHIN_SCOPE":
                    return "NON_MATCH", "COMPLETE_ANCESTRY"
            elif len(c["positions"]) >= group["min_paths"]:
                return "MATCH", "VERIFIED"
            elif c["status"] == "ABSENT_WITHIN_SCOPE" or not d["missing"]:
                return "NON_MATCH", "COMPLETE_ANCESTRY"
            return ("CONFLICT" if any(m["status"] == "CONFLICT" for m in d["missing"])
                    else "UNKNOWN", "INCOMPLETE_ANCESTRY")
        if axis in {"SIRE_LINE", "DAM_SIRE_LINE"}:
            if group.get("line_root_key"):
                d = self.derive(key, [group["line_root_key"]], group["depth"])
                if d.get("blocked_late_capture"):
                    return "UNKNOWN", "CAPTURED_AFTER_CUTOFF"
                prefix = "S" if axis == "SIRE_LINE" else "DS"
                chain = [prefix + "S" * n for n in range(group["depth"] - len(prefix) + 1)]
                facts = [d["derived_from"].get(p, {"status": "UNVERIFIED"}) for p in chain]
                if any(f.get("status") == "VERIFIED" and f.get("value") == target for f in facts):
                    return "MATCH", "VERIFIED_EXACT_SIRE_CHAIN"
                if all(f.get("status") == "VERIFIED" for f in facts):
                    return "NON_MATCH", "COMPLETE_SIRE_CHAIN_WITHIN_SCOPE"
                return ("CONFLICT" if any(f.get("status") == "CONFLICT" for f in facts)
                        else "UNKNOWN", "INCOMPLETE_SIRE_CHAIN")
            d = self.derive(key, [], group["depth"], self.definition["taxonomy_version"])
            if d.get("blocked_late_capture"):
                return "UNKNOWN", "CAPTURED_AFTER_CUTOFF"
            obj = d["lines"].get("sire_line" if axis == "SIRE_LINE" else "dam_sire_line", {})
            if obj.get("status") != "VERIFIED":
                return "UNKNOWN", "LINE_NOT_VERIFIED"
            return ("MATCH" if obj["line"] == target else "NON_MATCH", "VERIFIED_TAXONOMY")
        # 調教地域: 生産国・父系・国籍・血統からの推定を厳禁。
        subject = group["subject"]
        if subject in {"SIRE", "DAM_SIRE"}:
            f = self.edge(key, "S" if subject == "SIRE" else "DS")
            if f["status"] != "VERIFIED":
                return ("CONFLICT" if f["status"] == "CONFLICT" else "UNKNOWN",
                        "TRAINING_SUBJECT_" + f["status"])
            subject = f["value"]
        elif subject == "ANCESTOR":
            d = self.derive(key, [group["ancestor_key"]], group["depth"])
            if d.get("blocked_late_capture"):
                return "UNKNOWN", "CAPTURED_AFTER_CUTOFF"
            c = d["containment"][group["ancestor_key"]]
            if c["status"] == "ABSENT_WITHIN_SCOPE":
                return "NON_MATCH", "ANCESTOR_NOT_PRESENT"
            if c["status"] != "PRESENT":
                return "UNKNOWN", "ANCESTOR_UNKNOWN"
            subject = group["ancestor_key"]
        method = self.definition["training_classification"].get(
            "country_selection", "VERIFIED_COUNTRY")
        subject_key = subject if subject != "HORSE" else key
        source_reason = "VERIFIED_TRAINING_REGION"
        if method == "SEARCH_MATCH_PRIORITY_V1":
            searched = self.fact(subject_key, "attribute:training_country_matches")
            if searched["status"] != "VERIFIED":
                return ("CONFLICT" if searched["status"] == "CONFLICT" else "UNKNOWN",
                        "TRAINING_COUNTRY_SEARCH_" + searched["status"])
            country, reason = select_training_country(searched["value"], self.cutoff)
            if reason in {"TRAINING_COUNTRY_USER_INPUT_REQUIRED",
                          "TRAINING_COUNTRY_RECENT_DATE_REQUIRED",
                          "TRAINING_COUNTRY_LATEST_TIED_USER_INPUT_REQUIRED"}:
                # 複数国の保留には今回の明示的な末尾国指定だけ適用する。
                answer = self.fact(subject_key, "attribute:training_country_user")
                if (answer["status"] == "VERIFIED" and isinstance(answer.get("source"), dict) and
                        answer["source"].get("source_class") == "USER_PROVIDED" and
                        (reason == "TRAINING_COUNTRY_USER_INPUT_REQUIRED" or
                         answer["source"].get("resolution_policy") in {
                             "USER_CONFIRMED_NAME_SUFFIX_V1", "USER_EXPLICIT_COUNTRY_V1"})):
                    country = answer["value"]
                    source_reason = "USER_PROVIDED_TRAINING_REGION"
                elif answer["status"] == "CONFLICT":
                    return "CONFLICT", "TRAINING_COUNTRY_USER_INPUT_CONFLICT"
            if country is None:
                return "UNKNOWN", reason
        else:
            field = ("attribute:training_start_history" if method ==
                     "MOST_STARTS_BY_TRAINING_COUNTRY" else "attribute:training_country")
            f = self.fact(subject_key, field)
            if f["status"] != "VERIFIED":
                return ("CONFLICT" if f["status"] == "CONFLICT" else "UNKNOWN",
                        "TRAINING_" + f["status"])
            if method == "MOST_STARTS_BY_TRAINING_COUNTRY":
                country, reason = main_training_country(f["value"], self.cutoff)
                if country is None:
                    return "UNKNOWN", reason
            else:
                country = f["value"]
        if not isinstance(country, str) or re.search("[,;/+]", country):
            return "UNKNOWN", "MULTI_REGION_CLASSIFICATION_UNDEFINED"
        lookup = self.definition["training_classification"]["regions"]
        mapped = [r for r, countries in lookup.items() if country in countries]
        if len(mapped) != 1:
            return ("UNKNOWN", "UNMAPPED_OR_AMBIGUOUS_TRAINING_COUNTRY")
        return ("MATCH" if mapped[0] == target else "NON_MATCH", source_reason)

    def as_of_dependency(self, key):
        original = read(self.registry.path(key))
        if original is None:
            return None
        active = self.registry.active(original.get("revisions", []), self.cutoff)
        identity = self.registry.identity_at(original, self.cutoff)
        if identity is None and not active:
            return None
        fingerprint = {"identity": identity, "active_revisions": active}
        return {
            "as_of_sha256": digest(fingerprint),
            "revision_ids": sorted(r["revision_id"] for r in active),
            "identity_status": identity.get("status") if identity else "UNCONFIRMED",
        }

    def all_groups(self, key, cached=None):
        if key in self.cache:
            return self.cache[key]
        if isinstance(cached, dict) and isinstance(cached.get("dependencies"), dict):
            # as-of依存馬・祖先レコードに変更がないものは高コストな系統展開を再利用。
            if all(self.as_of_dependency(dep) == signature
                   for dep, signature in cached["dependencies"].items()):
                self.cache[key] = cached
                return cached
        self.used = set()
        self.derived = {}
        # 未同定馬は血統・地域の「非該当」へ入れない。
        rec = self.record(key)
        identity = self.registry.identity_at(rec, self.cutoff) if rec else None
        if not identity or identity.get("status") != "RESOLVED":
            states = {g["group_id"]: {"status": "UNKNOWN", "reason": "IDENTITY_UNRESOLVED"}
                      for g in self.definition["groups"]}
        else:
            states = {}
            for g in self.definition["groups"]:
                status, reason = self.classify(key, g)
                states[g["group_id"]] = {"status": status, "reason": reason}
        # 将来の修正・未観測revisionを過去cutoffの依存hashへ逆流させない。
        dependencies = {item: self.as_of_dependency(item) for item in sorted(self.used)}
        value = {"groups": states, "dependencies": dependencies}
        self.cache[key] = value
        return value


def counters():
    return {"entries": 0, "horses": 0, "races": 0,
            "valid_starts": 0, "wins": 0, "top2": 0, "top3": 0,
            "scratched": 0, "excluded": 0, "pending_results": 0, "dnf": 0, "dq": 0}


def add(c, race, runner, valid):
    c["entries"] += 1
    status = runner["status"]
    if status == "SCRATCHED":
        c["scratched"] += 1
    elif status == "EXCLUDED":
        c["excluded"] += 1
    elif not valid:
        c["pending_results"] += 1
    else:
        c["valid_starts"] += 1
        if status == "DNF":
            c["dnf"] += 1
        elif status == "DQ":
            c["dq"] += 1
        else:
            pos = runner["finish_position"]
            for label, limit in (("wins", 1), ("top2", 2), ("top3", 3)):
                c[label] += int(pos <= limit)


def finish(c, horses, races):
    c["horses"] = len(horses)
    c["races"] = len(races)
    denom = c["valid_starts"]
    for name, numerator in (("win_rate", "wins"), ("top2_rate", "top2"), ("top3_rate", "top3")):
        c[name] = c[numerator] / denom if denom else None
    return c


def compute(definition, manifest, registry, input_hash, definition_hash, previous=None):
    validate_definition(definition)
    rows, race_set, duplicates = validate_manifest(manifest, definition)
    resolver = Resolver(registry, definition["data_cutoff"], definition)
    # 系統taxonomyの同一version書き換えも差分判定に含める。
    lineage = definition.get("taxonomy_version")
    tax = read(registry.root / "taxonomies" / (safe(lineage) + ".json")) if lineage else None
    lineage_hash = digest(tax)
    compatible = bool(previous and previous.get("data_cutoff") == definition["data_cutoff"] and
                      previous.get("classification_version") == lineage and
                      previous.get("lineage_taxonomy_hash") == lineage_hash and
                      previous.get("training_classification_hash") ==
                      digest(definition.get("training_classification")) and
                      {k: v["definition"] for k, v in previous.get("groups", {}).items()} ==
                      {g["group_id"]: g for g in definition["groups"]})
    past = previous["horse_trace"] if compatible else {}
    groups = {}
    for g in definition["groups"]:
        groups[g["group_id"]] = {
            "definition": g, "cohorts": {s: counters() for s in
                                        ("MATCH", "NON_MATCH", "UNKNOWN", "CONFLICT")},
            "reason_counts": {}, "comparison": definition["comparison"],
        }
    total = counters()
    horses_all, races_all = set(), set()
    counts = {id(g): {st: (set(), set()) for st in
                      ("MATCH", "NON_MATCH", "UNKNOWN", "CONFLICT")}
              for g in groups.values()}
    whole_trace = {}
    for race, runner in rows:
        key = runner["horse_key"]
        result_valid = race["result_status"] == "OFFICIAL" and (
            runner["status"] not in NON_START | {"PENDING"})
        add(total, race, runner, result_valid)
        horses_all.add(key)
        races_all.add(race["race_id"])
        if key not in whole_trace:
            whole_trace[key] = resolver.all_groups(key, cached=past.get(key))
        for gid, group in groups.items():
            cls = whole_trace[key]["groups"][gid]
            status = cls["status"]
            c = group["cohorts"][status]
            add(c, race, runner, result_valid)
            counts[id(group)][status][0].add(key)
            counts[id(group)][status][1].add(race["race_id"])
            reason = cls["reason"]
            if status in UNRESOLVED:
                group["reason_counts"][reason] = group["reason_counts"].get(reason, 0) + 1
    finish(total, horses_all, races_all)
    missing = []
    if not manifest["all_runners_included"]:
        missing.append({"type": "INCOMPLETE_RACE_SCOPE", "reason": "all_runners_included=false"})
    if not rows:
        missing.append({"type": "NO_MATCHED_RACES", "reason": "no valid scope rows"})
    if total["pending_results"]:
        missing.append({"type": "RESULT_COVERAGE_INCOMPLETE",
                        "entries": total["pending_results"]})
    for gid, group in groups.items():
        for state, c in group["cohorts"].items():
            h, r = counts[id(group)][state]
            finish(c, h, r)
        known = sum(group["cohorts"][st]["entries"] for st in ("MATCH", "NON_MATCH"))
        eligible = group["cohorts"]["MATCH"]["entries"]
        group["coverage"] = {
            "pedigree_known": known,
            "pedigree_unknown": group["cohorts"]["UNKNOWN"]["entries"],
            "pedigree_conflict": group["cohorts"]["CONFLICT"]["entries"],
            "pedigree_coverage": known / total["entries"] if total["entries"] else None,
            "result_coverage": (
                group["cohorts"]["MATCH"]["valid_starts"] / eligible if eligible else None),
        }
        for state in ("UNKNOWN", "CONFLICT"):
            if group["cohorts"][state]["entries"]:
                missing.append({"type": "PEDIGREE_" + state, "group_id": gid,
                                "entries": group["cohorts"][state]["entries"],
                                "reasons": group["reason_counts"]})
        if group["cohorts"]["MATCH"]["pending_results"]:
            missing.append({"type": "RESULT_PENDING", "group_id": gid,
                            "entries": group["cohorts"]["MATCH"]["pending_results"]})
        group["baseline"] = total if definition["comparison"] == "ALL" else group["cohorts"]["NON_MATCH"]
        group["overlap_note"] = "Groups may overlap; sum of group counts is not an all-runners total"
    classification_hash = digest(definition.get("training_classification"))
    record = {
        "schema_version": SNAPSHOT_SCHEMA, "calculator_version": CALCULATOR,
        "result_rule": RESULT_RULE,
        "definition_id": definition["definition_id"],
        "definition_hash": definition_hash, "input_hash": input_hash,
        "mode": definition["mode"], "production_eligible": False,
        "usage": "RESEARCH_SHADOW_ONLY",
        "period_start": definition["period_start"], "period_end": definition["period_end"],
        "data_cutoff": definition["data_cutoff"],
        "source_scope": manifest["source_scope"],
        "scope_complete": manifest["all_runners_included"],
        "classification_version": definition.get("taxonomy_version"),
        "lineage_taxonomy_hash": lineage_hash,
        "training_classification_hash": classification_hash,
        "all_runners": total, "races_in_scope": sorted(race_set),
        "duplicates_removed": duplicates, "groups": groups,
        "horse_trace": whole_trace, "missing": missing,
        "completeness": "COMPLETE" if not missing else "PARTIAL",
    }
    record["content_sha256"] = digest(record)
    return record


def bounded(root, relative, prefix):
    rel = Path(relative)
    require(not rel.is_absolute() and ".." not in rel.parts and
            str(rel).startswith(prefix) and str(rel) != prefix,
            f"path outside {prefix}")
    full = root / rel
    require(full.resolve().is_relative_to(root.resolve()), "path escapes repository")
    return full


def freeze_input(root, obj, kind):
    """結果訂正後も旧snapshotの入力を再現できる内容アドレス保存。"""
    key = digest(obj)
    relative = f"data/condition_stats/{kind}/archive/{key}.json"
    path = root / relative
    if path.exists():
        require(read_object(path) == obj, "immutable input archive changed")
    else:
        atomic(path, obj)
    require(read_object(path) == obj, "input archive readback mismatch")
    return relative, filehash(path)


def run(root, definition_path, input_path, previous_path=None):
    root = Path(root)
    definition_file = bounded(root, definition_path, "data/condition_stats/definitions/")
    input_file = bounded(root, input_path, "data/condition_stats/inputs/")
    definition, manifest = read_object(definition_file), read_object(input_file)
    validate_definition(definition)
    # 元入力を上書きして訂正しても、旧版は固定入力へ再現できる。
    definition_archive, definition_hash = freeze_input(root, definition, "definitions")
    input_archive, input_hash = freeze_input(root, manifest, "inputs")
    previous = None
    if previous_path is not None:
        previous = verify(root, bounded(root, previous_path,
                                        "data/condition_stats/snapshots/"))
        require(previous["definition_id"] == definition["definition_id"],
                "previous snapshot definition_id mismatch")
    record = compute(definition, manifest, Registry(root / "data/pedigree"),
                     input_hash, definition_hash, previous=previous)
    record["definition_path"] = definition_archive
    record["input_path"] = input_archive
    record["requested_definition_path"] = str(definition_path)
    record["requested_input_path"] = str(input_path)
    record["content_sha256"] = digest({k: v for k, v in record.items()
                                        if k != "content_sha256"})
    dest = root / "data/condition_stats/snapshots" / safe(definition["definition_id"]) / (
        record["content_sha256"] + ".json")
    if dest.exists():
        require(read_object(dest) == record, "snapshot hash collision or overwrite")
    else:
        # condition_stat_snapshotのGit準備形式。入力事実は複製せず参照/hash固定。
        atomic(dest, record)
    require(read_object(dest) == record, "snapshot readback mismatch")
    return dest, record


def verify(root, path):
    root = Path(root).resolve()
    location = Path(path).resolve()
    require(location.is_relative_to((root / "data/condition_stats/snapshots").resolve()),
            "snapshot outside condition_stat_snapshot directory")
    obj = read_object(location)
    require(obj.get("schema_version") == SNAPSHOT_SCHEMA and
            obj.get("calculator_version") == CALCULATOR and
            obj.get("production_eligible") is False and
            obj.get("usage") == "RESEARCH_SHADOW_ONLY", "unexpected snapshot contract")
    key = obj.get("content_sha256")
    require(isinstance(key, str) and re.fullmatch("[0-9a-f]{64}", key) and
            digest({k: v for k, v in obj.items() if k != "content_sha256"}) == key,
            "snapshot content hash mismatch")
    require(location.name == key + ".json" and
            location.parent.name == safe(obj["definition_id"]), "snapshot filename/id mismatch")
    for link, prefix, field in (
        ("definition_path", "data/condition_stats/definitions/", "definition_hash"),
        ("input_path", "data/condition_stats/inputs/", "input_hash")):
        target = bounded(root, obj.get(link), prefix)
        require(target.is_file() and filehash(target) == obj.get(field),
                f"snapshot {link} missing or changed: pin original input")
    # Registry revisions are embedded as hashes in horse_trace so old snapshots
    # remain valid after future revisions; do not re-read latest pedigree here.
    require(obj.get("mode") in {"REPLAY", "FORWARD"} and
            obj.get("completeness") in {"COMPLETE", "PARTIAL"},
            "mode/completeness required")
    return obj


def audit(root):
    root = Path(root)
    base = root / "data/condition_stats"
    errors, validated = [], []
    snapshots = sorted((base / "snapshots").glob("*/*.json"))
    for path in snapshots:
        try:
            validated.append(verify(root, path))
        except (ValueError, KeyError, TypeError, OSError) as exc:
            errors.append(f"{path}: {exc}")
    # snapshotのみ検査すると、宣言後に一件も実行しない欠落を見逃す。
    for definition in sorted((base / "definitions").glob("*.json")):
        rel = definition.relative_to(root).as_posix()
        try:
            current = read_object(definition)
            validate_definition(current)
            current_hash = digest(current)
            matches = [r for r in validated if r.get("requested_definition_path") == rel]
            require(any(r.get("definition_id") == current["definition_id"] and
                        digest(read_object(root / r["definition_path"])) == current_hash
                        for r in matches), "definition has no matching current snapshot")
        except (ValueError, KeyError, TypeError, OSError) as exc:
            errors.append(f"{definition}: {exc}")
    for input_file in sorted((base / "inputs").glob("*.json")):
        rel = input_file.relative_to(root).as_posix()
        try:
            input_hash = digest(read_object(input_file))
            matching = [r for r in validated if r.get("requested_input_path") == rel]
            require(any(digest(read_object(root / r["input_path"])) == input_hash
                        for r in matching), "runner manifest has no matching current snapshot")
        except (ValueError, KeyError, TypeError, OSError) as exc:
            errors.append(f"{input_file}: {exc}")
    for error in errors:
        print(f"PEDIGREE_STAT_INCOMPLETE {error}")
    print(f"PEDIGREE_STAT_AUDIT: snapshots={len(snapshots)} invalid={len(errors)}")
    return not errors


def inventory(root):
    """legacy候補と確認済み事実の棚卸し。履歴候補は昇格しない。"""
    registry = Registry(root / "data/pedigree")
    source = read(registry.root / "migration.json")
    require(isinstance(source, dict) and source.get("schema_version") ==
            "pedigree-registry-v1", "pedigree migration manifest required")
    claims = source.get("claims")
    require(isinstance(claims, list) and source.get("extracted") == len(claims),
            "legacy migration counts mismatch")
    by_kind, by_status, files = {}, {}, set()
    for claim in claims:
        require(claim.get("status") == "UNVERIFIED" and
                claim.get("identity_status") == "IDENTITY_UNRESOLVED",
                "legacy candidates may not be automatically promoted")
        files.add(claim["path"])
        for component in claim["components"]:
            kind = component["kind"]
            by_kind[kind] = by_kind.get(kind, 0) + 1
            status = component["status"]
            by_status[status] = by_status.get(status, 0) + 1
            require(status == "UNVERIFIED", "legacy component wrongly promoted")
    known = registry.records()
    return {
        "schema_version": "pedigree-stat-inventory-v1",
        "source": "data/pedigree/migration.json",
        "source_sha256": filehash(registry.root / "migration.json"),
        "source_commit": source.get("commit"),
        "candidate_claims": len(claims),
        "candidate_components": sum(by_kind.values()),
        "candidate_by_kind": by_kind,
        "candidate_by_status": by_status,
        "source_files": sorted(files),
        "unverified_claims": len(claims),
        "registered_horses": len(known),
        "resolved_horses": sum(r.get("identity", {}).get("status") == "RESOLVED" for r in known),
        "verified_facts": sum(sum(rev.get("status") == "VERIFIED"
                                   for rev in r.get("revisions", [])) for r in known),
        "source_verification_complete": len(claims) == 0,
        "stats_source_ready": False,
        "status": "UNVERIFIED_CANDIDATES_REMAIN" if claims else "CANDIDATES_REVIEWED",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    task = parser.add_mutually_exclusive_group(required=True)
    task.add_argument("--run", metavar="DEFINITION_PATH")
    task.add_argument("--verify", metavar="SNAPSHOT_PATH")
    task.add_argument("--audit", action="store_true")
    task.add_argument("--inventory", action="store_true")
    parser.add_argument("--input", help="versioned full-field official runners manifest")
    parser.add_argument("--previous", help="previous immutable snapshot; reuse unchanged pedigree traces")
    args = parser.parse_args()
    try:
        if args.audit:
            return 0 if audit(args.root) else 1
        if args.inventory:
            print(json.dumps(inventory(args.root), ensure_ascii=False, indent=2))
            return 0
        if args.verify:
            obj = verify(args.root, args.root / args.verify)
            print(json.dumps({"status": "VERIFIED", "snapshot_hash": obj["content_sha256"],
                              "completeness": obj["completeness"]}, ensure_ascii=False))
            return 0
        require(args.input, "--run requires --input")
        path, obj = run(args.root, args.run, args.input, previous_path=args.previous)
        print(json.dumps({"snapshot": str(path), "sha256": obj["content_sha256"],
                          "status": obj["completeness"], "starts": obj["all_runners"]["valid_starts"],
                          "missing": obj["missing"]}, ensure_ascii=False))
        return 0
    except (ValueError, KeyError, TypeError, OSError) as exc:
        print(f"PEDIGREE_STAT_INCOMPLETE: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

