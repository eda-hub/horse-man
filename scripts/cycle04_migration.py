#!/usr/bin/env python3
"""第4サイクルの繰越・移行原票と事後日別台帳を独立して監査する。"""
import argparse
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
CONTRACT="docs/validation/contracts/cycle_04.json"
CARRYOVER="docs/validation/reviews/cycle_04/carryover.json"
MANIFEST="docs/validation/reviews/cycle_04/migration-manifest.json"
DAY="docs/validation/records/cycle_04/2026-10-17.json"
SUMMARY="docs/validation/reviews/cycle_04/summary.json"
MORNING="docs/validation/persistence-intents/2026-10-17/morning.json"
INDEX="docs/validation/reconciliations/2026-10-17-day-index.json"
RESULTS="docs/validation/reviews/cycle_04/2026-10-17-all-36-official-results-reference.json"
CERT="docs/validation/reviews/cycle_04/2026-10-17-formal-kpi-certification-decision.json"
DECISIONS="docs/validation/reviews/cycle_03/decisions.json"
COLLECTION="docs/validation/reviews/cycle_03/collection.json"
POSTRACE_SCHEMA="cycle04-day-postrace-reconciliation-v1"
SOURCE_COMMIT="885d7d490245ba4d948bb4594017371d17eadc04"
VENUES={"TOKYO":"TOK","KYOTO":"KYO","NIIGATA":"NII"}

def require(condition,reason):
    if not condition:
        raise ValueError(reason)

def read(root,path):
    p=(root/path).resolve()
    require(p.is_relative_to(root.resolve()) and p.is_file(),"参照不能: "+path)
    return json.loads(p.read_text(encoding="utf-8"))

def digest(root,path):
    return hashlib.sha256((root/path).read_bytes()).hexdigest()

def canon(race):
    m=re.fullmatch(r"(2026-10-17)-(TOKYO|KYOTO|NIIGATA)-(0[1-9]|1[0-2])",race)
    require(m is not None,"不正な原race_id: "+str(race))
    return "20261017-"+VENUES[m[2]]+"-"+m[3]

def validate_carryover(root):
    data=read(root,CARRYOVER)
    old=read(root,DECISIONS)
    collection=read(root,COLLECTION)
    require(data.get("schema_version")=="cycle04-carryover-v1","繰越schema")
    require(data.get("source_commit")==SOURCE_COMMIT,"繰越元commitの不一致")
    records=data.get("items")
    require(isinstance(records,list) and len({r["id"] for r in records})==len(records),"繰越IDの重複")
    groups={"CHANGE":16,"VALIDATION":13,"DIFFERENCE":21,"CYCLE02_REVIEW":5,"CYCLE02_OPERATION":9,"CYCLE02_DIAGNOSTIC":4}
    require({g:sum(r.get("group")==g for r in records) for g in groups}==groups,"繰越項目に欠落")
    expected={
        "CHANGE":set(x["id"] for x in old["changes"]),
        "VALIDATION":set(x["internal_id"] for x in old["validation_items"]),
        "DIFFERENCE":set(x["race_date_jst"]+"|"+x["race_id"] for x in old["candidate_difference_classification"])
    }
    for group,ids in expected.items():
        actual={r["source_item_id"] for r in records if r["group"]==group}
        require(actual==ids,"繰越元ID不一致: "+group)
    for r in records:
        require(r.get("source_cycle") in {"cycle_02","cycle_03"} and r.get("source_path")
                and r.get("source_item_id") and r.get("owner") and r.get("next_test")
                and r.get("protected") and r.get("decision") and
                r.get("implementation_status") and r.get("live_validation_status"),
                "出所/Owner/採否/検証が欠けた繰越項目: "+str(r.get("id")))
        require(r["live_validation_status"]!="VERIFIED" or bool(r.get("live_evidence")),
                "実測証拠がないのに検証済み")
    for group,source,key in [
        ("CHANGE",old["changes"],lambda x:x["id"]),
        ("VALIDATION",old["validation_items"],lambda x:x["internal_id"]),
        ("DIFFERENCE",old["candidate_difference_classification"],lambda x:x["race_date_jst"]+"|"+x["race_id"])]:
        rows={r["source_item_id"]:r for r in records if r["group"]==group}
        for item in source:
            require(rows[key(item)].get("source_payload")==item,"旧個別判定と移管内容が不一致: "+key(item))
    classified={(x["race_date_jst"],x["race_id"]) for x in old["candidate_difference_classification"]}
    actual={(date,race) for date,day in collection["daily"].items() for race in day["selected_without_final_ids"]}
    require(classified==actual,"第3の21件分類と原集合が不一致")
    require(data.get("historical_pending_kpi_decisions")==collection["pending_kpi_decision_count"],
            "第3KPI保留件数不一致")
    require(data.get("candidate_difference_counts")==old.get("candidate_difference_counts"),
            "第3候補差分類の数値が移管されていない")
    require(data.get("performance_promotion")=="NOT_APPROVED","性能認証の無断昇格")
    return data

