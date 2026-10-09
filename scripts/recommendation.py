#!/usr/bin/env python3
"""次期オッズ非依存推奨買い目: 生成・独立検証・保存監査・的中照合。

PR68 §25に基づく次期候補。現行v1.6.1/旧v2のProduction判定は変更しない。
"""
import argparse
import hashlib
import itertools
import json
import re
import sys
from datetime import datetime
from pathlib import Path

from check_prediction_compliance import ComplianceError, iso, receipt_records

SCHEMA = "recommendation-snapshot-v1"
CONTRACT = "odds-free-recommendation-v1"
GATE_SCHEMA = "recommendation-compliance-v1"
INTENT_SCHEMA = "recommendation-persistence-intent-v1"
TYPES = {"WIN": 1, "PLACE": 1, "QUINELLA": 2, "WIDE": 2,
         "EXACTA": 2, "TRIO": 3, "TRIFECTA": 3}
UNORDERED = {"QUINELLA", "WIDE", "TRIO"}
STATES = {"RECOMMENDED", "NO_RECOMMENDATION", "EXPLICIT_MARKS_ONLY", "PENDING"}
FORBIDDEN = {"odds", "expected_value", "ev_low", "popularity", "stake",
             "amount_yen", "total_stake_yen", "purchase", "payout", "roi",
             "budget", "purchase_status", "betting"}

def require(cond, message):
    if not cond:
        raise ComplianceError(message)

