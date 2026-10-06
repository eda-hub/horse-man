# Architecture

## 全体構成
```text
Mac
  Browser / PWA
      |
      | Parallels private/shared network
      v
Windows 11 VM
  Keiba Core Service (single process / single DB writer)
    |- JV-Link Adapter
    |- Ingest / Parser / Validator
    |- Scheduler / Job Queue
    |- Feature Engine
    |- Manual Contract Resolver
    |- Production Prediction Engine
    |- Conditional Adjustment Engine
    |- Shadow Engine
    |- Odds Forecast Engine
    |- Market Validation Engine (optional)
    |- Result Join / KPI Engine
    |- Review Package Builder
    |- AI Adapter
    |- Backup Engine
    `- FastAPI
        |
        v
      DuckDB
        + Parquet archive
        + limited RAW storage
```

## 競馬ルールとの境界
`Manual Contract Resolver` は `docs/manual/README.md` と必要なOwnerモジュールから、`manual_release`、モジュールhash、ルールID、Production/Shadow権限を読み取る。MarkdownをDB用ルールへ勝手に再解釈せず、実装済みのルールロジックとrule IDの対応を検証する。

価格情報はOdds/Market Validation層で扱い、`10_prediction` の基準能力順位・確率・印へ逆流させない。ShadowはProduction固定後にだけ実行する。実購入・ユーザー予算はCore ServiceのPrediction必須入力にしない。

## 責務分離
### JV-Link Adapter
COM/JV-Link固有仕様を内部に閉じ込める。下流はJV-Link型ではなく内部DTOだけを見る。

### Keiba Core Service
DuckDBへの書込を一か所に集約する。複数workerによる同一DBファイルへの書込を避ける。

### Web UI
Prediction・根拠・結果・回顧・任意市場検証の表示と操作に専念する。OSコマンドやJV-Linkを直接呼ばない。実購入操作やPAT連携を提供しない。

### AI Adapter
Review Packageだけを外部AIへ渡し、DBやファイルシステムへの直接権限を持たせない。

## 現在のリポジトリ構成
```text
horse-man/
  .agents/                    # Codex設定/スキル
  .devcontainer/              # Codex開発環境
  docs/
    manual/                   # 競馬予想ルール正本
    yosou/
      jra_racing/             # JRA重賞長期記録
      kaigai/                 # 海外競馬記録
    validation/               # 現行検証サイクル
    jravan/                   # 本システム設計
  AGENTS.md
  DECISIONS.md
```

## Phase実装で追加予定
```text
services/
  core/                       # Python FastAPI/Core
  jvlink/                     # Windows/JV-Link adapter
apps/
  web/                        # Web UI
db/
  migrations/
tests/
scripts/
```

`rules/` を別の正本として新設しない。構造化ルール表現が必要な場合は生成物/実装マッピングとして扱い、`docs/manual/` のreleaseとhashへ必ず紐付ける。

## プロセス
本番Windows VMではCore Serviceのworker数は1を基本とし、並列処理は内部タスクと読み取り側で行う。DB writeはWrite Queue経由にする。
