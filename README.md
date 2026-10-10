# horse-man

JRA-VAN Data Lab を利用し、個人のMacからWeb UIで操作するローカル競馬予想・記録・回顧システムを構築するリポジトリです。

## 正本

| 対象 | 正本 |
|---|---|
| 競馬予想ルール | `docs/manual/README.md` と `docs/manual/*.md` |
| 現行ルール版 | `docs/manual/README.md` の `現行リリース`（現在 `v1.6.1`） |
| JRA重賞の長期予想記録 | `docs/yosou/jra_racing/README.md` と各 `<race>.md` |
| 進行中Shadow検証 | `docs/validation/` |
| システム設計 | `DECISIONS.md` と `docs/jravan/` |
| Codex実装指示 | `AGENTS.md` と `.agents/` |

競馬予想ルールは、`00_core → 10_prediction → 20_conditional → 30_betting` をProductionの基本方向とし、Production固定後に `40_shadow`、結果確定後に `50_review` を使用します。システム実装でもこの境界を壊しません。

## 目標

- Windows 11 VM上のJV-LinkからJRA-VANデータを取得
- DuckDB + Parquetへ蓄積
- Macのブラウザから予想・市場評価・買い目候補を確認
- Production基準予想とShadow比較を分離して記録
- 最終オッズを予測し、買い目候補と買い条件/見送り条件を提示
- ユーザーが購入 / 見送りを最終判断
- 見送りを含む全FINAL予想を保存・結果精算・回顧
- AIは回顧、仮説生成、ルール改善候補の作成に使用
- バックアップと結果記録を自動化

## 現在の主な構成

```text
horse-man/
  .agents/                # Codex設定・スキル
  .devcontainer/          # Codex開発環境
  docs/
    manual/               # 競馬予想ルール正本
    yosou/
      jra_racing/         # JRA重賞の長期記録
      kaigai/             # 海外競馬記録
    validation/           # 現行Shadow検証サイクル
    jravan/               # JRA-VANシステム設計
  AGENTS.md
  DECISIONS.md
```

## 実装

システム実装計画は `docs/jravan/README.md` から参照してください。Codexは `AGENTS.md` と対象Phaseを読み、Phase 0から段階実装します。

自動投票、PAT連携、銀行情報の保存、公開Webサービス化は対象外です。


## PR69の調査・準備実装の現在値（2026-10-10）

父/母父613頭と追加指定祖先12頭の調教国は確認待ち0。海外42登録行の必要5代血統2,604位置を保存済み。旧482記述の保守分類と過去保存不足40件の当日Git再照合を別記録に保存した。JRA159レース・2,182登録行・2,177実出走に対する父/母父EU・USと指定祖先21条件、計25条件をREPLAYで保存/readback。結果はCOMPLETE。欧州対象国は利用者指定の英・愛・仏・独・伊。

[受入結果と残件](data/pedigree/acceptance.md)を参照。未検証の旧解釈・仮説と過去の保存不足、Yorkの結果原票、未選定集計は保持する。第3サイクル終了前の正式切替は行わず、非UIアプリは前提成立後に独立PRで実装する。WebUIは実施対象外。