def read_json(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    require(isinstance(data, dict), f"{path}: JSON object required")
    return data

def relative(root, path, prefix):
    value = Path(path)
    require(not value.is_absolute() and ".." not in value.parts and
            str(value).startswith(prefix) and str(value) != prefix,
            f"invalid artifact path: {path}")
    full = root / value
    require(full.resolve().is_relative_to(root.resolve()), f"path escapes root: {path}")
    return full

def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def ticket_key(ticket):
    kind = ticket.get("type")
    horses = ticket.get("horses")
    require(kind in TYPES, f"unsupported bet type: {kind}")
    require(isinstance(horses, list) and len(horses) == TYPES[kind] and
            all(type(x) is int and x > 0 for x in horses) and
            len(set(horses)) == len(horses), f"{kind}: invalid horse numbers")
    return kind, tuple(sorted(horses)) if kind in UNORDERED else tuple(horses)

def forbidden_keys(obj):
    if isinstance(obj, dict):
        for key, value in obj.items():
            require(key not in FORBIDDEN, f"market/purchase field forbidden: {key}")
            forbidden_keys(value)
    elif isinstance(obj, list):
        for value in obj:
            forbidden_keys(value)

def prediction_link(root, rec):
    link = rec.get("prediction_ref")
    require(isinstance(link, dict), "prediction_ref required")
    path = relative(root, link.get("artifact_path", ""),
                    "docs/validation/snapshots/")
    require(path.is_file(), "prediction snapshot missing")
    require(sha256(path) == link.get("sha256"), "prediction hash mismatch")
    data = read_json(path)
    require(data.get("schema_version") == "prediction-snapshot-v2", "prediction schema mismatch")
    require(link.get("artifact_id") == data.get("snapshot_id") and
            link.get("baseline_forecast_id") == data.get("baseline_forecast_id"),
            "prediction reference ID mismatch")
    for field in ("race_id", "manual_release", "manual_ref_commit", "working_branch",
                  "scheduled_post_time_jst", "data_cutoff"):
        require(rec.get(field) == data.get(field), f"prediction {field} mismatch")
    require(iso(rec.get("fixed_at_jst"), "recommendation fixed_at") >=
            iso(data.get("fixed_at_jst"), "prediction fixed_at"),
            "recommendation predates prediction fixation")
    return data

def validate_snapshot(root, rec):
    require(rec.get("schema_version") == SCHEMA and rec.get("recommendation_contract") == CONTRACT,
            "recommendation contract/schema mismatch")
    forbidden_keys(rec)
    for name in ("recommendation_id", "race_id", "manual_release", "manual_ref_commit"):
        require(isinstance(rec.get(name), str) and rec[name], f"{name} required")
    require(rec["manual_release"] == "v1.7.0" and
            re.fullmatch(r"[0-9a-f]{40}", rec["manual_ref_commit"]) is not None,
            "unsupported release or manual commit")
    date = rec.get("race_date_jst")
    require(isinstance(date, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", date),
            "race_date_jst required")
    require(rec.get("working_branch") == f"prediction/{date}", "wrong working branch")
    cutoff = iso(rec.get("data_cutoff"), "data_cutoff")
    post = iso(rec.get("scheduled_post_time_jst"), "scheduled_post_time_jst")
    fixed = iso(rec.get("fixed_at_jst"), "fixed_at_jst")
    require(cutoff < post and fixed < post, "recommendation must be fixed before post")
    revision = rec.get("revision")
    require(type(revision) is int and revision >= 1, "revision must be positive int")
    if revision == 1:
        require(rec.get("supersedes") is None, "first revision cannot supersede")
    else:
        require(isinstance(rec.get("supersedes"), str) and rec["supersedes"] != rec["recommendation_id"],
                "later revision must reference previous recommendation")
    prediction = prediction_link(root, rec)
    ranking = prediction.get("ranking", [])
    require(isinstance(ranking, list) and len(ranking) >= 3, "prediction ranking required")
    anchor, opponent = ranking[:2]
    cancelled = rec.get("cancelled_horses", [])
    require(isinstance(cancelled, list) and len(set(cancelled)) == len(cancelled) and
            set(cancelled).issubset(set(ranking)), "invalid cancelled horses")
    require(rec.get("phase") in {"FINAL", "INITIAL_PROVISIONAL"}, "phase required")
    state = rec.get("status")
    require(state in STATES, "invalid recommendation status")
    reasons = rec.get("reason")
    require(isinstance(reasons, str), "reason required")
    tickets = rec.get("tickets", [])
    require(isinstance(tickets, list), "tickets must be list")
    main_types = rec.get("main_ticket_types", [])
    require(isinstance(main_types, list) and len(main_types) == len(set(main_types)) and
            all(x in TYPES for x in main_types) and len(main_types) <= 2,
            "main_ticket_types must have at most two distinct types")
    if state != "RECOMMENDED":
        require(not tickets and not main_types and bool(reasons.strip()),
                "non-recommendation requires reason and no tickets")
    else:
        require(tickets and main_types and bool(reasons.strip()),
                "RECOMMENDED requires tickets, main_ticket_types and reason")
    assessments = rec.get("horse_roles", [])
    require(isinstance(assessments, list), "horse_roles required")
    roles = {}
    evidence_items = prediction.get("evidence_items", [])
    for item in assessments:
        require(isinstance(item, dict), "horse_role object required")
        horse = item.get("horse_no")
        require(type(horse) is int and horse in ranking and horse not in roles,
                "horse_role invalid or duplicate")
        require(item.get("finish_role") in {"WIN", "TOP2", "TOP3"}, "finish_role invalid")
        for field in ("reason", "source_ref", "scenario_id"):
            require(isinstance(item.get(field), str) and item[field].strip(),
                    f"horse_role {field} required")
        require(iso(item.get("observed_at_jst"), "horse_role/observed_at_jst") <= cutoff,
                "horse_role uses future information")
        require(any(e.get("horse_no") == horse and e.get("source_ref") == item["source_ref"] and
                    e.get("observed_at_jst") <= rec["data_cutoff"] for e in evidence_items),
                "horse_role requires matching Production evidence (including △)")
        roles[horse] = item
    scenarios = rec.get("scenarios", [])
    require(isinstance(scenarios, list), "scenarios required")
    scenario_ids = set()
    for item in scenarios:
        require(isinstance(item, dict), "scenario object required")
        sid = item.get("scenario_id")
        require(isinstance(sid, str) and sid.strip() and sid not in scenario_ids,
                "scenario_id missing or duplicate")
        scenario_ids.add(sid)
        require(isinstance(item.get("description"), str) and item["description"].strip(),
                "scenario description required")
        require(item.get("probability_status") in {"NOT_CALCULATED", "CALCULATED"},
                "scenario probability_status required")
        if item["probability_status"] == "CALCULATED":
            lo, hi = item.get("probability_range", [None, None])
            require(all(type(x) in (float, int) and 0 <= x <= 1 for x in (lo, hi)) and lo <= hi
                    and isinstance(item.get("probability_method"), str) and item["probability_method"].strip(),
                    "calculated probability requires range and method")
        else:
            require("probability_range" not in item and "probability_method" not in item,
                    "uncalculated scenario cannot declare probability")
    keys = set()
    priorities = set()
    for item in tickets:
        require(isinstance(item, dict), "ticket object required")
        key = ticket_key(item)
        require(key not in keys, "duplicate ticket combination")
        keys.add(key)
        kind, horses = key
        require(kind in main_types, "ticket type missing from main_ticket_types")
        require(all(x in ranking and x not in cancelled for x in horses),
                "ticket contains non-runner or scratched horse")
        require(kind not in {"QUINELLA", "WIDE", "EXACTA"} or anchor in horses,
                "non-anchor pair/EXACTA is not allowed")
        for name in ("reason", "scenario_id"):
            require(isinstance(item.get(name), str) and item[name].strip(),
                    f"ticket {name} required")
        require(item["scenario_id"] in scenario_ids, "ticket scenario missing")
        rank = item.get("priority")
        require(type(rank) is int and rank > 0 and rank not in priorities,
                "ticket priority must be unique positive int")
        priorities.add(rank)
        require(all(h in roles for h in horses), "ticket lacks horse roles")
        if kind in {"WIN", "EXACTA", "TRIFECTA"}:
            require(roles[item["horses"][0]]["finish_role"] == "WIN",
                    "winner position requires WIN role")
        if kind in {"EXACTA", "TRIFECTA", "QUINELLA"}:
            targets = item["horses"][:2] if kind == "EXACTA" else (
                item["horses"][:2] if kind == "TRIFECTA" else item["horses"])
            require(all(roles[x]["finish_role"] in {"WIN", "TOP2"} for x in targets),
                    "top2 ticket contains a TOP3-only horse")
        require(all(roles[h]["scenario_id"] == item["scenario_id"] for h in horses),
                "ticket horse scenarios mismatch")
    require(priorities == set(range(1, len(tickets) + 1)), "ticket priority must be contiguous")
    require(rec.get("unique_ticket_count") == len(keys), "unique_ticket_count mismatch")
    require((set(main_types) == {t["type"] for t in tickets}) if tickets else not main_types,
            "main_ticket_types mismatch")
    if any(t["type"] in {"QUINELLA", "WIDE"} for t in tickets):
        for kind in ("QUINELLA", "WIDE"):
            if kind in main_types:
                require((kind, tuple(sorted((anchor, opponent)))) in keys,
                        f"{kind} must include ◎-○")
    dependency = rec.get("dependency_audit")
    require(isinstance(dependency, dict), "dependency_audit required")
    actual = "ALL" if tickets and all(anchor in t["horses"] for t in tickets) else (
        "PARTIAL" if any(anchor in t["horses"] for t in tickets) else "NONE")
    require(dependency.get("anchor_dependency") == actual, "anchor_dependency mismatch")
    if actual == "ALL":
        require(bool(dependency.get("lower_bound_review")) and bool(dependency.get("anchor_failure_scenario")),
                "100% anchor dependency requires lower-bound and failure review")
    require(isinstance(dependency.get("scenario_overlap_reason"), str) and
            dependency["scenario_overlap_reason"].strip(), "scenario overlap audit required")
    require(rec.get("unique_ticket_count") == len(tickets), "ticket count mismatch")
    return rec

def verify(root, gate_path):
    gate = read_json(gate_path)
    require(gate.get("schema_version") == GATE_SCHEMA, "recommendation gate schema mismatch")
    ident = gate.get("recommendation_id")
    date = gate.get("race_date_jst")
    require(isinstance(date, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", date) and
            isinstance(ident, str) and ident, "recommendation gate id/date required")
    link = gate.get("evidence_ref")
    require(isinstance(link, dict), "recommendation evidence_ref required")
    artifact = relative(root, link.get("artifact_path", ""), "docs/validation/recommendations/")
    require(artifact.is_file() and artifact.suffix == ".json", "recommendation artifact missing")
    require(sha256(artifact) == gate.get("content_sha256"), "recommendation snapshot hash mismatch")
    rec = validate_snapshot(root, read_json(artifact))
    # Production認証と推奨認証は別判定。ただし推奨は実在する認証済みPredictionを参照する。
    from check_prediction_compliance import validate_gate
    prediction_gate = root / "docs/validation/execution-gates" / date / (rec["race_id"] + ".json")
    require(prediction_gate.is_file(), "certified Production gate missing")
    pg = validate_gate(root, prediction_gate)
    require(pg.get("production", {}).get("evidence_ref", {}).get("artifact_id") ==
            rec["prediction_ref"]["artifact_id"], "Production evidence reference mismatch")
    require(rec["recommendation_id"] == ident and rec["race_date_jst"] == date and
            rec["race_id"] == gate.get("race_id") and
            rec["status"] == gate.get("status") and
            rec["prediction_ref"] == gate.get("prediction_ref"),
            "gate/recommendation content mismatch")
    require(link.get("artifact_id") == ident and
            link.get("timing_eligibility") == "PRE_RACE_ELIGIBLE", "evidence reference mismatch")
    intent_path = relative(root, gate.get("intent_path", ""),
                           "docs/validation/recommendation-intents/")
    intent = read_json(intent_path)
    require(intent_path.parent.name == date and
            intent.get("schema_version") == INTENT_SCHEMA and
            intent.get("race_date_jst") == date and
            intent.get("race_id") == rec["race_id"] and
            intent.get("recommendation_id") == ident and
            intent.get("artifact_path") == link["artifact_path"] and
            intent.get("prediction_ref") == rec["prediction_ref"] and
            intent.get("deadline_jst") == rec["scheduled_post_time_jst"],
            "recommendation was not properly predeclared")
    receipt_path = relative(root, link.get("receipt_path", ""),
                            "docs/validation/persistence-receipts/")
    require(receipt_path.is_file() and receipt_path.name == date + ".md",
            "recommendation receipt missing")
    receipts = [r for r in receipt_records(receipt_path)
                if r.get("receipt_id") == link.get("receipt_id")]
    require(len(receipts) == 1, "recommendation receipt must be unique")
    receipt = receipts[0]
    for name, val in (("artifact_id", ident), ("artifact_path", link["artifact_path"]),
                      ("scheduled_post_time_jst", rec["scheduled_post_time_jst"]),
                      ("timing_eligibility", "PRE_RACE_ELIGIBLE"),
                      ("artifact_persist_status", "PERSIST_VERIFIED"),
                      ("receipt_persist_status", "RECEIPT_VERIFIED")):
        require(receipt.get(name) == val, f"recommendation receipt {name} mismatch")
    post = iso(rec["scheduled_post_time_jst"], "post")
    for name in ("persist_verified_at_jst", "receipt_verified_at_jst"):
        require(iso(receipt.get(name), name) < post, f"recommendation {name} must be before post")
    require(link.get("persist_verified_at_jst") == receipt.get("persist_verified_at_jst"),
            "recommendation receipt timestamp mismatch")
    if gate.get("kpi_eligibility") == "ELIGIBLE":
        require(rec["status"] == "RECOMMENDED" and rec["phase"] == "FINAL",
                "only FINAL RECOMMENDED may be KPI eligible")
        require(gate.get("mode") == "FORWARD", "REPLAY cannot be forward KPI eligible")
    else:
        require(gate.get("kpi_eligibility") in {"INELIGIBLE", "PENDING", "NOT_APPLICABLE"},
                "invalid recommendation eligibility")
    return rec


def ref_for_prediction(root, path):
    pred_path = relative(root, path, "docs/validation/snapshots/")
    pred = read_json(pred_path)
    require(pred.get("schema_version") == "prediction-snapshot-v2", "prediction v2 required")
    return {
        "artifact_path": str(path),
        "artifact_id": pred["snapshot_id"],
        "sha256": sha256(pred_path),
        "baseline_forecast_id": pred["baseline_forecast_id"],
    }

def prepare(root, prediction_path, rec_id, artifact_path, intent_id):
    require(re.fullmatch(r"[a-zA-Z0-9_-]+", intent_id or "") is not None,
            "valid intent ID required")
    prediction = read_json(relative(root, prediction_path, "docs/validation/snapshots/"))
    date = prediction.get("scheduled_post_time_jst", "")[:10]
    require(date and rec_id, "race date and recommendation ID required")
    now = datetime.now(iso(prediction["scheduled_post_time_jst"], "post").tzinfo)
    require(now < iso(prediction["scheduled_post_time_jst"], "post"),
            "cannot prepare intent after post time")
    artifact = relative(root, artifact_path, "docs/validation/recommendations/")
    require(artifact.parent.name == date and artifact.suffix == ".json", "recommendation path/date invalid")
    intent = {
        "schema_version": INTENT_SCHEMA, "race_date_jst": date,
        "race_id": prediction["race_id"], "recommendation_id": rec_id,
        "artifact_path": artifact_path, "prediction_ref": ref_for_prediction(root, prediction_path),
        "deadline_jst": prediction["scheduled_post_time_jst"],
    }
    path = root / "docs/validation/recommendation-intents" / date / (intent_id + ".json")
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(intent, ensure_ascii=False, indent=2) + "\n"
    if path.exists():
        require(path.read_text(encoding="utf-8") == content, "existing intent differs")
    else:
        path.write_text(content, encoding="utf-8")
    return path

def seal(root, rec_path, intent_id, receipt_id):
    path = relative(root, rec_path, "docs/validation/recommendations/")
    rec = validate_snapshot(root, read_json(path))
    date = rec["race_date_jst"]
    intent_path = f"docs/validation/recommendation-intents/{date}/{intent_id}.json"
    intent = read_json(root / intent_path)
    require(intent.get("recommendation_id") == rec["recommendation_id"] and
            intent.get("artifact_path") == rec_path and
            intent.get("prediction_ref") == rec["prediction_ref"],
            "recommendation does not match prior intent")
    receipt_path = f"docs/validation/persistence-receipts/{date}.md"
    receipts = receipt_records(root / receipt_path)
    matches = [r for r in receipts if r.get("receipt_id") == receipt_id]
    require(len(matches) == 1, "verified receipt required")
    record = matches[0]
    gate = {
        "schema_version": GATE_SCHEMA, "race_id": rec["race_id"],
        "race_date_jst": date, "recommendation_id": rec["recommendation_id"],
        "status": rec["status"], "prediction_ref": rec["prediction_ref"],
        "content_sha256": sha256(path), "intent_path": intent_path,
        "mode": "FORWARD",
        "kpi_eligibility": "ELIGIBLE" if rec["status"] == "RECOMMENDED" and rec["phase"] == "FINAL" else "INELIGIBLE",
        "evidence_ref": {
            "artifact_id": rec["recommendation_id"], "artifact_path": rec_path,
            "receipt_path": receipt_path, "receipt_id": receipt_id,
            "timing_eligibility": "PRE_RACE_ELIGIBLE",
            "persist_verified_at_jst": record.get("persist_verified_at_jst"),
        },
    }
    gate_path = root / "docs/validation/recommendation-gates" / date / (rec["race_id"] + ".json")
    require(not gate_path.exists(), "recommendation gate already exists; do not overwrite history")
    gate_path.parent.mkdir(parents=True, exist_ok=True)
    gate_path.write_text(json.dumps(gate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    try:
        verify(root, gate_path)
    except Exception:
        gate_path.unlink()
        raise
    return gate_path

def audit(root):
    base = root / "docs/validation"
    intents = {p.relative_to(base).as_posix(): p for p in
               (base / "recommendation-intents").glob("*/*.json")}
    snapshots = {p.relative_to(root).as_posix(): p for p in
                 (base / "recommendations").glob("*/*.json")}
    gates = sorted((base / "recommendation-gates").glob("*/*.json"))
    used_intents, used_snapshots = set(), set()
    errors = []
    for path in gates:
        try:
            data = read_json(path)
            rec = verify(root, path)
            used_intents.add(data["intent_path"].removeprefix("docs/validation/"))
            used_snapshots.add(data["evidence_ref"]["artifact_path"])
            require(path.parent.name == rec["race_date_jst"], "recommendation gate date/path mismatch")
            require(data.get("race_id") == path.stem, "recommendation gate race/path mismatch")
            print(f"RECOMMENDATION_VERIFIED {path}: {rec['status']}")
        except (ComplianceError, OSError, ValueError, TypeError, KeyError) as exc:
            errors.append(f"{path}: {exc}")
    for path in sorted(set(intents) - used_intents):
        errors.append(f"unregistered recommendation intent: {path}")
    for path in sorted(set(snapshots) - used_snapshots):
        errors.append(f"unregistered recommendation snapshot: {path}")
    # 次期推奨契約の発効日以降は、Prediction gateに対応する推奨gateの欠落も検出する。
    state_path = base / "execution-gates/contract-state.json"
    if state_path.is_file():
        state = read_json(state_path)
        effective = state.get("recommendation_effective_race_date")
        if state.get("status") == "ACTIVE" and effective:
            for prediction_gate in (base / "execution-gates").glob("*/*.json"):
                if prediction_gate.parent.name < effective:
                    continue
                data = read_json(prediction_gate)
                if data.get("schema_version") != "prediction-compliance-v2":
                    continue
                expected = base / "recommendation-gates" / prediction_gate.parent.name / prediction_gate.name
                if not expected.is_file():
                    errors.append(f"missing recommendation gate for {prediction_gate}")
    for error in errors:
        print(f"RECOMMENDATION_INCOMPLETE {error}")
    print(f"RECOMMENDATION_AUDIT: gates={len(gates)} incomplete={len(errors)}")
    return not errors

def settle(rec, result):
    """払戻・購入情報なしで公式着順と券の一致のみ判定。結果未確定は保留。"""
    if result.get("status") != "OFFICIAL":
        return {"status": "PENDING", "tickets": []}
    groups = result.get("finish_groups")
    require(isinstance(groups, list) and groups and all(
        isinstance(g, list) and g and all(type(h) is int and h > 0 for h in g)
        for g in groups), "finish_groups required")
    horses = [h for g in groups for h in g]
    require(len(horses) == len(set(horses)), "finish_groups duplicate horse")
    scratched = result.get("scratched_horses", [])
    require(isinstance(scratched, list) and len(scratched) == len(set(scratched)),
            "scratched_horses invalid")
    place_places = result.get("place_places")
    require(place_places in (2, 3), "place_places must be 2 or 3 (field-size rule)")
    permutations = [()]
    for group in groups:
        permutations = [p + q for p in permutations for q in itertools.permutations(group)]
    outcomes = []
    for ticket in rec["tickets"]:
        kind, members = ticket_key(ticket)
        if any(h in scratched for h in members):
            state = "INVALID"
        else:
            hit = False
            for order in permutations:
                first = order[:1]
                top2 = set(order[:2])
                top3 = set(order[:3])
                checked = {
                    "WIN": tuple(first) == members,
                    "PLACE": members[0] in order[:place_places],
                    "QUINELLA": set(members) == top2,
                    "WIDE": set(members).issubset(top3),
                    "EXACTA": tuple(order[:2]) == members,
                    "TRIO": set(members) == top3,
                    "TRIFECTA": tuple(order[:3]) == members,
                }
                if checked[kind]:
                    hit = True
                    break
            state = "HIT" if hit else "MISS"
        outcomes.append({"type": kind, "horses": ticket["horses"], "result": state})
    valid = [o for o in outcomes if o["result"] != "INVALID"]
    return {"status": "SETTLED" if valid else "INVALID", "tickets": outcomes,
            "valid_tickets": len(valid),
            "hit_tickets": sum(t["result"] == "HIT" for t in valid),
            "race_hit": any(t["result"] == "HIT" for t in valid)}

def build(prediction, assessment, artifact_path):
    """構成選択は明示的な非価格シナリオ評価から決め、周辺確率の積は使わない。"""
    a = assessment
    anchor, opponent = prediction["ranking"][:2]
    role_items = a.get("horse_roles", [])
    by_horse = {v["horse_no"]: v for v in role_items}
    pair = a.get("joint_top3_scenario")
    top2 = a.get("joint_top2_scenario")
    win = a.get("anchor_win_scenario")
    stable = a.get("anchor_place_scenario")
    kind = None
    horses = []
    scenario = None
    if pair and all(h in by_horse for h in (anchor, opponent)):
        kind, horses, scenario = "WIDE", [anchor, opponent], pair
    elif top2 and all(h in by_horse for h in (anchor, opponent)) and all(
            by_horse[h]["finish_role"] in ("WIN", "TOP2") for h in (anchor, opponent)):
        kind, horses, scenario = "QUINELLA", [anchor, opponent], top2
    elif stable and anchor in by_horse:
        kind, horses, scenario = "PLACE", [anchor], stable
    elif win and anchor in by_horse and by_horse[anchor]["finish_role"] == "WIN":
        kind, horses, scenario = "WIN", [anchor], win
    reason = a.get("reason", "シナリオ根拠不足のため推奨なし")
    if kind:
        require(isinstance(reason, str) and reason.strip(), "assessment reason required")
    state = "RECOMMENDED" if kind else "NO_RECOMMENDATION"
    tickets = ([{"type": kind, "horses": horses, "priority": 1,
                 "scenario_id": scenario, "reason": reason}] if kind else [])
    link_path = Path(artifact_path)
    return {
        "schema_version": SCHEMA, "recommendation_contract": CONTRACT,
        "recommendation_id": a["recommendation_id"],
        "race_id": prediction["race_id"], "race_date_jst": a["race_date_jst"],
        "manual_release": prediction["manual_release"],
        "manual_ref_commit": prediction["manual_ref_commit"],
        "working_branch": prediction["working_branch"],
        "scheduled_post_time_jst": prediction["scheduled_post_time_jst"],
        "data_cutoff": prediction["data_cutoff"], "fixed_at_jst": a["fixed_at_jst"],
        "prediction_ref": {
            "artifact_path": str(link_path),
            "artifact_id": prediction["snapshot_id"],
            "sha256": sha256(link_path),
            "baseline_forecast_id": prediction["baseline_forecast_id"],
        },
        "revision": a.get("revision", 1), "supersedes": a.get("supersedes"),
        "phase": a.get("phase", "FINAL"),
        "status": state, "reason": reason,
        "cancelled_horses": a.get("cancelled_horses", []),
        "main_ticket_types": [kind] if kind else [],
        "tickets": tickets, "unique_ticket_count": len(tickets),
        "horse_roles": role_items, "scenarios": a.get("scenarios", []),
        "dependency_audit": a.get("dependency_audit", {
            "anchor_dependency": "ALL" if kind else "NONE",
            "lower_bound_review": a.get("lower_bound_review", ""),
            "anchor_failure_scenario": a.get("anchor_failure_scenario", ""),
            "scenario_overlap_reason": a.get("scenario_overlap_reason", "同一軸・同一シナリオの重なりを確認"),
        }),
    }

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--audit", action="store_true")
    group.add_argument("--verify", metavar="GATE_PATH")
    group.add_argument("--settle", metavar="RECOMMENDATION_PATH")
    group.add_argument("--generate", metavar="PREDICTION_PATH")
    group.add_argument("--prepare", metavar="PREDICTION_PATH")
    group.add_argument("--seal", metavar="RECOMMENDATION_PATH")
    parser.add_argument("--result", help="official result JSON for --settle")
    parser.add_argument("--assessment", help="non-market judgement JSON for --generate")
    parser.add_argument("--output", help="recommendation JSON output for --generate")
    parser.add_argument("--recommendation-id")
    parser.add_argument("--intent-id")
    parser.add_argument("--receipt-id")
    args = parser.parse_args()
    try:
        if args.audit:
            return 0 if audit(args.root) else 1
        if args.verify:
            rec = verify(args.root, args.root / args.verify)
            print(f"RECOMMENDATION_VERIFIED {rec['recommendation_id']} {rec['status']}")
            return 0
        if args.settle:
            require(bool(args.result), "--result required")
            rec = validate_snapshot(args.root, read_json(args.root / args.settle))
            print(json.dumps(settle(rec, read_json(args.root / args.result)), ensure_ascii=False, indent=2))
            return 0
        if args.prepare:
            require(bool(args.recommendation_id and args.output and args.intent_id),
                    "--prepare needs --recommendation-id, --output and --intent-id")
            path = prepare(args.root, args.prepare, args.recommendation_id, args.output, args.intent_id)
            print(f"RECOMMENDATION_INTENT_PREPARED {path}; commit/read back before generating")
            return 0
        if args.seal:
            require(bool(args.intent_id and args.receipt_id),
                    "--seal needs --intent-id and --receipt-id")
            path = seal(args.root, args.seal, args.intent_id, args.receipt_id)
            print(f"RECOMMENDATION_SEALED {path}")
            return 0
        require(bool(args.assessment) and bool(args.output and args.intent_id),
                "--generate requires --assessment, --output and --intent-id")
        prediction = read_json(args.root / args.generate)
        rec = build(prediction, read_json(args.root / args.assessment), args.generate)
        intent = read_json(args.root / "docs/validation/recommendation-intents" /
                           rec["race_date_jst"] / (args.intent_id + ".json"))
        require(intent.get("recommendation_id") == rec["recommendation_id"] and
                intent.get("artifact_path") == args.output and
                intent.get("prediction_ref") == rec["prediction_ref"],
                "generate must match predeclared intent")
        validate_snapshot(args.root, rec)
        dest = relative(args.root, args.output, "docs/validation/recommendations/")
        require(not dest.exists(), "cannot overwrite a fixed recommendation; create new revision")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(rec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"RECOMMENDATION_GENERATED {dest}; intent/receipt/gate verification still required")
        return 0
    except (ComplianceError, OSError, ValueError, TypeError, KeyError) as exc:
        print(f"RECOMMENDATION_INCOMPLETE: {exc}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
