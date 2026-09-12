# Phase 6 — Result / Settlement / Automation

## 目的
予想後の記録・精算・回顧準備・バックアップを自動化し、Production / Shadow / 実購入を分離して結果へ接続する。

## 対象
- result / payout ingest
- Production推奨のtheoretical settlement
- Shadow comparison settlement
- actual purchase settlement
- GOOD SKIP / MISSED OPPORTUNITY等の判断評価材料
- Review Package自動生成
- Scheduler / Job Queue
- Race Mode
- daily backup
- Mac backup drop
- JRA重賞Markdownとの将来同期に備えたexport interface（自動Git書込は未決事項）

## 受入条件
- BET/SKIPに関係なく全Production FINALが結果と結合される。
- Shadow結果をProduction成績へ混入しない。
- 見送りレースも仮想精算される。
- `baseline_forecast_id`、manual release/hashを結果・回顧まで引き継ぐ。
- service再起動後に不足jobが再開される。
- 日次backupが自動実行され、検証結果がstatusへ出る。
- `docs/yosou/jra_racing/` の現行運用を勝手に置換しない。
