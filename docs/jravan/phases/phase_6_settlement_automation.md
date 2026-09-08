# Phase 6 — Result / Settlement / Automation

## 目的
予想後の記録・精算・回顧準備・バックアップを自動化する。

## 対象
- result / payout ingest
- theoretical settlement
- actual purchase settlement
- GOOD SKIP / MISSED OPPORTUNITY等の判断評価材料
- Review Package自動生成
- Scheduler / Job Queue
- Race Mode
- daily backup
- Mac backup drop

## 受入条件
- BET/SKIPに関係なく全FINALが結果と結合される。
- 見送りレースも仮想精算される。
- service再起動後に不足jobが再開される。
- 日次backupが自動実行され、検証結果がstatusへ出る。
