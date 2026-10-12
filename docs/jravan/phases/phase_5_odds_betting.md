# Phase 5 — 任意Market/Odds validation

## 目的

固定Production/Recommendationを変更せず、60_marketに従う価格観測・予測・任意仮想収益を独立sidecarとして実装する。価格不要推奨の前提ではない。

## 受入

観測/予測最終/実最終オッズ、出所・時点・応答hashを分離する。未試行/失敗/締切を期待値不足と混同しない。前向き固定した仮想額/券/価格だけを任意ROIへ使用し、Prediction/推奨KPIへ混ぜない。実購入・ユーザー予算・BET/SKIP状態・PAT連携を新規中核へ追加しない。
