#!/usr/bin/env python3
"""推奨厳格監査の非0を保持し、固定4診断と新規回帰を区別する。"""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEBT = "docs/validation/reconciliations/2026-10-17-recommendation-historical-debts.json"

def verify(root, command=None):
    debt=json.loads((root/DEBT).read_text(encoding="utf-8"))
    if not (debt.get("schema_version")=="recommendation-historical-debt-inventory-v1"
            and debt.get("formal_kpi_eligibility")=="INELIGIBLE"
            and debt.get("count_expected")==4 and len(debt.get("items",[]))==4):
        raise ValueError("過去の推奨不足原票の契約/件数が一致しない")
    expected=set()
    for item in debt["items"]:
        if not item.get("code") or item.get("expected_error") in expected:
            raise ValueError("過去診断コードが不明/重複")
        expected.add(item["expected_error"])
        path=item["source_path"]
        if not path.startswith("docs/validation/") or ".." in Path(path).parts:
            raise ValueError("過去原票の不正な参照")
        raw=(root/path).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=item["source_sha256"]:
            raise ValueError("過去原票のSHA-256改変: "+path)
    executed=subprocess.run(command or [sys.executable,str(root/"scripts/recommendation.py"),"--audit"],
                            cwd=root,capture_output=True,text=True)
    diagnostics=[row[len("RECOMMENDATION_INCOMPLETE "):]
                 for row in (executed.stdout+"\n"+executed.stderr).splitlines()
                 if row.startswith("RECOMMENDATION_INCOMPLETE ")]
    if executed.returncode!=1 or len(diagnostics)!=4 or set(diagnostics)!=expected:
        raise ValueError("推奨厳格監査で未知の不足・診断変化・改変・成功偽装: status="+
                         str(executed.returncode)+" diagnostics="+repr(diagnostics))
    return {"schema_version":"cycle04-recommendation-audit-status-v1",
            "strict_audit_exit_code":executed.returncode,
            "historical_unresolved_diagnostics":len(diagnostics),
            "new_or_changed_diagnostics":0,
            "state":"HISTORICAL_UNRESOLVED",
            "forward_recommendation_complete":False,
            "formal_kpi_certified":False,
            "source":DEBT}

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root",type=Path,default=ROOT)
    p.add_argument("--audit",action="store_true")
    args=p.parse_args(argv)
    try:
        print("CYCLE04_RECOMMENDATION_AUDIT "+json.dumps(verify(args.root.resolve()),ensure_ascii=False))
        return 0
    except (ValueError,OSError) as exc:
        print("新規/改変推奨不足または監査不合格: "+str(exc),file=sys.stderr)
        return 1
if __name__=="__main__":raise SystemExit(main())
