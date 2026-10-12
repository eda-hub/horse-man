#!/usr/bin/env python3
"""第3サイクルの終了審査資料を再現する。適格性の認証・昇格は行わない。"""

import argparse
import hashlib
import json
import re
import sys
from datetime import date
from pathlib import Path

from check_cycle03 import (
    CONTRACT, DAY_TAG, EXPECTED_DATES, SUMMARY_TAG, block, summarize, validate_day,
)

DEFAULT_REPORT = Path("docs/validation/reviews/cycle_03/collection.json")
SET_KEYS = ("target_ids", "eligible_ids", "ineligible_ids", "pending_ids")


def fingerprint(path, root):
    content = path.read_bytes()
    return {
        "path": path.relative_to(root).as_posix(),
        "bytes": len(content),
        "git_blob_sha": hashlib.sha1(
            b"blob " + str(len(content)).encode() + b"\0" + content
        ).hexdigest(),
        "sha256": hashlib.sha256(content).hexdigest(),
    }


def kpi_view(kpis):
    result = {}
    for name, value in sorted(kpis.items()):
        result[name] = dict(value)
        result[name]["counts"] = {key: len(value[key]) for key in SET_KEYS}
        if name == "betting":
            stake = value.get("stake_yen")
            result[name]["ledger_claimed_return_rate_pct"] = (
                round(100 * value["return_yen"] / stake, 6) if stake else None
            )
    return result


def build(root, as_of_date_jst, basis_commit):
    root = root.resolve()
    as_of = date.fromisoformat(as_of_date_jst)
    if as_of.isoformat() != as_of_date_jst:
        raise ValueError("確認日はYYYY-MM-DDで指定してください")
    if not isinstance(basis_commit, str) or not re.fullmatch(r"[0-9a-f]{40}", basis_commit):
        raise ValueError("参照commitは完全な40桁のSHAで指定してください")
    cycle_file = root / "docs/validation/cycle_03.md"
    days, sources = {}, {cycle_file}
    for path in sorted((root / "docs/validation/records").glob("*.md")):
        day = block(path, DAY_TAG)
        if day is None:
            continue
        day_date = validate_day(day, path)
        if day_date in days:
            raise ValueError("同じ開催日の日別台帳が重複しています")
        days[day_date] = day
        sources.add(path)
    if not days:
        raise ValueError("日別台帳がなく、終了総括を実測として作成できません")
    race_ids = [r for day in days.values() for r in day["initial_scope"]]
    if len(race_ids) != len(set(race_ids)):
        raise ValueError("同じレースが異なる開催日の台帳に含まれています")
    summary = summarize(days)
    if block(cycle_file, SUMMARY_TAG) != summary:
        raise ValueError("サイクル集計が日別台帳と不一致です。原記録を確認してください")

    per_day = {}
    scope_totals = {key: 0 for key in (
        "initial", "selected", "final_completed", "selected_without_final", "reviewed", "unreviewed",
    )}
    for day_date in sorted(EXPECTED_DATES):
        evidence = []
        for folder in ("snapshots", "persistence-receipts", "preservation"):
            path = root / "docs/validation" / folder / f"{day_date}.md"
            if path.exists():
                evidence.append(path)
        for folder in ("persistence-intents", "execution-gates"):
            evidence.extend(sorted((root / "docs/validation" / folder / day_date).glob("*.json")))
        sources.update(evidence)
        inventory = [p.relative_to(root).as_posix() for p in sorted(evidence)]
        if day_date not in days:
            per_day[day_date] = {
                "ledger_status": "MISSING", "scope_counts": None, "kpis": None,
                "evidence_paths": inventory,
                "note": "日別台帳なし。無開催・未依頼・0件・全件不適格とは判定しない。",
            }
            continue
        day = days[day_date]
        selected = set(day["validation_candidates"]) | set(day["purchase_candidates"])
        missing_final = sorted(selected - set(day["final_completed_scope"]))
        counts = {
            "initial": len(day["initial_scope"]), "selected": len(selected),
            "final_completed": len(day["final_completed_scope"]),
            "selected_without_final": len(missing_final),
            "reviewed": len(day["reviewed_scope"]), "unreviewed": len(day["unreviewed_scope"]),
        }
        for key, value in counts.items():
            scope_totals[key] += value
        per_day[day_date] = {
            "ledger_status": "RECORDED", "scope_counts": counts,
            "selected_without_final_ids": missing_final,
            "kpi_contract": day.get("kpi_contract", "LEGACY_UNSPLIT"),
            "kpis": kpi_view(day["kpis"]), "evidence_paths": inventory,
            "note": "集合差は未実施件数。障害・失敗・利用者許容の区別は元記録を参照。",
        }

    contracts = {}
    for contract in sorted({d.get("kpi_contract", "LEGACY_UNSPLIT") for d in days.values()}):
        group = {k: d for k, d in days.items() if d.get("kpi_contract", "LEGACY_UNSPLIT") == contract}
        contracts[contract] = {"recorded_dates": sorted(group), "kpis": kpi_view(summarize(group)["kpis"])}
    settlements = [(d, value["fixed_plan_settlement"]) for d, value in sorted(days.items())
                   if value.get("kpi_contract") == CONTRACT]
    stake = sum(value["stake_yen"] for _, value in settlements) if settlements else None
    returned = sum(value["return_yen"] for _, value in settlements) if settlements else None
    fixed_ids = sorted(r for _, value in settlements for r, item in value["races"].items()
                       if item.get("missing_fixed_plan") is not True)
    missing_ids = sorted(r for _, value in settlements for r, item in value["races"].items()
                         if item.get("missing_fixed_plan") is True)
    missing_dates = sorted(EXPECTED_DATES - set(days))
    end = max(EXPECTED_DATES)
    return {
        "schema_version": "cycle03-review-v1", "cycle_id": "cycle_03",
        "as_of_date_jst": as_of_date_jst, "basis_commit": basis_commit,
        "period": {"first_scheduled_date": min(EXPECTED_DATES), "last_scheduled_date": end,
                   "status": "ENDED" if as_of_date_jst > end else
                             "LAST_SCHEDULED_DAY" if as_of_date_jst == end else "IN_PERIOD"},
        "collection": {"expected_dates": sorted(EXPECTED_DATES), "recorded_dates": sorted(days),
                       "missing_dates": missing_dates,
                       "status": "INCOMPLETE" if missing_dates or scope_totals["unreviewed"] else "REVIEW_REQUIRED"},
        "scope_totals_recorded_days_only": scope_totals,
        "daily": per_day,
        "kpi_ledger_claims": kpi_view(summary["kpis"]), "contract_groups": contracts,
        "pending_kpi_decision_count": sum(len(k["pending_ids"]) for k in summary["kpis"].values()),
        "split_fixed_plan_reference": {
            "recorded_dates": [d for d, _ in settlements],
            "fixed_plan_ids": fixed_ids, "missing_fixed_plan_ids": missing_ids,
            "stake_yen": stake, "return_yen": returned,
            "reference_return_rate_pct": round(100 * returned / stake, 6) if stake else None,
            "note": "分離契約の固定全券精算。旧契約・未登録日・別研究・海外・実購入を含まない。正式ROIではない。",
        },
        "certification": {
            "ledger_consistency": "MATCHED", "evidence_authenticity": "NOT_REAUTHENTICATED",
            "performance_metrics": "NOT_COMPUTED", "rule_promotion": "NOT_PERFORMED",
            "stage_transition": "NOT_PERFORMED",
            "note": "入力hashと台帳整合の確認は発走前保存・個別完了・性能有効性の認証ではない。",
        },
        "source_manifest": [fingerprint(p, root) for p in sorted(sources)],
    }


