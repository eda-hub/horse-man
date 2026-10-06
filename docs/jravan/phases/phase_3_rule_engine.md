# Phase 3 — Feature / Production / Shadow engine

## 目的
`docs/manual/` のモジュール契約に従い、AIなしでProduction基準予想とShadow比較を再現可能に生成する中核を作る。

## 対象
- feature_run / runner_feature
- data_cutoff
- Manual Contract Resolver
- `module + rule_id` 実装マッピング
- `baseline_forecast_id`
- 10_prediction Production baseline
- Production順位→印の決定的マッピング
- prediction evidence（fact/source/time/direction/strength）
- 20_conditional formal adjustments
- Production freeze
- 40_shadow comparison engine
- 近5走相手レベル / 開催傾向 / 新馬専用評価のShadow feature受け皿
- PRE/DAY/FINAL prediction snapshots
- manual release / manifest hash / module hashes
- rule application理由

## 受入条件
- 未来情報混入テストが通る。
- 必須module release不一致時に処理を停止する。
- 同じmanual release、engine version、snapshotから同じProduction評価を再現できる。
- 上位Production順位を説明する構造化根拠を再現できる。
- 印がProduction順位から一意に導出され、印のために順位を変更しない。
- Shadowは固定済Productionを親としてのみ生成できる。
- ShadowがProduction順位・確率を変更できない。
- オッズだけの変化で `baseline_forecast_id` を再発行しない。
- FINAL確定済み履歴を結果に合わせて上書きしない。
- `docs/manual/` を変更・複製して別正本を作らない。
- `docs/yosou/jra_racing/` の代表レースで適用rule IDsを説明できる。
- 新規featureはdata_cutoff/provenanceを保持し、初期状態ではProductionへ逆流しない。
