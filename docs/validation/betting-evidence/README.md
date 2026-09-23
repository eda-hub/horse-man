# Betting Evidence

`betting-evidence-v1` は、買い目監査で使用する価格・確率をgate JSONの自己申告値から分離し、発走前に固定するための構造化証跡である。

## 保存条件

- 発走前に日次作業branchへ保存する。
- artifact自身に persistence receipt を発行し、同じreceiptレコード内で `PERSIST_VERIFIED` / `RECEIPT_VERIFIED` / `PRE_RACE_ELIGIBLE` を確認する。
- 発走後Replayで新規作成した値を前向き証跡として扱わない。
- 価格は取得元URLと観測時刻を必須とする。
- 確率は `scenario_id` と算出根拠を示す `method_ref`、固定時刻を必須とする。

## schema

```json
{
  "schema_version": "betting-evidence-v1",
  "evidence_id": "20260926-NAK-01-BET-E01",
  "race_id": "20260926-NAK-01",
  "prices": [
    {
      "type": "WIDE",
      "horses": [2, 6],
      "odds": 11.1,
      "source_url": "https://...",
      "observed_at_jst": "2026-09-26T10:00:00+09:00"
    }
  ],
  "probabilities": [
    {
      "type": "WIDE",
      "horses": [2, 6],
      "scenario_id": "S2_...",
      "probability_low": 0.095,
      "method_ref": "baseline_forecast_id or probability-model revision",
      "fixed_at_jst": "2026-09-26T09:59:00+09:00"
    }
  ]
}
```

## checker照合

非◎縦目を `FIXED` にする場合、checkerは以下を完全一致で照合する。

- 券種
- 馬番集合
- `scenario_id`
- `probability_low`
- `odds`
- artifactの `evidence_id`
- 対応receiptの `artifact_id` / `artifact_path`
- receiptの保存状態と `PRE_RACE_ELIGIBLE`

gate側で価格・確率を書き換えても、発走前artifactと一致しなければ不合格となる。