def validate_manifest(root):
    manifest=read(root,MANIFEST)
    require(manifest.get("schema_version")=="cycle04-migration-manifest-v1" and
            manifest.get("source_commit")==SOURCE_COMMIT,"移行manifest原点")
    files=manifest.get("files")
    require(isinstance(files,list) and len({r.get("path") for r in files})==len(files),
            "削除候補・保持原票が重複")
    for item in files:
        require(item.get("role") and item.get("decision") in {"RETAIN","DELETE_VERIFIED","PENDING"} and
                item.get("reason") and re.fullmatch(r"[0-9a-f]{40}",item.get("git_blob_sha1","")) and
                re.fullmatch(r"[0-9a-f]{64}",item.get("sha256","")),"manifest参照/判断不備")
        if item["decision"]=="RETAIN":
            require((root/item["path"]).is_file() and digest(root,item["path"])==item["sha256"],
                    "保持する原本が失われたか改変: "+item["path"])
        if item["decision"]=="DELETE_VERIFIED":
            require(not (root/item["path"]).exists() and
                    item.get("fixed_history_verified") is True and
                    item.get("references_retargeted") is True and
                    item.get("recomputed_results_verified") is True,
                    "削除の必須3ゲート不一致: "+item["path"])
        if item["decision"]=="PENDING":
            require((root/item["path"]).exists(),"削除前審査なしの原票喪失: "+item["path"])
    require(manifest.get("carryover_path")==CARRYOVER,"課題台帳の正本参照")
    return manifest

def validate_postrace(root,day=None):
    d=day if day is not None else read(root,DAY)
    morning=read(root,MORNING); idx=read(root,INDEX)
    results=read(root,RESULTS);cert=read(root,CERT)
    ids=morning["required_race_ids"]
    require(d.get("schema_version")==POSTRACE_SCHEMA and d.get("cycle_id")=="cycle_04"
            and d.get("race_date_jst")=="2026-10-17" and d.get("manual_release")=="v1.7.0"
            and d.get("registration_origin")=="POSTRACE_RECONCILIATION",
            "10/17事後台帳schema/起源")
    registered=datetime.fromisoformat(d.get("registered_at_jst",""))
    require(registered.utcoffset() is not None and registered.date().isoformat()>="2026-10-17",
            "事後登録時刻が不正")
    require(d.get("declared_scope")==ids and d.get("initial_scope")==[]
            and d.get("selected_scope")==[] and d.get("final_scope")==[]
            and d.get("reviewed_scope")==[] and len(ids)==len(set(ids))==36,
            "事後照合を発走前のscope/回顧へ昇格")
    require(d.get("source_paths")=={"morning":MORNING,"index":INDEX,"results":RESULTS,"certification":CERT},
            "事後原本参照の不一致")
    require([r["race_id"] for r in d.get("races",[])]==ids and
            [r["race_id"] for r in idx["races"]]==ids and
            [r["race_id"] for r in results["races"]]==ids and
            [r["race_id"] for r in cert["decisions"]]==ids,
            "36件の順序と集合不一致")
    require(d.get("formal_certification")=="REJECTED" and
            d.get("pre_off_scope_registered") is False,"歴史的不適格の無断変更")
    count_primary=0; prior=0; canon_ids=set()
    for row,old,source,decision in zip(d["races"],idx["races"],results["races"],cert["decisions"]):
        rid=row["race_id"]
        require(row.get("canonical_race_id")==canon(rid),"ID正規化不一致: "+rid)
        canon_ids.add(row["canonical_race_id"])
        require(row.get("post_time_jst")==source["scheduled_post_time_jst"]
                and registered>datetime.fromisoformat(row["post_time_jst"]),
                "実登録時刻を事前時刻へ改変: "+rid)
        require(row.get("source_result_path")==RESULTS and
                row.get("result_status")=="POSTRACE_RESULT_ONLY","事後結果の出所不一致")
        primary=source["source"]["official_url"] is not None
        count_primary+=int(primary)
        prior+=int(source["pre_off_forecast"]["path"] is not None)
        require(row.get("official_individual_page_verified") is primary and
                row.get("pre_off_evidence_path")==source["pre_off_forecast"]["path"] and
                row.get("original_prediction_status")==old["prediction"]["status"],
                "原票の予想/結果/公式種別不一致: "+rid)
        require(row.get("prediction_eligibility")==decision["prediction"]["status"]=="INELIGIBLE"
                and row.get("recommendation_eligibility")==decision["recommendation"]["status"]=="INELIGIBLE"
                and row.get("shadow_eligibility")==decision["shadow"]["status"]=="INELIGIBLE",
                "過去の不適格判定を改変: "+rid)
    require(len(canon_ids)==36 and count_primary==6 and prior==6,
            "公式個別6件/参考30件または6予想証拠の数が不一致")
    return {"races":36,"official_primary":count_primary,"secondary_results":36-count_primary,
            "pre_off_reference_only":prior,"formally_eligible":0}

