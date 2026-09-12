---
name: horse-racing-forecast
description: horse-manのJRA-VAN競馬予想システムを、現行のモジュール化競馬予想ルールと設計書に従ってCodexで段階実装・検証する。
---

# Horse Racing Forecast System

競馬判断の正本は `docs/manual/`、システム設計の正本は `DECISIONS.md` と `docs/jravan/` とする。ルールの入口は必ず `docs/manual/README.md`。

## 実装開始時
1. ルートの `AGENTS.md` を読む。
2. `docs/manual/README.md` を読み、現行 `manual_release` とOwner構造を確認する。
3. `DECISIONS.md` と `docs/jravan/00_project_plan.md` を読む。
4. 実装対象Phaseの `docs/jravan/phases/phase_*.md` を読む。
5. 実装対象が予想ロジックに関係する場合だけ、必要なOwnerモジュールを読む。
6. JRA重賞記録に関係する場合は `docs/yosou/jra_racing/README.md`、Shadow検証に関係する場合は `docs/validation/` の現行サイクルを確認する。
7. Phaseの受入条件を満たす最小実装を行う。

## ルール境界
- Productionの基本方向は `00_core → 10_prediction → 20_conditional → 30_betting`。
- `40_shadow` はProduction固定後の比較系で、Productionへ逆流させない。
- `50_review` は結果後の回顧・検証・変更管理で、過去Productionを遡及変更しない。
- 必須モジュール間の `manual_release` が一致しなければ処理を停止する。
- `baseline_forecast_id` を予想の同一性キーとして保持する。
- PRE / DAY / FINALはデータ時点のsnapshotであり、上記Owner境界を置き換えない。

## 共通制約
- Phaseを跨いで先回り実装しない。
- 旧Node/TypeScript CLIを復元しない。
- `.agents/` と `.devcontainer/` を削除しない。
- `docs/manual/` を実装都合で自動改変しない。
- `docs/manual/` と重複するルール正本を `rules/` 等に作らない。
- FINAL予想を結果に合わせて上書き可能にしない。
- 見送りレースを記録・回顧対象から除外しない。
- AIをPrediction Engineの必須依存にしない。
- AIにDB/OS/ルールの直接変更権限を与えない。
- PAT、自動投票、銀行情報保存を実装しない。
- `data_cutoff` より未来の情報をバックテスト/予想へ混入させない。

## 完了時
- テストを追加・実行する。
- Phase受入条件を確認する。
- 設計変更があれば `DECISIONS.md` または対象docsを更新する。
- 次Phaseの機能を混ぜずにPRを完結させる。
