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
