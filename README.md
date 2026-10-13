# horse-man

JRA-VAN Data Lab を利用し、価格不要の予想・推奨・記録・回顧運用と、Windows側のローカル競馬システムを構築するリポジトリです。

## 正本

| 対象 | 正本 |
|---|---|
| 競馬予想ルール | `docs/manual/README.md` と `docs/manual/*.md` |
| 現行ルール版 | `docs/manual/README.md` の `現行リリース`（PR79のmainマージ後 `v1.7.0`） |
| JRA重賞の長期予想記録 | `docs/yosou/jra_racing/README.md` と各 `<race>.md` |
| 進行中Shadow検証 | `docs/validation/` |
| システム設計 | `DECISIONS.md` と `docs/jravan/` |
| Codex実装指示 | `AGENTS.md` と `.agents/` |

競馬予想ルールは、`00_core → 10_prediction → 20_conditional → 30_betting` をProductionの基本方向とし、Production固定後に `40_shadow`、結果確定後に `50_review` を使用します。システム実装でもこの境界を壊しません。

## 目標

- Windows 11 VM上のJV-LinkからJRA-VANデータを取得
- DuckDB + Parquetへ蓄積
- ChatGPT/GitとCLIで予想・価格不要推奨・独立保存・回顧を実施（WebUIは対象外）
- Production基準予想とShadow比較を分離して記録
- 市場価格・最終オッズ予測は任意sidecarで検証
- 推奨の有無と予想確信度を独立記録
- 初回全scopeと選定済み最終を保存し、公式結果照合・回顧
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
