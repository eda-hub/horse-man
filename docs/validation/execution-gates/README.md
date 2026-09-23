# Execution Compliance Gate

このディレクトリは、チャットやAIの自己申告ではなく、機械判定で予想・買い目・回顧のルール準拠状態を確定するための実行台帳を置く。

## 原則

- AIが `PASS` と書いても準拠扱いにしない。
- `scripts/check_prediction_compliance.py` が終了コード0を返した場合だけ、当該execution gateを機械的に準拠とする。
- 第3サイクルの日別machine ledgerへrace_idを載せる場合、対応するexecution gate JSONを必須とする。
- 発走後に作ったReplay Shadowは、結果を入力へ直接使っていなくても `ELIGIBLE` にできない。
- KPIを `ELIGIBLE` にするには、参照artifactとreceiptが実在し、receipt近傍に `PRE_RACE_ELIGIBLE` が存在することをcheckerが確認する。
- E-11はv1.6.1の確信度尺度矛盾が解消されるまで `PENDING_RULE_CONFLICT` 以外を許可しない。
- 買い目は採用前の `natural_candidates` を必ず保持する。採用しなかった候補には `rejected_candidates.reason` を要求する。
- ◎を含まない馬連・ワイド・馬単は例外扱い。保険、依存率低下、予算消化では通さない。独立シナリオ、保守側成立確率、価格、`EV > 1.0` を機械確認する。
- 非◎縦目の `reason_code` は allowlist 方式とし、現行は `INDEPENDENT_POSITIVE_EV` だけを許可する。未知の理由コードは拒否する。
- 非◎縦目の `probability_low` と `odds` はgate内の自己申告値だけでは認証しない。`betting-evidence-v1` の発走前構造化証跡と完全一致し、そのartifactのreceiptが同一レコードで `PRE_RACE_ELIGIBLE` / `PERSIST_VERIFIED` / `RECEIPT_VERIFIED` を満たす場合だけ監査済みとする。
- 発走後Replayで新規算出した確率・価格は `betting-evidence-v1` の前向き証跡として扱わない。必要証跡がない買い目は `FIXED` にせず `BLOCKED` または参考案として保持する。
- 検証用正式買い目は合計10,000円を機械確認する。
- 回顧完了には結果取得URL・取得時刻、KPI適格性、反実仮想、非劣化の「保護/再検証/改善対象」を必須とする。

## 保存先

`docs/validation/execution-gates/YYYY-MM-DD/<race_id>.json`

## 最小例

```json
{
  "schema_version": "prediction-compliance-v1",
  "race_id": "20260926-NAK-01",
  "race_date_jst": "2026-09-26",
  "mode": "FORWARD",
  "working_branch": "prediction/2026-09-26",
  "manual_release": "v1.6.1",
  "manual_ref_commit": "40文字のcommit SHA",
  "scheduled_post_time_jst": "2026-09-26T10:10:00+09:00",
  "timing_route": "SNAPSHOT_CANDIDATE",
  "production": {
    "baseline_forecast_id": "20260926-NAK-01-P001",
    "marks": {"honmei": 1, "taikou": 2, "tanana": 3},
    "fixed_at_jst": "2026-09-26T09:50:00+09:00",
    "evidence_ref": {
      "artifact_path": "docs/validation/snapshots/2026-09-26.md",
      "artifact_id": "20260926-NAK-01-P001-S01",
      "receipt_path": "docs/validation/persistence-receipts/2026-09-26.md",
      "receipt_id": "20260926-NAK-01-P001-S01-R02",
      "timing_eligibility": "PRE_RACE_ELIGIBLE",
      "persist_verified_at_jst": "2026-09-26T09:51:00+09:00"
    }
  },
  "kpi_eligibility": {
    "production": "ELIGIBLE",
    "betting": "PENDING",
    "shadow": "PENDING"
  },
  "shadow_items": [
    {"item_id": "E-11", "state": "PENDING_RULE_CONFLICT", "kpi_eligibility": "PENDING"}
  ],
  "betting": {"status": "NOT_REQUIRED"},
  "review": {"status": "NOT_STARTED"}
}
```

## 機械判定

ローカル:

```bash
python3 -m unittest discover -s scripts -p 'test_*.py'
python3 scripts/check_prediction_compliance.py
python3 scripts/check_cycle03.py
```

GitHub Actionsでも同じcheckerを実行する。

## 強制境界

このgateは「チャットが回答文を表示すること」自体をOSレベルで止めるものではない。代わりに、gateを通っていない出力を正式Production、正式Betting、Shadow KPI、cycle集計へ登録できないようにする。

つまりチャットは提案者であり、**正式性の判定者はchecker**とする。


## 非◎縦目の発走前数値証跡

`vertical_exception` は次を満たす必要がある。

- `reason_code=INDEPENDENT_POSITIVE_EV`
- `scenario_id`
- `probability_low`
- `odds`
- `ev_low = probability_low * odds > 1.0`
- `evidence_ref`

`evidence_ref` は `docs/validation/betting-evidence/YYYY-MM-DD/<race_id>.json` 等の
`betting-evidence-v1` artifactを参照し、そのartifact自身が発走前receiptで検証済みでなければならない。

checkerは、gateの `type / horses / scenario_id / probability_low / odds` と、
artifact内の対応するprice/probability recordを完全一致で照合する。
