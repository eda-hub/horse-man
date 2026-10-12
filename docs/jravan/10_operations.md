> v1.7.0 / PR79のmainマージ後の正式境界：標準はPrediction→価格不要Recommendation→公式結果/回顧。実購入・予算・購入確認・実購入ROIは中核対象外。市場は60_marketの任意sidecar、WebUIは対象外/N/A。以下の旧BET/SKIP/実購入設計は履歴であり新規runtimeへ移植しない。正式Ownerはdocs/manual、関連Phase3/5/6を参照。Windows/JRA-VAN実接続の受入をチャット/Git運用成功で代用しない。

# Operations and automation

## Core Service内ジョブ
Windows Task Schedulerへ多数の個別タスクを作るのではなく、Core Service内部SchedulerとJob Queueを基本とする。

`ops.job_run`: job_type, scheduled_at, started_at, finished_at, status, records_read, records_written, error

`ops.data_watermark`: source, last_success_at, source_timestamp, record_key

## 開催日フロー
```text
service start
 -> watermark確認 / catch-up
 -> JVWatchEvent開始
 -> manual contract整合性確認
 -> race/runner更新
 -> PRE feature / Production baseline
 -> 当日馬場更新
 -> DAY conditional adjustment
 -> 馬体重発表event受信時に0B11即時取得・保存
 -> 未取得レースのみ0B11 fallback polling
 -> T-20 FINAL readiness verification
 -> 最新の馬場・取消変更等を更新
 -> FINAL readiness gate
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

## FINAL readiness gate
発走前FINALは原則としてT-20以降にreadinessを再検証して確定する。ただし、**馬体重だけはT-20以降に新規取得した値であることを要求しない**。当日公式馬体重は通常それより前に発表されるため、発表時点で取得・保存済みの完全なWHをT-20で再検証して使用する。

最低限、次を必須非価格データとして扱う。

- 当日馬体重と増減（現出走対象馬のcoverageが完全であること）
- 最新の公式馬場状態・天候
- 取消・競走除外
- 騎手・斤量・発走時刻等の変更event

取得元は次の優先順位とする。

1. JRA-VAN/JV-Link速報（馬体重は `JVEvtWeight` + `0B11` を主経路）
2. JRA-VAN `0B11` のtargeted catch-up / polling
3. JRA公式一次情報による照合・障害時フォールバック
4. 補助Webソースは確認用途のみ

ブラウザGUIでJavaScriptにより描画される値が静的HTML取得で欠落する場合があるため、静的HTMLで空欄だから「未発表」と判定してはならない。

必須項目が取得できない場合は値を推測せず、`data_readiness=DEGRADED` として欠損項目、最終成功時刻、取得失敗時刻、source、acquisition methodを保存する。DEGRADED状態でFINALを確定する場合は、予想確信度・購入確信度を下げ、回顧で予想ロジック失敗とデータ取得失敗を分離する。

## 馬体重取得ジョブ
### Primary: event-driven
開催日はJV-Link初期化後に `JVWatchEvent` を開始する。`JVEvtWeight` を受信したら、返却されたrace keyをそのまま `JVRTOpen("0B11", key)` に渡し、対象レースのWHを即時保存する。これを通常経路とする。

### Catch-up
Core Service起動・再起動時はEvent受信履歴だけに依存せず、予想対象レースについて `0B11` を問い合わせ、既に発表済みの馬体重を回収する。race-keyで不足する場合、開催日単位取得で照合してよい。

### Polling fallback
Event通知の欠落、JVWatchEvent停止、夏季等の発表タイミング差を吸収するため、未取得の対象レースだけ次の目安でtargeted pollingする。

`T-75 -> T-65 -> T-55 -> T-45 -> T-35 -> T-25 -> T-20`

- `READY` になった時点でそのレースの馬体重pollingを停止する。
- `PARTIAL` の場合だけ不足馬を照合しながら継続する。
- 固定の「T-60に必ず出る」「T-20で初めて取る」という前提を置かない。
- JRAから季節・競馬場別の計量/発表時刻変更が告知されている場合は、その情報をexpected windowの補助に使うが、Event監視を主とする。

### T-20 verification
T-20では少なくとも1回、現在のrunner構成と保存済みWHのcoverageを再照合する。必要なら `0B11` のtargeted catch-upを1回実行する。T-20より前に取得済みでも完全な当日WHなら `READY` のままとし、取得時刻だけを理由に `STALE` へ落とさない。

## 障害切り分け
T-20時点で当日馬体重が完全でない場合、次の順に切り分ける。

1. `JVEvtWeight` の受信有無、JV-Link初期化・event watcher状態を確認。
2. `JVRTOpen(0B11, race-key)` を直接再実行。
3. 必要なら開催日単位 `0B11` で回収し、race-key生成/絞込不良を切り分ける。
4. JRA-VAN公式の動作確認ツールで同一データが取得できるか確認する。公式ツールで取得できるならAdapter/Parser側、取得できないなら未提供・通信・ローカルJV-Data環境側を疑う。
5. JRA公式の出馬表等に表示済みかを照合する。表示済みなのに内部取得できなければ `SOURCE_ERROR` とする。

検索indexや補助サイトの静的HTMLは切り分けの根拠補助に留め、そこが空欄でも `MISSING` と即断しない。

## manual contract
起動時と予想実行前に `docs/manual/README.md` の現行releaseと、利用する必須moduleの `manual_release` を検査する。不一致時は予想ジョブをfail closedし、データ取得・バックアップ等の安全なジョブだけ継続可能とする。

## baseline_forecast_id
チャット、UI再読込、オッズ更新だけを理由にProduction基準予想を再作成しない。正式な非価格情報更新条件を満たす場合だけ `docs/manual/00_core.md` の契約に従って更新する。

## Race Mode
非開催日は低頻度。開催日は発走時刻を基準に必要なjobだけ増やす。全レース全券種を常時高頻度取得しない。馬体重は開催中のEvent監視を基本にし、予想対象レースで未取得の場合だけ上記fallback cadenceを適用する。馬場・変更event等の時点依存情報はT-20前後で優先更新する。

## 再実行性
すべてのingest/settlement jobはidempotentにする。PC停止後もwatermarkから不足分を再開できること。Eventを取り逃してもcatch-upで復旧でき、固定済みProductionを再実行で上書きしない。

## Git記録との関係
JRA重賞の長期記録は `docs/yosou/jra_racing/`、進行中Shadow検証は `docs/validation/` の現行運用を尊重する。DBからGitへの自動同期は方式決定まで実装せず、まずexport可能な境界を作る。

## 障害表示
JRA-VAN外部停止、JVWatchEvent停止、0B11取得失敗、DB障害、Parserエラー、Manual Contract不整合、Backup失敗、FINAL必須データ欠損を別statusとして表示する。「通信できない=DB故障」「静的HTMLで空欄=未発表」と短絡しない。

## 例外
取消、競走除外、騎手変更、斤量変更、馬場変更、発走変更、中止、同着、失格、競走中止、返還、Event取り逃し、Core Service再起動、0B11部分取得をテストケースに含める。
