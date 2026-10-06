# Phase 6 — Result / Review preparation / Automation

## 目的
予想後の結果結合・回顧準備・バックアップを自動化し、Production / Shadow / 任意市場検証を分離して結果へ接続する。

## 対象
- result / payout ingest
- Production / Shadow result join
- Prediction KPI materialization
- optional market validation settlement
- 初回→最終変更と結果の比較材料
- Review Package自動生成
- Scheduler / Job Queue
- Race Mode
- daily backup
- Mac backup drop
- JRA重賞Markdownとの将来同期に備えたexport interface（自動Git書込は未決事項）

## 受入条件
- 実購入・BET/SKIP情報の有無に関係なく全Production FINALが結果と結合される。
- Shadow結果をProduction成績へ混入しない。
- 低確信レースもPrediction回顧対象から除外されない。
- 仮想精算はsidecar実行時だけ行い、標準完了条件にしない。
- `baseline_forecast_id`、manual release/hashを結果・回顧まで引き継ぐ。
- service再起動後に不足jobが再開される。
- 日次backupが自動実行され、検証結果がstatusへ出る。
- `docs/yosou/jra_racing/` の現行運用を勝手に置換しない。
