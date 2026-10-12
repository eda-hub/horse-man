"""2026-10-12 PR78 regression audit: run the real standard checker on fixed evidence."""
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class PR78HistoricalAuditTest(unittest.TestCase):
    def test_fixed_commit_and_standard_checker(self):
        record = ROOT / "docs/validation/records/2026-10-12.md"
        # The historical audit is specific to this day's existing live record.
        if not record.exists():
            self.skipTest("2026-10-12 live record not present on this branch")
        task = subprocess.run(
            [sys.executable, str(ROOT / "scripts/audit_20261012_pr78.py"),
             "--root", str(ROOT)], cwd=ROOT, text=True, capture_output=True)
        self.assertEqual(task.returncode, 0,
                         f"PR78 audit failed:\n{task.stdout}\n{task.stderr}")
        self.assertIn("PR78_AUDIT_CONSISTENT", task.stdout)
        print(task.stdout, end="")

if __name__ == "__main__":
    unittest.main()
