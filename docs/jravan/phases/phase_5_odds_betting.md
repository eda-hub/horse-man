# Phase 5 — Odds forecast / Betting decision

## 目的
現行運用どおり、最終オッズを予測して買い目候補を作り、ユーザーが購入/見送りを判断できるようにする。

## 対象
- observed / predicted final / actual final odds分離
- 初期統計型Odds Forecast
- range予測
- 馬連・ワイド中心Bet Engine
- EV計算
- budget allocation
- BET / SKIP decision
- skip reason
- decision時snapshot

## 受入条件
- predicted final oddsを使って買い目を生成できる。
- 見送りでも推奨買い目が残る。
- decision時のオッズが固定保存される。
- 予想対象のみ詳細snapshotを残す保存レベルが機能する。
- PAT連携を行わない。
