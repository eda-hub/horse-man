#!/usr/bin/env python3
"""旧ノートから血統関連の記述だけを未確認候補として移行する。"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

from pedigree_registry import RegistryError, atomic_save, file_blob_sha, now, single_writer

SOURCE_DIRECTORIES = (
    "docs/yosou/jra_racing",
    "docs/validation/records",
    "docs/validation/snapshots",
)
SEARCH = re.compile(
    r"血統|父系|母父|母系|父馬|種牡馬|繁殖牝馬|祖先|(?:\d[×xX]\d)|クロス|"
    r"ディープ|サンデー|ダンジグ|ロベルト|カロ|ノーザンダンサー|"
    r"Deep Impact|Danzig|Roberto|Caro|Northern Dancer|Kingmambo|Storm Cat",
    re.IGNORECASE,
)
SCHEMA = "pedigree-backfill-v1"
MANIFEST_SCHEMA = "pedigree-migration-manifest-v1"


def collect(repo, commit, recorded_at):
    records, scanned = [], []
    duplicate = 0
    seen = set()
    for directory in SOURCE_DIRECTORIES:
        base = repo / directory
        if not base.is_dir():
            continue
        for file in sorted(base.rglob("*")):
            if not file.is_file() or file.suffix not in (".md", ".json") or file.name in (
                    "README.md", "_template.md"):
                continue
            rel = file.relative_to(repo).as_posix()
            scanned.append(rel)
            for lineno, raw in enumerate(file.read_text(encoding="utf-8").splitlines(), 1):
                claim = raw.strip()
                if not claim or not SEARCH.search(claim) or len(claim) > 6000:
                    continue
                content_id = hashlib.sha256((rel + ":" + str(lineno) + ":" + claim).encode()).hexdigest()
                if content_id in seen:
                    duplicate += 1
                    continue
                seen.add(content_id)
                records.append({
                    "claim_id": "legacy-" + content_id[:24],
                    "raw_text": claim, "source_path": rel,
                    "source_line": lineno,
                    "source_text_sha256": hashlib.sha256(claim.encode()).hexdigest(),
                    "source_commit": commit,
                    "status": "UNVERIFIED",
                    "claim_kind": "PEDIGREE_OR_TREND_CANDIDATE",
                    "source_origin_status": "UNKNOWN",
                    "migration_observed_at": recorded_at,
                    "usage": "RESEARCH_ONLY_NOT_PRODUCTION_EVIDENCE",
                })
    return {
        "schema_version": SCHEMA,
        "seed_id": "backfill-2026-10-09",
        "generated_at": recorded_at,
        "mode": "BACKFILL_SEED",
        "records": records,
    }, {
        "schema_version": MANIFEST_SCHEMA,
        "generated_at": recorded_at,
        "source_commit": commit,
        "scanned_directories": list(SOURCE_DIRECTORIES),
        "scanned_files": scanned,
        "scanned_file_count": len(scanned),
        "extracted_count": len(records),
        "verified_count": 0,
        "unverified_count": len(records),
        "duplicate_count": duplicate,
        "conflicts_assessed": False,
        "unaccessed_sources": [
            "過去チャット全履歴（このリポジトリの外部）",
            "リポジトリに存在しないスナップショット・旧ノート",
        ],
        "note": "行単位候補抽出のみ。馬同定、真偽、分類、勝率、出所の独立性は検証していない。",
    }


def run(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--source-commit", required=True,
                        help="抽出元のファイル群を確認したGitコミットSHA")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    repo = args.repo_root.resolve()
    if not re.fullmatch(r"[0-9a-f]{40}", args.source_commit):
        raise RegistryError("source-commitは40桁Git SHA")
    check = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                           check=False, capture_output=True, text=True)
    if check.returncode != 0:
        raise RegistryError("Git HEADを確認できない")
    if check.stdout.strip() != args.source_commit:
        # source_commit以降に抽出元が変更されていないことを担保する
        ancestor = subprocess.run(
            ["git", "-C", str(repo), "merge-base", "--is-ancestor", args.source_commit, "HEAD"],
            check=False, capture_output=True,
        )
        if ancestor.returncode != 0:
            raise RegistryError("抽出元コミットが作業HEADの祖先ではない")
    for diff_args in (
        ["diff", "--quiet", args.source_commit, "HEAD", "--"],
        ["diff", "--quiet", "--"],
        ["diff", "--cached", "--quiet", "--"],
    ):
        check_files = subprocess.run(["git", "-C", str(repo), *diff_args, *SOURCE_DIRECTORIES],
                                     check=False, capture_output=True)
        if check_files.returncode != 0:
            raise RegistryError("元コミットと現作業ツリーの抽出対象に差分があるため中止")
    untracked = subprocess.run(
        ["git", "-C", str(repo), "ls-files", "--others", "--exclude-standard",
         "--", *SOURCE_DIRECTORIES],
        check=False, capture_output=True, text=True,
    )
    if untracked.returncode != 0 or untracked.stdout.strip():
        raise RegistryError("未追跡の抽出対象があるため中止")
    registered_at = now()
    results, manifest = collect(repo, args.source_commit, registered_at)
    paths = [repo / "data/pedigree/research/backfill-2026-10-09.json",
             repo / "data/pedigree/migration_manifest.json"]
    if args.dry_run:
        return {"manifest": manifest, "saved": False}
    with single_writer(repo / "data/pedigree"):
        receipts = [atomic_save(path, payload, file_blob_sha(path))
                    for path, payload in zip(paths, (results, manifest))]
    return {"manifest": manifest, "receipts": receipts}


def main(argv=None):
    try:
        print(json.dumps(run(argv), ensure_ascii=False, indent=2))
        return 0
    except (RegistryError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
