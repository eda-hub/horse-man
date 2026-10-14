"""第4回顧：Owner必須項目・改訂履歴・独立分類の共通契約。

旧記録を遡及改変せず、予想/推奨の固定原本からのみ分類する。
"""
import hashlib
import json
from collections import Counter

from cycle04_operations import require, safe_path, verified_artifact

REVIEW_SCHEMA = "cycle04-review-v2"
REVISION_SCHEMA = "cycle04-review-revision-v1"
TARGETS = ("protected_good_parts", "revalidation_targets", "improvement_targets")
STATES = {"RECORDED", "NOT_APPLICABLE", "PENDING"}
CHANGE_STATES = {"PRE_RACE_CONFIRMED", "INSUFFICIENT", "PENDING"}


def review_hash(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":")).encode("utf-8")).hexdigest()


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def review_status(value):
    """共通検査：状態とOwner不足を返す。旧記録は成功を偽装せず読み取る。"""
    if not isinstance(value, dict):
        return {"state": "MISSING", "missing": ["review"]}
    if value.get("schema_version") != REVIEW_SCHEMA:
        missing = ["HISTORICAL_REVIEW_SCHEMA"]
        for name in ("error_classification", "non_degradation", "next_validation"):
            if not nonempty(value.get(name)):
                missing.append(name)
        for name in TARGETS:
            if not value.get(name):
                missing.append(name)
        return {"state": "LEGACY_INCOMPLETE", "missing": missing}
    require(value.get("state") in {"DRAFT", "COMPLETE"}, "review state must be DRAFT/COMPLETE")
    missing = []
    for name in ("error_classification", "non_degradation", "next_validation"):
        if not nonempty(value.get(name)):
            missing.append(name)
    for name in TARGETS:
        items = value.get(name)
        status = value.get(name + "_status")
        reason = value.get(name + "_reason")
        inputs = value.get(name + "_required_inputs")
        require(isinstance(items, list) and all(nonempty(v) for v in items)
                and len(items) == len(set(items)), name + " must be unique nonempty entries")
        require(status in STATES and nonempty(reason) and isinstance(inputs, list)
                and all(nonempty(x) for x in inputs), name + " state/reason/required_inputs invalid")
        require(not (status == "RECORDED" and (not items or inputs))
                and not (status == "NOT_APPLICABLE" and (items or inputs))
                and not (status == "PENDING" and (items or not inputs)),
                name + " items/state/required_inputs inconsistent")
        if status == "PENDING":
            missing.append(name + ":PENDING")
    changes = value.get("change_evidence")
    require(isinstance(changes, list), "review change_evidence list required")
    for evidence in changes:
        require(isinstance(evidence, dict) and evidence.get("status") in CHANGE_STATES
                and nonempty(evidence.get("reason")), "change evidence state/reason required")
        if evidence["status"] == "PENDING":
            require(isinstance(evidence.get("required_inputs"), list)
                    and bool(evidence["required_inputs"])
                    and all(nonempty(v) for v in evidence["required_inputs"]),
                    "pending change requires input names")
            missing.append("change_evidence:PENDING")
    if value["state"] == "COMPLETE":
        require(not missing, "COMPLETE review requires all Owner items: " + ", ".join(missing))
    return {"state": value["state"], "missing": missing}


