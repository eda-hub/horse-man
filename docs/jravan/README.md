# JRA-VAN local prediction system docs

このディレクトリは、`horse-man` を JRA-VAN Data Lab 対応のローカル予想・記録・回顧システムとして新規実装するための設計書である。

## 読む順番
1. `00_project_plan.md` — 目的、範囲、全体計画
2. `01_architecture.md` — Mac / Windows VM / Python / Web UI 構成
3. `02_database_design.md` — DuckDBのER・テーブル方針
4. `03_jravan_mapping.md` — JV-Dataから内部DBへの対応
5. `04_prediction_engine.md` — 特徴量、ルール、予想、買い目
6. `05_odds_design.md` — 最終オッズ予測と保存戦略
7. `06_webui.md` — 予想画面、回顧AI画面、管理画面
8. `07_review_ai.md` — AI回顧とルール改善ライフサイクル
9. `08_backup_recovery.md` — 自動バックアップと復旧
10. `09_security.md` — Windows VM、Python、DB、ネットワーク
11. `10_operations.md` — 開催日の自動ジョブ、障害復旧
12. `12_testing_quality.md` — テスト、バックテスト品質、過学習防止
13. `phases/` — Codexに渡すフェーズ別実装計画

`DECISIONS.md` は横断的な確定事項の正本とする。
