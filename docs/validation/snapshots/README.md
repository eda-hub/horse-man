# 発走前不変snapshot

本ディレクトリは、チャット予想で正式固定したProduction / Betting / Shadowの**結果確認前の最小証跡**を保存する。

## 1. 目的

- baseline_forecast_idとProduction内容を後日の回顧で確実に参照できるようにする。
- 既存Productionの無断再生成を防ぐ。
- 初期→最終差分、購入前監査、Shadow完了状態を結果後に捏造・再構成しない。
- チャット履歴の参照可能性だけに正式KPIを依存させない。

## 2. 保存タイミング

分析途中では保存しない。

原則：

**分析・監査完了 → 正式内容FIXED → 本ディレクトリへ保存 → 同内容をチャット送信**

とする。

依頼を受けた時点で、[保存事前宣言と直後確認](../persistence-intents/README.md)を行う。全レース予想では対象scopeを先に保存し、snapshot・receiptの読戻し後に直後照合する。保存確認に失敗しても発走前の回答を遅らせず、実際の未保存範囲を明示する。

全体選別は対象全レースを1回のsnapshotへまとめてよい。個別最終・買い目更新は当該レースだけを追記してよい。

## 3. 保存先と正規参照先

日別に、

`YYYY-MM-DD.md`

へappend-onlyで保存する。

正式ルールの参照元は `main` だが、snapshotの書込先と読戻し先は当該作業日の**日次作業ブランチ `prediction/YYYY-MM-DD`** とする。JSTの初回予想時に1本だけ作成し、同日の別レース・別チャットでは再利用する。翌日の回顧・再開も元予想が属する日次ブランチを継続して使用し、日付が変わったことだけを理由に移動しない。

`main` への予想関連の直接コミットは禁止する。日次作業ブランチへ保存できない場合も `main` へフォールバックしない。

既存snapshotを編集して現在値だけにしない。正式更新では新しいsnapshotを追記し、前snapshotを参照する。

保存前には**同じ日次作業ブランチ**の対象日ファイルの最新内容を再取得し、他の実行コンテキストによる追記を保持する。snapshot本体はFIXED時点の内容だけを不変で保存し、保存後に確定する読戻し時刻・保存状態・commit SHAは本体へ追記しない。保存確認証跡は `docs/validation/persistence-receipts/YYYY-MM-DD.md` の別エントリへ追記する。

`snapshot_id` は `00_core.md` の正本定義に従う。

- 個別レース：`<baseline_forecast_id>-SNN`
- 全体選別：`YYYYMMDD-WHOLE-SNN`

後続snapshotは `previous_snapshot_ref` で直前snapshotを参照する。

## 4. 最低項目

### Production

- snapshot_id
- snapshot_type
- race_id
- baseline_forecast_id
- manual_release
- manual_ref_commit
- contract_effective_date
- task_started_at_jst
- scheduled_post_time_jst と出所
- fixed_at_jst
- working_branch
- information_cutoff_jst
- timing_route: SNAPSHOT_CANDIDATE
- previous_preservation_ref（時刻未確認から発走前に復旧した場合）
- previous_snapshot_ref
- production_status: NEW / REUSED / UPDATED
- 順位・印
- 勝率 / 連対率 / 3着内率
- 予想確信度
- 選別区分・購入優先度（該当時）
- 当日馬体重取得状態
- 市場を能力順位へ使用していないことの状態
- 変更時は変更対象、非価格理由、証拠強度、情報時刻

### Betting

固定買い目がある場合：

- 購入確信度
- 買い / 見送り
- 使用価格と取得時刻
- 固定10,000円案
- 最大馬依存額・率
- 券種成立確率と合理的レンジ下側
- 軸崩れシナリオ
- 監査後判断：維持 / 配分変更 / 総投資削減 / 見送り
- 判断理由

### Shadow

- 適用対象
- 完了 / 未完了 / 非該当
- 完了した場合だけ発走前比較内容
- 未完了理由が発走前に判明していればその理由

## 4.1 保存確認証跡はsnapshot本体と分離する

snapshot本体には、保存後にしか確定しない次の値を書かない。

- `persist_verified_at_jst`
- 最終 `persist_status`
- snapshot保存commit SHA
- 読戻し結果

これらは本体の読戻し後、`docs/validation/persistence-receipts/YYYY-MM-DD.md` に `persistence_receipt` としてappend-only追記する。receiptは `artifact_id=snapshot_id` で本体を参照し、本体を更新しない。

receipt自身の書込確認は、同じ日次ブランチから `receipt_id` と主要内容の一致を確認する。確認結果をreceiptへ再度書き戻さない。書込失敗・タイムアウト・競合・限定再試行・引継ぎは `docs/validation/persistence-receipts/README.md` の契約に従う。

