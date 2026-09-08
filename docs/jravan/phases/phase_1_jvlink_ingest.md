# Phase 1 — JV-Link ingest

## 目的
Windows VMでJV-Linkから最低限のレースデータを安全に取得し、DuckDBへ保存する。

## 対象
- JV-Link Adapter
- RA / SE / UMを中心とした最小Parser
- race / horse / runner / resultのmigration
- validation
- RAW一時保存
- watermark
- idempotent ingest
- Windows実機integration test

## 受入条件
- 指定日のレース一覧をDBへ取り込める。
- 同じ範囲を2回取得しても重複しない。
- 中断後にwatermarkから再開できる。
- 過去レースをAPIから参照できる。
- JV-Link固有型がPrediction層へ漏れない。