def validate_revision_history(root, row, race, date, post):
    """reviewにだけ追記可能な独立履歴を検査。固定結果・予想には触れない。"""
    review = row.get("review")
    status = review_status(review)
    history = row.get("review_history")
    if history is None:
        require(status["state"] in {"LEGACY_INCOMPLETE", "MISSING"},
                "new review must have an immutable revision history")
        return status
    require(isinstance(history, list) and history, "review history required")
    previous = None
    for index, item in enumerate(history, 1):
        require(isinstance(item, dict) and item.get("revision") == index
                and item.get("previous_sha256") == previous,
                "review revision sequence/previous hash invalid")
        payload = item.get("review")
        review_status(payload)
        sha = review_hash(payload)
        require(sha == item.get("sha256"), "review revision hash mismatch")
        if index == 1:
            require(item.get("revision_ref") is None, "first review cannot impersonate amendment")
        else:
            ref = item.get("revision_ref")
            prefix = f"docs/validation/review-revisions/{date}/{race}/"
            require(isinstance(ref, dict) and set(ref) == {"artifact_path", "sha256"}
                    and ref["artifact_path"].startswith(prefix)
                    and ref["artifact_path"].endswith(".json"), "review revision fixed path/hash required")
            data = safe_path(root, ref["artifact_path"]).read_bytes()
            require(hashlib.sha256(data).hexdigest() == ref["sha256"], "review revision artifact hash mismatch")
            doc = json.loads(data)
            require(doc == {"schema_version": REVISION_SCHEMA, "race_date_jst": date,
                            "race_id": race, "revision": index, "supersedes_sha256": previous,
                            "review": payload},
                    "review revision artifact identity/chain mismatch")
        previous = sha
    require(history[-1]["review"] == review, "review latest/history mismatch")
    from check_prediction_compliance import validate_gate, iso
    frames = {p: [v for v in row.get("prediction_history", [])
                  if v.get("phase") == p] for p in ("INITIAL", "FINAL")}
    for evidence in review.get("change_evidence", []) if status["state"] != "LEGACY_INCOMPLETE" else []:
        for field in ("initial_gate_sha256", "final_gate_sha256",
                      "initial_baseline_forecast_id", "final_baseline_forecast_id",
                      "initial_cutoff", "final_cutoff"):
            require(nonempty(evidence.get(field)), "change evidence fixed binding required: " + field)
    if len(frames["INITIAL"]) == len(frames["FINAL"]) == 1:
        initial, final = frames["INITIAL"][0], frames["FINAL"][0]
        first = validate_gate(root, safe_path(root, initial["prediction_gate_path"]))
        last = validate_gate(root, safe_path(root, final["prediction_gate_path"]))
        changed = first["production"]["ranking"] != last["production"]["ranking"]
        evidence = (review or {}).get("change_evidence", [])
        matches = [v for v in evidence
                   if v.get("initial_gate_sha256") == initial["prediction_gate_sha256"]
                   and v.get("final_gate_sha256") == final["prediction_gate_sha256"]
                   and v.get("initial_baseline_forecast_id") == initial["baseline_forecast_id"]
                   and v.get("final_baseline_forecast_id") == final["baseline_forecast_id"]
                   and v.get("initial_cutoff") == first["data_cutoff"]
                   and v.get("final_cutoff") == last["data_cutoff"]]
        if status["state"] == "COMPLETE" and changed:
            require(len(matches) == 1, "changed fixed phases need one pinned change evidence")
        require(not evidence or len(matches) == len(evidence),
                "cross-race/phase/revision change evidence not allowed")
        for item in matches:
            if item["status"] == "PRE_RACE_CONFIRMED":
                ref = item.get("evidence_ref")
                payload, receipt = verified_artifact(root, ref, post)
                require(payload.get("race_id") == race and payload.get("race_date_jst") == date,
                        "fixed change evidence race/date mismatch")
                require(iso(receipt.get("receipt_verified_at_jst"), "change receipt")
                        <= iso(last["data_cutoff"], "last cutoff"),
                        "change evidence appeared after final cutoff")
    else:
        require(not review or not review.get("change_evidence"),
                "ambiguous INITIAL/FINAL revision cannot carry implicit change evidence")
    return status


def official_places(result):
    positions, place = {}, 1
    for group in result["finish_groups"]:
        for horse in group:
            require(horse not in positions, "duplicate official finisher")
            positions[horse] = place
        place += len(group)
    return positions


def coverage(targets):
    return {"target_ids": sorted(set(targets)), "eligible_ids": [],
            "included_ids": [], "missing": {}, "eligible_count": 0,
            "included_count": 0, "value": None}


def missing(cov, ident, reason, required):
    cov["missing"][ident] = {"reason": reason, "required_inputs": required}


def close_coverage(cov, numerator=None, denominator=None):
    cov["eligible_ids"] = sorted(set(cov["eligible_ids"]))
    cov["included_ids"] = sorted(set(cov["included_ids"]))
    cov["eligible_count"] = len(cov["eligible_ids"])
    cov["included_count"] = len(cov["included_ids"])
    if numerator is not None:
        cov["value"] = numerator / denominator if denominator else None
    return cov


def classify_ticket(ticket, position, anchor):
    """settleがMISSとした票だけを説明する。重複原因は消さない。"""
    kind, horses = ticket["type"], ticket["horses"]
    n = {"WIN": 1, "PLACE": 3, "QUINELLA": 2, "WIDE": 3,
         "EXACTA": 2, "TRIO": 3, "TRIFECTA": 3}[kind]
    top = {h for h, p in position.items() if p <= n}
    present = set(horses) & top
    labels = []
    if anchor in horses and anchor not in top:
        labels.append("AXIS_COLLAPSE")
    if kind in {"EXACTA", "TRIFECTA"} and set(horses) == top and [
            position.get(h) for h in horses] != list(range(1, n + 1)):
        labels.append("ORDER_MISMATCH")
    if kind in {"TRIO", "TRIFECTA"} and len(present) == 2:
        labels.append("THIRD_HORSE_MISSING")
    if kind in {"QUINELLA", "WIDE", "EXACTA", "TRIO", "TRIFECTA"} and len(present) < len(horses):
        labels.append("OPPONENT_MISSING")
    return labels or ["UNCLASSIFIED"]