## 4.2 保存先の事前判断と最終時刻適格性を分離する

通常snapshotへの保存可否を、保存後にしか確定しない読戻し時刻で事前判定しない。

書込要求を送る直前に次だけで保存先を決める。

- 発走予定時刻確認済み、かつ現在時刻が発走予定時刻より前：`snapshots/YYYY-MM-DD.md` へ `timing_route: SNAPSHOT_CANDIDATE` として保存する。
- 発走時刻未確認：`preservation/YYYY-MM-DD.md` へ `TIMING_UNVERIFIED` として保全する。
- 書込要求送信前から発走予定時刻以後：`preservation/YYYY-MM-DD.md` へ `LATE_PRESERVATION` として保全する。

`SNAPSHOT_CANDIDATE` は発走前KPI適格を意味しない。snapshot本体の読戻し後、`persistence-receipts/` 側でのみ最終時刻適格性を判定する。

- 読戻し未完了・失敗・成否不明：`READBACK_PENDING`
- 読戻し成功時刻が発走予定時刻より前：`PRE_RACE_ELIGIBLE`
- 読戻し成功時刻が発走予定時刻以後：`READBACK_AFTER_POST_INELIGIBLE`

`READBACK_PENDING` の間は `persist_verified_at_jst=null` とし、発走予定時刻との比較を実施しない。読戻し成功が確認できるまで前向きKPIへ適格化しない。

例えば15:29:59に本体書込、15:30:01に読戻し、15:30発走なら、本体は不変の `SNAPSHOT_CANDIDATE` のまま残し、receiptだけを `READBACK_AFTER_POST_INELIGIBLE` とする。本体を訂正しない。

preservation後に発走予定時刻を確認でき、**新しい書込要求の直前がまだ発走前**なら、新しい `snapshot_id` の `SNAPSHOT_CANDIDATE` を作り、`previous_preservation_ref` で保全IDを参照する。最終適格性はそのsnapshotのreceiptで判定する。

preservationを後から通常snapshotへ名前変更・移動して発走前証跡に見せることは禁止する。

## 5. 禁止事項

- 結果後に発走前snapshotを新規作成して適格化する
- 結果・払戻・着順を書く
- 結果後コメントを発走前根拠として追記する
- 古いsnapshotを上書き・削除する
- 未確認を見送り・非該当へ置換する
- Shadow欠落を理由にProduction snapshotを無効化する

## 6. 保存・再送・競合・読戻し

保存処理は次で判定する。

1. `docs/validation/daily-branches/README.md` に従って `working_branch` を確定する。引継ぎ票がない場合や導入前main記録は、同READMEの探索・移行手順を先に実施する。
2. 書込要求送信前の発走予定時刻と現在時刻だけで、`SNAPSHOT_CANDIDATE` かpreservationかを決定する。
3. 対象の日次作業ブランチ・対象ファイルを取得する。
4. 同じ本体IDがなければ、FIXED済み内容だけを末尾へ追記する。
5. 同じID・同じ内容があれば重複追記せず既存本体を再利用する。同じID・異なる内容は `SNAPSHOT_ID_CONFLICT` とし、上書きしない。
6. 本体保存後に同じ日次作業ブランチから読戻す。
7. 読戻しが未完了ならreceiptへ `timing_eligibility=READBACK_PENDING` を記録できる。読戻し成功後にのみ実測時刻を比較し、同じreceipt系列の次revisionへ最終 `timing_eligibility` を追記する。本体へは書き戻さない。
8. 本体の競合等では最新内容を取り直し、他の追記を保持して最大1回だけ再試行する。force更新は禁止する。
9. 本体書込タイムアウト等で成否が不明な場合は `PERSIST_REQUESTED_UNKNOWN` とし、同一本体IDを読戻して解決する。
10. receipt保存は `docs/validation/persistence-receipts/README.md` の独立した保存・復旧契約に従う。

### 既存ブランチ・ファイルと書込拒否

- 当日ブランチが存在する場合は再利用する。ファイルが存在する場合は、同ブランチの最新内容とblob SHAを取得し、既存内容を保持した追記として更新する。既存ファイルに新規作成APIを送って失敗した場合は、更新APIに切り替えて同一内容を保存する。
- 更新の競合は新しいblob SHAを取得し、`snapshot_id` の重複・内容一致を照合して一度だけ再試行する。既存のスプリンターズSを含む別セクションを削除しない。
- 実行環境の安全性審査が書込要求を拒否した場合は、その拒否理由・拒否対象・送信前か送信後かを記録する。単なるファイル競合と混同しない。許可された別の安全な保存経路があれば同一内容を保存・読戻しする。審査をすり抜けるために同一の禁止操作を別APIへ付け替えない。
- GitHubへ保存できないまま発走する場合も、FIXED済みの全レース内容と候補・買い目を発走前回答に出し、未保存範囲をレース単位で特定する。後で復旧できた原文は実際の保存時刻で保全し、9:30保存済みなどと遡及表示しない。
- Actionsの成否はこの保存手順の開始条件にしない。保存とreceiptの読戻しを先に行い、監査で見つかった不足は別の修正対象として残す。

