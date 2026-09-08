# Phase 0 — Foundation

## 目的
新システムのPython Core基盤をクリーンな状態から作る。まだJV-Link本接続や予想ロジックは実装しない。

## 実装
- `services/core/` Python project
- `tests/` 基盤
- 設定管理
- logging
- Pydantic base models
- DuckDB connection / migration runner
- single writer abstraction
- FastAPI `/system/status`
- prod/test DB分離
- Python lint/type/test

## 受入条件
- Python lint/type/testが通る。
- `/system/status` でService/DB OKを確認できる。
- prod/test DBが分離される。
- 競馬予想ルール原本を変更しない。
- `.agents/` と `.devcontainer/` を維持する。

## 非対象
JV-Link、血統、予想、AI、オッズ、Web UI本体。
