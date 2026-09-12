# Operations and automation

## Core Service内ジョブ
Windows Task Schedulerへ多数の個別タスクを作るのではなく、Core Service内部SchedulerとJob Queueを基本とする。

`ops.job_run`: job_type, scheduled_at, started_at, finished_at, status, records_read, records_written, error

`ops.data_watermark`: source, last_success_at, source_timestamp, record_key

## 開催日フロー
```text
service start
 -> watermark確認 / catch-up
 -> manual contract整合性確認
 -> race/runner更新
 -> PRE feature / Production baseline
 -> 当日馬場更新
 -> DAY conditional adjustment
 -> 馬体重・非価格情報更新
 -> Production FINAL snapshot固定
 -> 必要時Shadow比較生成
 -> observed odds取得 / predicted final odds更新
 -> 30_betting市場評価 / 推奨候補
 -> ユーザー購入条件入力
 -> BET or SKIP
 -> 結果/払戻取得
 -> Production theoretical settlement
 -> Shadow comparison settlement
 -> actual settlement（購入記録がある場合）
 -> Review Package生成
 -> backup
```

## manual contract
起動時と予想実行前に `docs/manual/README.md` の現行releaseと、利用する必須moduleの `manual_release` を検査する。不一致時は予想ジョブをfail closedし、データ取得・バックアップ等の安全なジョブだけ継続可能とする。

## baseline_forecast_id
チャット、UI再読込、オッズ更新だけを理由にProduction基準予想を再作成しない。正式な非価格情報更新条件を満たす場合だけ `docs/manual/00_core.md` の契約に従って更新する。

## Race Mode
非開催日は低頻度。開催日は発走時刻を基準に必要なjobだけ増やす。全レース全券種を常時高頻度取得しない。

## 再実行性
すべてのingest/settlement jobはidempotentにする。PC停止後もwatermarkから不足分を再開できること。固定済みProductionを再実行で上書きしない。

## Git記録との関係
JRA重賞の長期記録は `docs/yosou/jra_racing/`、進行中Shadow検証は `docs/validation/` の現行運用を尊重する。DBからGitへの自動同期は方式決定まで実装せず、まずexport可能な境界を作る。

## 障害表示
JRA-VAN外部停止、DB障害、Parserエラー、Manual Contract不整合、Backup失敗を別statusとして表示する。「通信できない=DB故障」にしない。

## 例外
取消、競走除外、騎手変更、斤量変更、馬場変更、発走変更、中止、同着、失格、競走中止、返還をテストケースに含める。
