# Phase 5 — Odds forecast / Market validation

## 目的
Production基準予想を変えずに最終オッズを予測し、市場との乖離・価格予測精度・任意の固定ルール仮想検証を実装する。実購入・ユーザー予算・BET/SKIPは本Phaseの必須責務にしない。

## 対象
- observed / predicted final / actual final odds分離
- 初期統計型Odds Forecast
- range予測
- Market Evaluation
- Market Evaluation
- 価格予測誤差評価
- optional fixed-rule virtual validation
- market validation snapshot
- method_version / data_cutoff / fixed_at

## 受入条件
- predicted final oddsを市場評価に使用できる。
- 価格情報だけでProduction基準順位・基準確率が変わらない。
- 市場検証を実行しなくてもPrediction KPIが完了できる。
- 市場検証が能力評価へ逆流しない。
- sidecar実行時のオッズ・method version・fixed_atが固定保存される。
- オッズ更新だけで `baseline_forecast_id` が変わらない。
- 予想対象のみ詳細snapshotを残す保存レベルが機能する。
- 実購入・PAT連携を行わない。
- 仮想検証は結果後に券種・selection・stakeを変更しない。
