# Phase 5 — Odds forecast / Betting decision

## 目的
Production基準予想を変えずに最終オッズを予測し、`docs/manual/30_betting.md` に従う市場評価・推奨候補・ユーザー購入条件・BET/SKIP判断を実装する。

## 対象
- observed / predicted final / actual final odds分離
- 初期統計型Odds Forecast
- range予測
- Market Evaluation
- rule-defined ticket candidate generation
- EV/価格評価
- ユーザー指定馬/券種/予算/リスク入力
- 指定条件内の最終購入設計
- BET / SKIP decision
- skip reason
- decision時snapshot

## 受入条件
- predicted final oddsを市場評価に使用できる。
- 価格情報だけでProduction基準順位・基準確率が変わらない。
- 見送りでも推奨候補が残る。
- ユーザー指定条件が能力評価へ逆流しない。
- decision時のオッズが固定保存される。
- オッズ更新だけで `baseline_forecast_id` が変わらない。
- 予想対象のみ詳細snapshotを残す保存レベルが機能する。
- PAT連携を行わない。
