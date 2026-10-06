# 次期検証サイクル記録テンプレート（v1.7.0予定）

> 状態: 次期契約用。第3サイクルの既存記録・`cycle03_execution.md` を変更しない。

## 日別scope

- race_date_jst:
- cycle_id:
- manual_release:
- manual_ref_commit:
- initial_scope:
- final_scope:
- reviewed_scope:

## Prediction KPI

| 項目 | 対象 | 適格 | 不適格 | 保留 | 備考 |
|---|---:|---:|---:|---:|---|
| Production |  |  |  |  |  |
| Shadow |  |  |  |  |  |

## レース別記録

| race_id | baseline_forecast_id | 初回順位 | 最終順位 | 予想確信度 | 主要根拠 | 順位変更理由 | Production gate | Shadow | 回顧 |
|---|---|---|---|---|---|---|---|---|---|

## 集計

- ◎勝率:
- ◎連対率:
- ◎3着内率:
- 上位3頭勝ち馬捕捉率:
- Brier Score:
- 順位変更改善件数:
- 順位変更悪化件数:
- 無印好走馬件数:
- 根拠不足変更件数:

## 任意sidecar

市場・仮想収益検証を実行した場合だけ別集計へ記録する。Prediction対象集合・適格性へ混入しない。

- market_validation_scope:
- eligible:
- ineligible:
- pending:
- fixed_rule_return:

## 完了条件

- Prediction対象集合 = 適格 + 不適格 + 保留
- 初回・最終・回顧のrace_idを照合
- 発走後に順位・確率・根拠を新設して適格化しない
- 実購入情報なしで日別Prediction集計が完了する


## 機械可読日別台帳

日別recordでは次の `prediction-day-v2` を1日・1cycleにつき1ブロック保存する。表とJSONが矛盾する場合は修正し、結果後に対象race_idを都合よく削除しない。

```prediction-day-v2
{
  "race_date_jst": "2026-10-17",
  "cycle_id": "cycle_04",
  "manual_release": "v1.7.0",
  "initial_scope": ["race-1", "race-2"],
  "final_scope": ["race-1"],
  "reviewed_scope": ["race-1", "race-2"],
  "kpis": {
    "production": {
      "target_ids": ["race-1", "race-2"],
      "eligible_ids": ["race-1"],
      "ineligible_ids": [],
      "pending_ids": ["race-2"]
    },
    "shadow": {
      "target_ids": ["race-1"],
      "eligible_ids": [],
      "ineligible_ids": [],
      "pending_ids": ["race-1"]
    }
  }
}
```

`market_validation` はsidecarを実行した日だけ追加する。Production / Shadowの対象集合や適格性とは独立して分類する。

機械照合:

```bash
python3 scripts/check_prediction_cycle.py
```


## execution gateとの照合

`production.eligible_ids` または `shadow.eligible_ids` にrace_idを登録する場合、同日・同race_idの `prediction-compliance-v2` execution gateを必須とする。

- gateが存在しないELIGIBLEは不正。
- 日別台帳のELIGIBLE / INELIGIBLE / PENDINGとgateの `kpi_eligibility` が一致しない場合は不正。
- Production ELIGIBLEでは、gateが参照する `prediction-snapshot-v2` の内容とgate内の順位・印・確率・根拠・baseline ID等が完全一致しなければならない。
- Shadow ELIGIBLEでは、少なくとも1件のELIGIBLEなShadow evidence itemと発走前receiptを要求する。
- 非ELIGIBLEでgate自体が存在しないレースに、内容のないダミーgateを作る必要はない。
