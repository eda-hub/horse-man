# JRA-VAN local prediction system docs

このディレクトリは、`horse-man` を JRA-VAN Data Lab 対応のローカル予想・記録・回顧システムとして実装するための設計書である。

## 競馬ドメイン側の正本
システム設計は競馬ルールを再定義しない。実装時は次を参照する。

- `docs/manual/README.md`: 現行ルールreleaseとモジュールmanifest
- `docs/manual/00_core.md`: 実行契約、Production/Shadow境界、`baseline_forecast_id`
- `docs/manual/10_prediction.md`: Production基準予想
- `docs/manual/20_conditional.md`: Production条件別補正・重賞51A
- `docs/manual/30_betting.md`: v1.6.1までの市場・Betting Owner。次期契約では任意市場検証へ縮小予定
- `docs/manual/40_shadow.md`: Shadow比較
- `docs/manual/50_review.md`: 回顧・検証・ルール変更管理
- `docs/yosou/jra_racing/README.md`: JRA重賞の長期記録運用
- `docs/validation/`: 現行検証サイクル

## システム設計を読む順番
1. `00_project_plan.md` — 目的、範囲、全体計画
2. `01_architecture.md` — Mac / Windows VM / Python / Web UI 構成
3. `02_database_design.md` — DuckDBのER・テーブル方針
4. `03_jravan_mapping.md` — JV-Dataから内部DBへの対応
5. `04_prediction_engine.md` — モジュール化ルールとPrediction Engineの対応
6. `05_odds_design.md` — 最終オッズ予測と保存戦略
7. `06_webui.md` — 予想画面、回顧AI画面、管理画面
8. `07_review_ai.md` — AI回顧とルール改善ライフサイクル
9. `08_backup_recovery.md` — 自動バックアップと復旧
10. `09_security.md` — Windows VM、Python、DB、ネットワーク
11. `10_operations.md` — 開催日の自動ジョブ、障害復旧
12. `11_source_provenance.md` — 情報種別ごとの一次取得元、fallback、出典独立性、source bias対策
13. `12_testing_quality.md` — テスト、バックテスト品質、過学習・source bias防止
14. `15_prediction_feature_expansion.md` — 相手レベル、開催傾向、新馬、条件別統計のfeature契約
15. `phases/` — Codexに渡すフェーズ別実装計画

`DECISIONS.md` は横断的な確定事項の正本とする。競馬判断の意味に矛盾がある場合、`docs/manual/` を優先し、システム設計側を修正する。

血統調査の初期Git基盤: [保存・検索手順](../../data/pedigree/README.md)。計画の正本はPR68、コードと過去候補移行はPR69。JRA-VANアプリのPhase順は変更せず、DB移行はPhase 2、派生根拠固定はPhase 3、表示はPhase 4、評価・昇格はPhase 8へ引き継ぐ。
