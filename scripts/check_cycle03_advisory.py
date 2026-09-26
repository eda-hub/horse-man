#!/usr/bin/env python3
"""Advisory-only checker for Cycle 03 evidence collection.

This script reports evidence gaps that can make later validation impossible.
It never treats warnings as a failing process result and is intentionally not
wired into the operational GitHub Actions gate.
"""

import argparse
import json
import re
from pathlib import Path

DAY_TAG = "cycle03-day-v1"
MISSING_TOKENS = {
    "",
    "MISSING",
    "MISSING_IN_INITIAL_SNAPSHOT",
    "UNAVAILABLE",
    "UNRECORDED",
    "UNRESOLVED",
    "NONE",
    "NULL",
}


def fenced_json(path: Path, tag: str):
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    matches = re.findall(
        r"^```" + re.escape(tag) + r"\s*\n(.*?)\n```\s*$",
        text,
        re.M | re.S,
    )
    if not matches:
        return None
    return json.loads(matches[-1])


def sections(text: str):
    return re.split(r"(?=^##\s+)", text, flags=re.M)


def field(section: str, name: str):
    match = re.search(rf"^{re.escape(name)}:\s*(.*?)\s*$", section, re.M)
    return match.group(1).strip() if match else None


def valid(value):
    if value is None:
        return False
    normalized = value.strip().upper()
    return (
        normalized not in MISSING_TOKENS
        and not normalized.startswith("MISSING_")
        and not normalized.startswith("UNRESOLVED")
    )


def section_stage(section: str):
    snapshot_type = field(section, "snapshot_type")
    if snapshot_type:
        normalized = snapshot_type.strip().upper()
        if normalized in {"INITIAL", "INITIAL_PRODUCTION"}:
            return "initial"
        if normalized in {"FINAL", "FINAL_PRODUCTION"}:
            return "final"

    heading = section.splitlines()[0].lower() if section.splitlines() else ""
    has_initial = "初回" in heading or re.search(r"\binitial\b", heading)
    has_final = "最終" in heading or re.search(r"\bfinal\b", heading)
    if has_initial and not has_final:
        return "initial"
    if has_final and not has_initial:
        return "final"
    return None


def race_sections(text: str):
    result = {}
    for section in sections(text):
        race_id = field(section, "race_id")
        if race_id:
            result.setdefault(race_id, []).append(section)
    return result


def stage_sections(blocks, stage):
    return [block for block in blocks if section_stage(block) == stage]


def receipt_statuses(text: str):
    result = {}
    for section in sections(text):
        artifact_id = field(section, "artifact_id")
        if not artifact_id:
            continue
        result.setdefault(artifact_id, []).append(
            {
                "receipt": field(section, "receipt_persist_status"),
                "timing": field(section, "timing_eligibility"),
            }
        )
    return result


def has_probability_evidence(section: str):
    labels = ("推定確率", "勝率", "連対率", "3着内率")
    missing_markers = (
        "UNAVAILABLE",
        "UNRECORDED",
        "MISSING",
        "未取得",
        "未保存",
        "不明",
        "判定不能",
    )
    unrelated_ratio_labels = (
        "依存率",
        "予算",
        "配分",
        "投資",
        "回収率",
        "ROI",
        "割合",
        "比率",
    )
    numeric_percent = re.compile(
        r"(?<![\d.])(?:100(?:\.0+)?|\d{1,2}(?:\.\d+)?)\s*%"
    )
    lines = section.splitlines()

    def is_missing(line):
        upper = line.upper()
        return any(marker in upper or marker in line for marker in missing_markers)

    def percentages(line):
        return numeric_percent.findall(line)

    for index, line in enumerate(lines):
        if not any(label in line for label in labels):
            continue
        if is_missing(line):
            continue
        if percentages(line):
            return True

        following = lines[index + 1:]
        first_index = None
        for offset, child in enumerate(following):
            if child.strip():
                first_index = offset
                break
        if first_index is None:
            continue

        first = following[first_index].strip()
        if first.startswith("#"):
            continue

        if first.startswith("|"):
            table_lines = []
            for child in following[first_index:]:
                stripped = child.strip()
                if not stripped:
                    break
                if not stripped.startswith("|"):
                    break
                table_lines.append(stripped)

            if not table_lines:
                continue

            header = table_lines[0]
            if not any(label in header for label in labels):
                continue

            for row in table_lines[1:]:
                normalized = row.replace("|", "").replace(":", "").replace("-", "").strip()
                if not normalized:
                    continue
                if is_missing(row):
                    continue
                if percentages(row):
                    return True
            continue

        if first.startswith("-"):
            for child in following[first_index:]:
                stripped = child.strip()
                if not stripped:
                    break
                if not stripped.startswith("-"):
                    break
                if any(label in stripped for label in unrelated_ratio_labels):
                    break
                if is_missing(stripped):
                    continue
                values = percentages(stripped)
                if values and (
                    any(label in stripped for label in labels)
                    or len(values) >= 2
                ):
                    return True
            continue

    return False