def safe_output(root, output):
    path = output if output.is_absolute() else root / output
    path = path.resolve()
    if not path.is_relative_to(root / "docs/validation/reviews") or path.suffix != ".json":
        raise ValueError("出力先はdocs/validation/reviews内のJSONに限定します。原記録は上書きできません")
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--write", action="store_true", help="生成JSONだけを保存する")
    modes.add_argument("--check", action="store_true", help="保存済みJSONを再計算し照合する")
    parser.add_argument("--as-of-date-jst", help="確認日。保存済み資料の検査時は資料内の日付を使用")
    parser.add_argument("--basis-commit", help="参照した原記録のcommit SHA。適格性認証ではない")
    parser.add_argument("--require-complete", action="store_true", help="日別台帳/回顧の不足があれば不合格")
    args = parser.parse_args(argv)
    try:
        root = args.root.resolve()
        output = safe_output(root, args.output)
        saved = json.loads(output.read_text(encoding="utf-8")) if args.check else None
        as_of = args.as_of_date_jst or (saved["as_of_date_jst"] if saved else None)
        basis = args.basis_commit or (saved["basis_commit"] if saved else None)
        if not as_of or not basis:
            raise ValueError("生成時は確認日と参照commitの明示が必要です")
        report = build(root, as_of, basis)
        if args.check and saved != report:
            raise ValueError("保存済み終了資料が再計算値と不一致です。入力hash・集合・金額を確認してください")
        if args.require_complete and report["collection"]["status"] == "INCOMPLETE":
            raise ValueError("日別台帳または回顧が不足しており終了審査は未完了です")
        if args.write:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        elif not args.check:
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0
        print(f"終了資料の照合成功：日別台帳{len(report['collection']['recorded_dates'])}/{len(EXPECTED_DATES)}日。"
              "資料整合の確認であり、正式KPI・昇格・切替の認証ではありません。")
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"終了資料の検査不合格：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
