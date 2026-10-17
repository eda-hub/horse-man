"""第4の既知不足を原票固定で監視し厳格監査の失敗を隠さない。"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
from cycle04_recommendation_diagnostics import ROOT,DEBT,verify

class RecommendationHistoricalDiagnosticsTest(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        debt=json.loads((ROOT/DEBT).read_text())
        self.expected=[i["expected_error"] for i in debt["items"]]
        for name in [DEBT]+[i["source_path"] for i in debt["items"]]:
            p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(ROOT/name,p)

    def runner(self, lines,code=1):
        return SimpleNamespace(stdout="\n".join("RECOMMENDATION_INCOMPLETE "+line for line in lines),
                               stderr="",returncode=code)

    def test_only_fixed_four_errors_are_classified_unresolved(self):
        with patch("cycle04_recommendation_diagnostics.subprocess.run",
                   return_value=self.runner(self.expected)):
            status=verify(self.root,["synthetic"])
        self.assertEqual(status["strict_audit_exit_code"],1)
        self.assertEqual(status["state"],"HISTORICAL_UNRESOLVED")
        self.assertFalse(status["formal_kpi_certified"])

    def test_new_error_and_historical_diagnosis_change_are_fatal(self):
        for lines in (self.expected+["new fault"],
                      self.expected[:3]+["unknown replacement"],
                      self.expected[:3]):
            with self.subTest(lines=lines),patch(
                    "cycle04_recommendation_diagnostics.subprocess.run",
                    return_value=self.runner(lines)),self.assertRaises(ValueError):
                verify(self.root,["synthetic"])

    def test_success_without_correction_and_source_tampering_are_fatal(self):
        with patch("cycle04_recommendation_diagnostics.subprocess.run",
                   return_value=self.runner(self.expected,code=0)),self.assertRaises(ValueError):
            verify(self.root,["synthetic"])
        source=json.loads((self.root/DEBT).read_text())["items"][0]["source_path"]
        (self.root/source).write_bytes((self.root/source).read_bytes()+b" ")
        with self.assertRaises(ValueError):
            verify(self.root,["synthetic"])
if __name__=="__main__":unittest.main()
