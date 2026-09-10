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
    |- Rule Engine
    |- Prediction Engine
    |- Odds Forecast Engine
    |- Bet Engine
    |- Settlement Engine
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

## 責務分離
### JV-Link Adapter
COM/JV-Link固有仕様を内部に閉じ込める。下流はJV-Link型ではなく内部DTOだけを見る。

### Keiba Core Service
DuckDBへの書込を一か所に集約する。複数workerによる同一DBファイルへの書込を避ける。

### Web UI
表示とユーザー意思決定に専念する。OSコマンドやJV-Linkを直接呼ばない。

### AI Adapter
Review Packageだけを外部AIへ渡し、DBやファイルシステムへの直接権限を持たせない。

## 予定ディレクトリ
```text
horse-man/
  .agents/                    # Codex設定/スキル
  .devcontainer/              # Codex開発環境
  services/
    core/                     # Python FastAPI/Core
    jvlink/                   # Windows/JV-Link adapter
  apps/
    web/                      # Web UI（Phase 4）
  db/
    migrations/
  rules/                      # 構造化ルール。原本はルートで保持
  tests/
  docs/jravan/
  scripts/
  競馬予想ルール原本_v1.4.1.md
```

Gitは空ディレクトリを保持しないため、実ディレクトリは各Phaseの実装開始時に作成する。

## プロセス
本番Windows VMではCore Serviceのworker数は1を基本とし、並列処理は内部タスクと読み取り側で行う。DB writeはWrite Queue経由にする。
