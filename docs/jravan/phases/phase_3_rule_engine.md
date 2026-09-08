# Phase 3 — Feature / Rule engine

## 目的
AIなしで予想評価を生成できる中核を作る。

## 対象
- feature_run / runner_feature
- data_cutoff
- common/race-specific rule schema
- Rule Engine
- ability/suitability/pace/pedigree/trend score
- rule hit理由
- PRE/DAY/FINAL prediction history
- rule hash/version

## 受入条件
- 未来情報混入テストが通る。
- 同じversionとsnapshotから同じ評価を再現できる。
- FINAL確定後に上書きされない。
- 既存ルール原本を直接変更しない。
- 過去の代表レースfixtureで適用ルールを説明できる。