def independent_metrics(root, days):
    """分母・欠測を伴う無印/事前変更/推奨失敗の追加集計。既存KPIは変更しない。"""
    from check_prediction_compliance import validate_gate
    from recommendation import verify as verify_recommendation
    races = [f"{day['race_date_jst']}:{race}" for day in days for race in day["initial_scope"]]
    unm = {phase: {"coverage": coverage(races), "horse_count": 0, "race_count": 0,
                   "first": 0, "second": 0, "top3": 0}
           for phase in ("INITIAL", "FINAL")}
    changes = {"coverage": coverage(races), "states": Counter(), "comparisons": []}
    recs = {"coverage": coverage(races), "unique_races": 0, "unique_tickets": 0,
            "miss_tickets": 0, "label_counts": Counter(), "labeled_tickets": [],
            "states_excluded": Counter()}
    for day in days:
        date = day["race_date_jst"]
        for race in day["initial_scope"]:
            ident = f"{date}:{race}"
            row = day["races"][race]
            result_ref = row.get("result_ref")
            result = json.loads(safe_path(root, result_ref["artifact_path"]).read_bytes()) if result_ref else None
            pos = official_places(result) if result else {}
            history = row.get("prediction_history", [])
            phases = {phase: [h for h in history if h.get("phase") == phase]
                      for phase in ("INITIAL", "FINAL")}
            for phase, rec in unm.items():
                cov = rec["coverage"]
                frames = phases[phase]
                if not result or not frames:
                    missing(cov, ident, "RESULT_OR_PHASE_MISSING", ["official_result", phase + "_fixed_gate"])
                    continue
                if len(frames) > 1:
                    missing(cov, ident, "AMBIGUOUS_PHASE_REVISIONS", [phase + "_revision_selection"])
                    continue
                gate = validate_gate(root, safe_path(root, frames[0]["prediction_gate_path"]))
                production = gate["production"]
                marks = production.get("marks")
                marked = ({marks.get("honmei"), marks.get("taikou"), marks.get("tanana")} |
                          set(marks.get("renka", []))) if isinstance(marks, dict) else None
                if marked is None or any(isinstance(v, bool) or type(v) is not int for v in marked):
                    missing(cov, ident, "FIXED_MARKS_MISSING", [phase + "_marks"])
                    continue
                if set(result.get("scratched_horses", [])) & set(production["ranking"]):
                    missing(cov, ident, "SCRATCHED_HORSE_IN_FIXED_SCOPE", ["comparable_fixed_phase"])
                    continue
                cov["eligible_ids"].append(ident)
                cov["included_ids"].append(ident)
                rec["race_count"] += 1
                for horse in set(production["ranking"]) - marked:
                    rec["horse_count"] += 1
                    rec["first"] += int(pos.get(horse) == 1)
                    rec["second"] += int(pos.get(horse) == 2)
                    rec["top3"] += int(pos.get(horse, 999) <= 3)
            change_cov = changes["coverage"]
            if not result or len(phases["INITIAL"]) != 1 or len(phases["FINAL"]) != 1:
                missing(change_cov, ident, "UNPAIRED_OR_AMBIGUOUS_FIXED_PHASES",
                        ["official_result", "single_initial_gate", "single_final_gate"])
            else:
                first, last = phases["INITIAL"][0], phases["FINAL"][0]
                old = validate_gate(root, safe_path(root, first["prediction_gate_path"]))
                new = validate_gate(root, safe_path(root, last["prediction_gate_path"]))
                if (set(result.get("scratched_horses", [])) & (set(old["production"]["ranking"]) |
                                                               set(new["production"]["ranking"]))):
                    missing(change_cov, ident, "SCRATCHED_PHASE_NOT_COMPARABLE", ["comparable_phase_revision"])
                else:
                    change_cov["eligible_ids"].append(ident)
                    if old["production"]["ranking"] == new["production"]["ranking"]:
                        change_cov["included_ids"].append(ident)
                        changes["states"]["UNCHANGED"] += 1
                    else:
                        evidence = (row.get("review") or {}).get("change_evidence", [])
                        matches = [v for v in evidence if v.get("initial_gate_sha256") == first["prediction_gate_sha256"]
                                   and v.get("final_gate_sha256") == last["prediction_gate_sha256"]
                                   and v.get("initial_baseline_forecast_id") == first["baseline_forecast_id"]
                                   and v.get("final_baseline_forecast_id") == last["baseline_forecast_id"]
                                   and v.get("initial_cutoff") == old["data_cutoff"]
                                   and v.get("final_cutoff") == new["data_cutoff"]]
                        if len(matches) != 1:
                            missing(change_cov, ident, "FIXED_CHANGE_EVIDENCE_MISSING", ["fixed_change_evidence"])
                        else:
                            e = matches[0]
                            if e["status"] == "PRE_RACE_CONFIRMED":
                                # 同一レースの真正な発走前receipt付き原本が無ければ算入しない。
                                try:
                                    payload, receipt = verified_artifact(
                                        root, e.get("evidence_ref"), row["scheduled_post_time_jst"])
                                    require(payload.get("race_id") == race
                                            and payload.get("race_date_jst") == date,
                                            "change evidence race mismatch")
                                except (ValueError, KeyError, TypeError, OSError) as exc:
                                    missing(change_cov, ident, str(exc), ["pre_race_evidence_receipt"])
                                    continue
                            change_cov["included_ids"].append(ident)
                            changes["states"][e["status"]] += 1
                            changes["comparisons"].append({"race_id": race, "race_date_jst": date,
                                "initial_gate_sha256": first["prediction_gate_sha256"],
                                "final_gate_sha256": last["prediction_gate_sha256"],
                                "status": e["status"], "reason": e["reason"]})
            rcov = recs["coverage"]
            status = row.get("recommendation_state", "PENDING")
            if status != "RECOMMENDED":
                recs["states_excluded"][status] += 1
                missing(rcov, ident, "NO_ELIGIBLE_FIXED_RECOMMENDATION",
                        ["RECOMMENDED_status", "fixed_recommendation_gate"])
                continue
            if not result or race not in day["kpis"]["recommendation"]["eligible_ids"]:
                missing(rcov, ident, "OFFICIAL_RESULT_OR_RECOMMENDATION_ELIGIBILITY_MISSING",
                        ["official_result", "eligible_recommendation"])
                continue
            settlement = row.get("recommendation_result")
            if not isinstance(settlement, dict) or settlement.get("status") != "SETTLED":
                missing(rcov, ident, "NOT_SETTLED", ["valid_settlement"])
                continue
            rec = verify_recommendation(root, safe_path(root, row["recommendation_gate_path"]))
            final = phases["FINAL"]
            if not final:
                missing(rcov, ident, "FINAL_PREDICTION_MISSING", ["final_gate"])
                continue
            gate = validate_gate(root, safe_path(root, final[-1]["prediction_gate_path"]))
            anchor = gate["production"]["ranking"][0]
            rcov["eligible_ids"].append(ident)
            rcov["included_ids"].append(ident)
            recs["unique_races"] += 1
            for ticket in settlement["tickets"]:
                if ticket["result"] == "INVALID":
                    continue
                recs["unique_tickets"] += 1
                if ticket["result"] != "MISS":
                    continue
                recs["miss_tickets"] += 1
                labels = classify_ticket(ticket, pos, anchor)
                for label in labels:
                    recs["label_counts"][label] += 1
                recs["labeled_tickets"].append({"race_id": race, "race_date_jst": date,
                    "type": ticket["type"], "horses": ticket["horses"], "labels": labels,
                    "recommendation_id": rec["recommendation_id"]})
    for phase in unm:
        value = unm[phase]
        close_coverage(value["coverage"])
        value["first_rate"] = value["first"] / value["horse_count"] if value["horse_count"] else None
        value["second_rate"] = value["second"] / value["horse_count"] if value["horse_count"] else None
        value["top3_rate"] = value["top3"] / value["horse_count"] if value["horse_count"] else None
    close_coverage(changes["coverage"])
    close_coverage(recs["coverage"])
    changes["states"] = dict(changes["states"])
    recs["label_counts"] = dict(recs["label_counts"])
    recs["states_excluded"] = dict(recs["states_excluded"])
    recs["miss_ticket_rate"] = recs["miss_tickets"] / recs["unique_tickets"] if recs["unique_tickets"] else None
    return {"unmarked_by_fixed_phase": unm, "initial_final_change_evidence": changes,
            "recommendation_failure_classification": recs,
            "composite_unmarked_good_run": None,
            "composite_unmarked_good_run_reason": "Ownerに新しい合成しきい値の定義がない"}
