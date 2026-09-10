# Operations and automation

## Core Service内ジョブ
Windows Task Schedulerへ多数の個別タスクを作るのではなく、Core Service内部SchedulerとJob Queueを基本とする。

`ops.job_run`: job_type, scheduled_at, started_at, finished_at, status, records_read, records_written, error

`ops.data_watermark`: source, last_success_at, source_timestamp, record_key

## 開催日フロー
```text
service start
 -> watermark確認 / catch-up
 -> race/runner更新
 -> PRE feature/prediction
 -> 当日馬場更新
 -> DAY prediction
 -> 馬体重取得
 -> observed odds取得
 -> FINAL prediction / predicted final odds / bet recommendation
 -> ユーザー BET or SKIP
 -> 結果/払戻取得
 -> theoretical settlement
 -> actual settlement（購入記録がある場合）
 -> Review Package生成
 -> backup
```

## Race Mode
非開催日は低頻度。開催日は発走時刻を基準に必要なjobだけ増やす。全レース全券種を常時高頻度取得しない。

## 再実行性
すべてのingest/settlement jobはidempotentにする。PC停止後もwatermarkから不足分を再開できること。

## 障害表示
JRA-VAN外部停止、DB障害、Parserエラー、Backup失敗を別statusとして表示する。「通信できない=DB故障」にしない。

## 例外
取消、競走除外、騎手変更、斤量変更、馬場変更、発走変更、中止、同着、失格、競走中止、返還をテストケースに含める。
