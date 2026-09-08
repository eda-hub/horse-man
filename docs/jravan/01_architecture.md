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
既存構造を壊さず段階的に以下へ寄せる。

```text
horse-man/
  src/                         # 既存TypeScript CLI（当面維持）
  test/                        # 既存テスト
  services/
    core/                      # Python FastAPI/Core（Phase 0以降）
    jvlink/                    # Windows/JV-Link adapter
  apps/
    web/                       # Web UI（Phase 4）
  db/
    migrations/
  rules/                       # 将来。原本からの正式移行までは作成のみ
  records/                     # 既存記録
  docs/jravan/
  scripts/
```

Gitは空ディレクトリを保持しないため、実ディレクトリは各Phaseの実装開始時に作成する。

## プロセス
本番Windows VMではCore Serviceのworker数は1を基本とし、並列処理は内部タスクと読み取り側で行う。DB writeはWrite Queue経由にする。
