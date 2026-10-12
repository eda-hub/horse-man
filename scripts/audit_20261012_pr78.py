#!/usr/bin/env python3
"""PR #78: 2026-10-12 prediction preservation audit (post-race only).

Use real standard checkers. A successful non-task receipt check is not a
TASK_PERSISTENCE_COMPLETE, and hashes reconstructed from Git commits do not
establish that a pre-write SHA-256 was saved at the fixed time.
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

DATE = "2026-10-12"
SNAPSHOT = f"docs/validation/snapshots/{DATE}.md"
RECEIPTS = f"docs/validation/persistence-receipts/{DATE}.md"
ITEMS = (
    ("京都10R", "KYO-10", "kyoto-10-final", "20261012-KYO-10-P001-S01",
     "35691ddff712f284caf400f8fee8a584189282dc",
     "c1656e21271c49f19ce17db7f4b2a3a1c76e770c6c2c53aa1b3bd9869ada6142",
     "2026-10-12T15:10:00+09:00"),
    ("東京11R", "TOK-11", "tokyo-11-final", "20261012-TOK-11-P001-S01",
     "ca6e347124410b7ec976a1da2a9fe8309dd14c6e",
     "bab7a6ace2ab8b95066e66728e067f4eeff776001738866d9911d0330d39885e",
     "2026-10-12T15:30:00+09:00"),
    ("京都11R", "KYO-11", "kyoto-11-final", "20261012-KYO-11-P001-S01",
     "73881671fa04dc1db540fc8bc6f1d44a89e8e83c",
     "89a747eea4f9d0aa9a5ce69043078fa1a355b541d7e64e99b479eee9e6f71223",
     "2026-10-12T15:45:00+09:00"),
)

def run(root, args):
    return subprocess.run(args, cwd=root, capture_output=True, text=True, check=False)

def command(root, *args):
    return run(root, [sys.executable, *args])

def digest(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def section(content, snapshot_id):
    matches = [part for part in re.split(r"(?=^##\s+)", content, flags=re.M)
               if re.search(r"^(?:-\s+)?snapshot_id:\s*" +
                            re.escape(snapshot_id) + r"\s*$", part, re.M)]
    if len(matches) != 1:
        raise AssertionError(f"Expected one section for {snapshot_id}; got {len(matches)}")
    return matches[0]

def original_commit_file(root, sha):
    args = ["git", "show", f"{sha}:{SNAPSHOT}"]
    original = run(root, args)
    if original.returncode:
        fetched = run(root, ["git", "fetch", "--quiet", "--no-tags", "--depth=1",
                             "origin", sha])
        if fetched.returncode:
            raise AssertionError(f"Cannot fetch historical commit {sha}: {fetched.stderr}")
        original = run(root, args)
    if original.returncode:
        raise AssertionError(f"Cannot read original snapshot {sha}: {original.stderr}")
    return original.stdout

def require_audit_markers(output):
    # 旧Markdownのみの検索とJSON対応検索は、同じsnapshot欠落を別文言で報告する。
    # 対象IDと「欠落」の判定を維持し、成功や別対象のエラーは代用しない。
    missing_whole = (
        '20261012-WHOLE-S01: expected one snapshot section, found 0',
        '20261012-WHOLE-S01: snapshot file missing:',
    )
    if not any(marker in output for marker in missing_whole):
        raise AssertionError('Missing standard checker audit marker: whole24 snapshot absent')
    for marker in ('20261012-REMAINING-S01',
                   '20261012-TOK-11-WEIGHT-S01: verified pre-race receipt missing'):
        if marker not in output:
            raise AssertionError(f'Missing standard checker audit marker: {marker}')

def audit(root):
    s = (root / SNAPSHOT).read_text(encoding="utf-8")
    receipts_text = (root / RECEIPTS).read_text(encoding="utf-8")
    receipts = [json.loads(block) for block in re.findall(
        r"^\x60\x60\x60persistence-receipt-v1\s*\n(.*?)\n\x60\x60\x60\s*$",
        receipts_text, re.M | re.S)]
    for name, _, intent, snapshot_id, sha, original_digest, deadline in ITEMS:
        current = section(s, snapshot_id)
        history = section(original_commit_file(root, sha), snapshot_id)
        if digest(history) != original_digest:
            raise AssertionError(f"{name}: original-commit hash differs from audit baseline")
        if not current.startswith(history):
            raise AssertionError(f"{name}: FIXED content changed, not just appended delimiters")
        trailing = current[len(history):]
        if trailing not in ("\n---\n\n", "\n\n---\n\n"):
            raise AssertionError(f"{name}: unexpected change following original content: {trailing!r}")
        current_digest = digest(current)
        if current_digest == original_digest:
            raise AssertionError(f"{name}: expected post-append section hash difference was not found")
        intent_data = json.loads((root / f"docs/validation/persistence-intents/{DATE}/{intent}.json").read_text(encoding="utf-8"))
        if intent_data["snapshot_id"] != snapshot_id or intent_data["deadline_jst"] != deadline:
            raise AssertionError(f"{name}: intent differs from fixed race/deadline")
        r02 = [r for r in receipts if r.get("artifact_id") == snapshot_id and
               r.get("receipt_persist_status") == "RECEIPT_VERIFIED"]
        if len(r02) != 1:
            raise AssertionError(f"{name}: expected one verified readback receipt")
        receipt = r02[0]
        if receipt.get("artifact_commit_sha") != sha or receipt.get("timing_eligibility") != "PRE_RACE_ELIGIBLE":
            raise AssertionError(f"{name}: receipt not linked to original FIX commit")
        if receipt["persist_verified_at_jst"] >= deadline or receipt["receipt_verified_at_jst"] >= deadline:
            raise AssertionError(f"{name}: receipt times are not before scheduled post")
        direct = command(root, "scripts/verify_prediction_persistence.py",
                         "--date", DATE, "--snapshot-id", snapshot_id, "--machine-log")
        if direct.returncode or "PERSISTENCE_VERIFIED " not in direct.stdout:
            raise AssertionError(f"{name}: direct standard checker failed: {direct.stdout} {direct.stderr}")
        task = command(root, "scripts/verify_prediction_persistence.py",
                       "--date", DATE, "--snapshot-id", snapshot_id,
                       "--intent-id", intent, "--task-complete",
                       "--fixed-content-sha256", original_digest)
        if task.returncode == 0 or "fixed/readback content hash mismatch" not in task.stderr:
            raise AssertionError(f"{name}: unexpected task-complete result: {task.stdout} {task.stderr}")
        print(f"PR78_FIXED {name} receipt=PASS original_commit={sha} "
              f"original_sha256={original_digest} current_section_sha256={current_digest} "
              f"original_bytes={len(history.encode('utf-8'))} "
              f"delimiter_added_bytes={len(trailing.encode('utf-8'))} "
              f"task_complete=FAIL_HASH_MISMATCH prewrite_hash=NOT_EVIDENCED")

    audit_result = command(root, "scripts/verify_prediction_persistence.py",
                           "--audit", "--date", DATE)
    if audit_result.returncode != 0:
        raise AssertionError("standard audit unexpectedly returned nonzero")
    require_audit_markers(audit_result.stdout)
    compliance = command(root, "scripts/check_prediction_compliance.py", "--audit")
    if compliance.returncode:
        raise AssertionError("compliance checker returned unexpected nonzero")
    for code in ("20261012-KYO-10", "20261012-TOK-11", "20261012-KYO-11"):
        if f"snapshot has no execution gate: {code}" not in compliance.stdout:
            raise AssertionError(f"Missing execution gate failure: {code}")
    print("PR78_DECLARATIONS full24=NO_SNAPSHOT remaining21=VERIFIED "
          "tokyo11_weight7=NO_PRE_RACE_RECEIPT")
    print("PR78_EXECUTION_GATE missing=KYO-10,TOK-11,KYO-11 "
          "production_eligibility=INELIGIBLE_ALL_THREE")
    print("PR78_AUDIT_CONSISTENT: 3 original FIX commits and standard checker outcomes confirmed")
    return 0

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    try:
        raise SystemExit(audit(args.root))
    except (AssertionError, FileNotFoundError, ValueError) as exc:
        print(f"PR78_AUDIT_FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1)