保存状態は、`PERSIST_NOT_ATTEMPTED` / `PERSIST_UNAVAILABLE` / `PERSIST_REQUESTED_UNKNOWN` / `PERSIST_WRITE_FAILED` / `PERSISTED_READBACK_UNVERIFIED` / `PERSIST_READBACK_FAILED` / `PERSIST_VERIFIED` を区別する。

- `PERSIST_NOT_ATTEMPTED`：保存工程漏れ。保存失敗ではない。
- `PERSIST_UNAVAILABLE`：書込要求を送る手段・権限・branchがなく、要求自体を送れていない。保存失敗ではない。
- `PERSIST_REQUESTED_UNKNOWN`：要求済みだが成否不明。保存失敗ではない。
- `PERSIST_WRITE_FAILED`：送信した書込要求が明示的に失敗した。
- `PERSISTED_READBACK_UNVERIFIED`：書込成功、読戻し未実施。
- `PERSIST_READBACK_FAILED`：書込成功後の読戻しが失敗または不一致。
- `PERSIST_VERIFIED`：読戻しで本体一致を確認した。

見送り、正式投資額0円、ProductionのREUSED、短い回答指定でも、正式FIXEDした内容は回答前保存ゲートの対象とする。

発走前に保存・読戻しまで完了できない場合は、予想回答を発走に遅らせない。

チャットには正式内容とともに実際の保存状態を明示する。

- `PRE_RACE_SNAPSHOT_PERSIST_FAILED` は `PERSIST_WRITE_FAILED` の場合だけ使用する。
- `PRE_RACE_SNAPSHOT_READBACK_FAILED` は `PERSIST_READBACK_FAILED` の場合だけ使用する。
- `PERSIST_NOT_ATTEMPTED`、`PERSIST_UNAVAILABLE`、`PERSIST_REQUESTED_UNKNOWN`、`PERSISTED_READBACK_UNVERIFIED` に保存失敗コードを付けない。
- 発走前までに `PERSIST_VERIFIED` へ到達できなかった事実はKPI不適格・未判定の根拠にはなるが、保存失敗コードの根拠にはしない。

結果後に同じ内容をGitへ追加しても「発走前Git保存済み」にはならない。KPI適格性は `docs/validation/README.md` の要件で独立判定する。

## 7. 役割分離

- `snapshots/`：発走前に書込要求を開始した不変snapshot候補。最終適格性はreceiptで判定
- `persistence-receipts/`：snapshot / preservation本体の保存確認証跡
- `preservation/`：時刻未確認・発走後等の固定内容保全。前向きKPIには使わない
- `records/`：結果後の正式回顧・KPI・実購入・エラー分類
- `cycle_02.md`：サイクル集計
- `docs/yosou/`：重賞等の翌年用レース固有知識

本ディレクトリを結果後回顧の保存先として使用しない。


## 8. 別チャット・別モデルへの引継ぎ

引継ぎ時は会話要約だけに依存せず、少なくとも次を短い引継ぎ票として渡す。

- repository: `eda-hub/horse-man`
- manual_ref_commit
- 対象race_id
- baseline_forecast_id
- 最新snapshot_id
- working_branch
- snapshot path
- artifact_persist_status
- persist_requested_at_jst / persist_verified_at_jst
- snapshot保存commit SHA
- receipt_id / receipt path
- receipt_persist_status
- timing_eligibility（receiptが存在する場合）
- 未完了工程
- 発生中のHARD STOP / FAIL-SOFT状態

後続実行は、引継ぎ票があればその `working_branch` から本体とreceiptを再取得してから継続する。引継ぎ票がない場合は `docs/validation/daily-branches/README.md` の所属ブランチ探索を実行する。取得不能時に基準予想・買い目・Shadowを記憶から再生成しない。正式ルール自体はその時点の `main` のmanualを参照し、既存予想に記録済みの `manual_ref_commit` も保持する。


## 第3サイクルの候補台帳・取得引継ぎ

`00_core` 0.0.12をOwnerとし、正式なWHOLE_DAY/個別snapshotに `cycle_id`、初回scope、検証/購入フラグ、選定理由・時刻・履歴、未取得項目の取得予定段階・出所・範囲を含める。[記録テンプレート](../templates/cycle03_execution.md) を使用する。候補台帳だけを結果後に新設して事前選定を装わない。買い目にはticket_purposeを持たせ、検証用だけの案を正式ROIへ混ぜない。
