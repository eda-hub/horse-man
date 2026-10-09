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

## 次期推奨買い目（PR68 §25、Stage 2発効後）

- Production順位・印・確率・根拠を固定した後、**オッズ非依存**で同時好走シナリオ・着順適性から券種と具体的な馬番構成を生成する。
- PR69の先行実装は `scripts/recommendation.py` の単純な◎中心候補生成・全7券種の検証・独立推奨gate。Phase 3のアプリ実行コード・全券種自動候補展開は依然未実装。
- `baseline_forecast_id`・Prediction snapshot hash・推奨契約versionとdata cutoffを保持し、オッズ/人気/資金変動だけで推奨を再生成しない。
- 根拠不十分なら`NO_RECOMMENDATION`、処理未完了なら`PENDING`とし、Production認証を無効にしない。
- ☆・非◎保険縦目の流用はしない。未決の点数上限・閾値を暗黙に決めない。

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
