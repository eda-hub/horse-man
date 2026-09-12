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
- `docs/manual/README.md` と各module front matterをread-onlyで検査するManual Contract Checkerの最小骨格

## 受入条件
- Python lint/type/testが通る。
- `/system/status` でService/DB OKを確認できる。
- prod/test DBが分離される。
- Manual Contract Checkerが現行releaseとmodule release一致/不一致を判定できる。
- `docs/manual/`、`docs/yosou/`、`docs/validation/` を変更しない。
- `.agents/` と `.devcontainer/` を維持する。

## 非対象
JV-Link、血統、予想ロジック、AI、オッズ、Web UI本体。