def add_warning(items, code, message, race_id=None):
    items.append({"code": code, "race_id": race_id, "message": message})


def inspect(day, snapshot_text: str, receipt_text: str, preservation_text: str):
    warnings = []
    initial = set(day.get("initial_scope", []))
    validation = set(day.get("validation_candidates", []))
    purchase = set(day.get("purchase_candidates", []))
    selected = validation | purchase
    completed = set(day.get("final_completed_scope", []))

    snap_by_race = race_sections(snapshot_text)
    preserve_by_race = race_sections(preservation_text)
    receipts = receipt_statuses(receipt_text)

    for race_id in sorted(initial):
        initial_blocks = stage_sections(snap_by_race.get(race_id, []), "initial")

        baseline_ok = any(
            valid(field(block, "baseline_forecast_id"))
            for block in initial_blocks
        )
        if not baseline_ok:
            add_warning(
                warnings,
                "BASELINE_ID_MISSING",
                "初回比較の基準IDを確認できません。",
                race_id,
            )

        probability_ok = any(
            has_probability_evidence(block)
            for block in initial_blocks
        )
        if not probability_ok:
            add_warning(
                warnings,
                "PROBABILITY_EVIDENCE_MISSING",
                "勝率等の確率証跡を確認できません。",
                race_id,
            )

    for race_id in sorted(selected):
        race_blocks = snap_by_race.get(race_id, []) + preserve_by_race.get(race_id, [])
        if not any(
            valid(field(block, "candidate_class"))
            or valid(field(block, "候補区分"))
            for block in race_blocks
        ):
            add_warning(
                warnings,
                "CANDIDATE_CLASS_MISSING",
                "候補区分の明示を確認できません。",
                race_id,
            )

    for race_id in sorted(selected - completed):
        add_warning(
            warnings,
            "FINAL_NOT_COMPLETED",
            "selected_final_scope に属しますが最終予想完了集合にありません。",
            race_id,
        )

    for race_id in sorted(completed):
        final_blocks = stage_sections(snap_by_race.get(race_id, []), "final")
        artifact_ids = []
        for block in final_blocks:
            snapshot_id = field(block, "snapshot_id")
            if valid(snapshot_id):
                artifact_ids.append(snapshot_id)

        prereceipt = any(
            status.get("receipt") == "RECEIPT_VERIFIED"
            and status.get("timing") == "PRE_RACE_ELIGIBLE"
            for artifact_id in artifact_ids
            for status in receipts.get(artifact_id, [])
        )
        if not prereceipt:
            add_warning(
                warnings,
                "PRE_RACE_RECEIPT_MISSING",
                "発走前の RECEIPT_VERIFIED 証跡を確認できません。",
                race_id,
            )

        if any(
            field(block, "timing_eligibility") == "LATE_PRESERVATION"
            for block in preserve_by_race.get(race_id, [])
        ):
            add_warning(
                warnings,
                "LATE_PRESERVATION",
                "発走後保全が存在します。前向きKPIの代替にはなりません。",
                race_id,
            )

    shadow = day.get("kpis", {}).get("shadow", {})
    for race_id in sorted(set(shadow.get("ineligible_ids", []))):
        add_warning(
            warnings,
            "SHADOW_INELIGIBLE",
            "Shadow対象ですが適格な検証証跡になっていません。",
            race_id,
        )

    for race_id in sorted(set(shadow.get("pending_ids", []))):
        add_warning(
            warnings,
            "SHADOW_PENDING",
            "Shadow対象の適格性判定が未完了です。",
            race_id,
        )

    return warnings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", required=True, help="YYYY-MM-DD")
    parser.add_argument(
        "--records-dir",
        type=Path,
        default=Path("docs/validation/records"),
    )
    parser.add_argument(
        "--snapshots-dir",
        type=Path,
        default=Path("docs/validation/snapshots"),
    )
    parser.add_argument(
        "--receipts-dir",
        type=Path,
        default=Path("docs/validation/persistence-receipts"),
    )
    parser.add_argument(
        "--preservation-dir",
        type=Path,
        default=Path("docs/validation/preservation"),
    )
    args = parser.parse_args()

    day_path = args.records_dir / f"{args.date}.md"
    day = fenced_json(day_path, DAY_TAG)
    if day is None:
        print(f"WARN DAY_LEDGER_MISSING {day_path}")
        return 0

    def read_optional(path):
        return path.read_text(encoding="utf-8") if path.exists() else ""

    warnings = inspect(
        day,
        read_optional(args.snapshots_dir / f"{args.date}.md"),
        read_optional(args.receipts_dir / f"{args.date}.md"),
        read_optional(args.preservation_dir / f"{args.date}.md"),
    )

    if not warnings:
        print("ADVISORY_OK: no evidence gaps detected by this checker")
        return 0

    for item in warnings:
        race = f" race_id={item['race_id']}" if item["race_id"] else ""
        print(f"WARN {item['code']}{race}: {item['message']}")

    print(
        f"ADVISORY_ONLY: {len(warnings)} warning(s); "
        "exit status remains 0"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
