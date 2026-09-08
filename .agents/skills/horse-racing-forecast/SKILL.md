---
name: horse-racing-forecast
description: horse-manのJRA-VAN競馬予想システムを、設計書と競馬予想ルール原本に従ってCodexで段階実装・検証する。
---

# Horse Racing Forecast System

`競馬予想ルール原本_v1.4.1.md` を競馬判断の正本、`DECISIONS.md` と `docs/jravan/` をシステム設計の正本として使う。

## 実装開始時
1. ルートの `AGENTS.md` を読む。
2. `DECISIONS.md` と `docs/jravan/00_project_plan.md` を読む。
3. 実装対象Phaseの `docs/jravan/phases/phase_*.md` を読む。
4. 対象領域の詳細設計書だけ追加で読む。
5. Phaseの受入条件を満たす最小実装を行う。

## 共通制約
- Phaseを跨いで先回り実装しない。
- 旧Node/TypeScript CLIを復元しない。
- `.agents/` と `.devcontainer/` を削除しない。
- 競馬予想ルール原本を自動改変しない。
- FINAL予想を上書き可能にしない。
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