def compute_summary(root):
    contract=read(root,CONTRACT)
    dates=contract["race_dates"]
    from check_cycle04 import validate_day
    postrace=[];forward=[];missing=[]
    for date in dates:
        p=root/"docs/validation/records/cycle_04"/(date+".json")
        if not p.is_file():
            missing.append(date);continue
        d=json.loads(p.read_text(encoding="utf-8"))
        if d.get("registration_origin")=="POSTRACE_RECONCILIATION":
            require(date=="2026-10-17","事後照合対象外の日")
            postrace.append({"date":date,**validate_postrace(root,d)})
        else:
            verified=validate_day(root,p,contract)
            forward.append({"date":date,"initial":len(verified["initial_scope"]),
                "selected":len(verified["selected_scope"]),"final":len(verified["final_scope"]),
                "reviewed":len(verified["reviewed_scope"]),
                "unfinished_selected":len(verified["unfinished_reasons"])})
    from cycle04_completion import evaluate_days
    completion=evaluate_days(root, [validate_day(root,root/"docs/validation/records/cycle_04"/
                                                 (item["date"]+".json"),contract)
                                   for item in forward])
    return {"schema_version":"cycle04-cycle-summary-v1","cycle_id":"cycle_04",
        "performance_promotion":"NOT_APPROVED","expected_dates":dates,
        "postrace_reconciliation":postrace,"forward_days":forward,
        "not_registered_dates":missing,"normal_full_cycle_complete":bool(completion["normal_cycle_complete"]),
        "note":"事後照合は前向き日別実績・独立KPI適格に含まない。期間終了判定はcompletion契約が別途必要。"}

def audit(root):
    validate_carryover(root)
    validate_manifest(root)
    computed=compute_summary(root)
    require(read(root,SUMMARY)==computed,"サイクルsummaryが日別の再生成値と不一致")
    for date in computed["not_registered_dates"]:
        intent_dir=root/"docs/validation/persistence-intents"/date
        if intent_dir.exists() and any(intent_dir.glob("*.json")):
            raise ValueError("依頼宣言があるのに日別未登録: "+date)
    require(len(computed["postrace_reconciliation"])==1,
            "10月17日の事後照合台帳が存在しない")
    return computed

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root",type=Path,default=ROOT)
    p.add_argument("--audit",action="store_true")
    p.add_argument("--write-summary",action="store_true")
    args=p.parse_args(argv);root=args.root.resolve()
    try:
        if args.write_summary:
            path=root/SUMMARY
            path.write_text(json.dumps(compute_summary(root),ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        result=audit(root) if args.audit else compute_summary(root)
        print("CYCLE04_MIGRATION "+json.dumps(result,ensure_ascii=False,sort_keys=True))
        return 0
    except (ValueError,OSError,KeyError,TypeError) as exc:
        print("第4移行検査不合格: "+str(exc),file=sys.stderr)
        return 1

if __name__=="__main__":
    raise SystemExit(main())
