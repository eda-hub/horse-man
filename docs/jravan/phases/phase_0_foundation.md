# Phase 0 — Foundation

## 目的
新Python Coreを既存TypeScript CLIと共存させる土台を作る。まだJV-Link本接続や予想ロジックは実装しない。

## 実装
- `services/core/` Python project
- 設定管理
- logging
- Pydantic base models
- DuckDB connection / migration runner
- single writer abstraction
- FastAPI `/system/status`
- test DB分離
- Python lint/type/test

## 受入条件
- 既存 `npm run check` が通る。
- Python testが通る。
- `/system/status` でService/DB OKを確認できる。
- prod/test DBが分離される。
- 既存CLI・records・ルール原本に変更を加えない。

## 非対象
JV-Link、血統、予想、AI、オッズ。
