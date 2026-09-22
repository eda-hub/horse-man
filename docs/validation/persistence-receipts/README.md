# 保存確認証跡

本ディレクトリは、`docs/validation/snapshots/` または `docs/validation/preservation/` に保存した**不変本体の保存・読戻し結果**を別エントリで記録する。

## 原則

- 本体を保存後の情報で更新しない。
- 本体の読戻し結果が確定してから、日別 `YYYY-MM-DD.md` へ `persistence_receipt` をappend-only追記する。
- receiptは本体の適格性を後から変更するための文書ではなく、保存工程の事実を追跡する証跡である。
- receiptが後日作成されても、本体の発走前適格性を遡及して作らない。

## receipt ID

`receipt_id` はartifactごとに決定的に生成し、再試行・別チャットでも同じIDを使う。

- snapshot: `<snapshot_id>-R01`
- preservation: `<preservation_id>-R01`

同じartifactの保存確認をやり直すために新しいreceipt IDを乱発しない。内容訂正が必要な場合は既存receiptを上書きせず、原因を明記した新revisionを別IDとして追加する。

## 最低項目

- `receipt_id`
- `artifact_type`: SNAPSHOT / PRESERVATION
- `artifact_id`: snapshot_id または preservation_id
- `working_branch`
- `artifact_path`
- `persist_requested_at_jst`
- `persist_verified_at_jst`（読戻し完了時。未完了なら null）
- `artifact_persist_status`
- 本体保存commit SHA（取得できた場合）
- 本体読戻し結果
- `scheduled_post_time_jst` と出所
- `timing_eligibility`: PRE_RACE_ELIGIBLE / READBACK_AFTER_POST_INELIGIBLE / TIMING_UNVERIFIED / LATE_PRESERVATION

## 状態と失敗コード

- `PERSIST_NOT_ATTEMPTED`、`PERSIST_UNAVAILABLE`、`PERSIST_REQUESTED_UNKNOWN` は保存失敗ではない。
- `PRE_RACE_SNAPSHOT_PERSIST_FAILED` は、実際に送信した本体書込要求が明示的に失敗した `PERSIST_WRITE_FAILED` の場合だけ使用する。
- `PRE_RACE_SNAPSHOT_READBACK_FAILED` は、本体書込成功後の読戻しが失敗・不一致となった `PERSIST_READBACK_FAILED` の場合だけ使用する。

## receipt保存状態

本体の保存状態とreceipt自身の保存状態は別に管理する。本体が `PERSIST_VERIFIED` でもreceiptが確認できなければ、KPI証跡は完了扱いにしない。

receipt自身は少なくとも次を区別する。

- `RECEIPT_NOT_ATTEMPTED`：receipt書込要求をまだ送っていない。
- `RECEIPT_UNAVAILABLE`：書込手段・権限・対象branch等が利用できず、receipt要求自体を送れていない。
- `RECEIPT_REQUESTED_UNKNOWN`：receipt要求済みだがタイムアウト等で成否不明。
- `RECEIPT_WRITE_FAILED`：実際に送信したreceipt書込要求が明示的に失敗した。
- `RECEIPT_READBACK_FAILED`：receipt書込成功後、同じ `receipt_id` の存在・主要内容を確認できない。
- `RECEIPT_VERIFIED`：同じ日次作業ブランチから `receipt_id` と主要内容を確認できた。

receiptが `RECEIPT_VERIFIED` になるまで、`artifact_persist_status=PERSIST_VERIFIED` だけを理由に前向きKPI証跡完了としない。

## receiptの保存・復旧

1. receipt書込前に、同じ日次作業ブランチの当日receiptファイルを再取得する。
2. 同じ `receipt_id` がすでに存在し、主要内容も一致する場合は重複追記せず、そのreceiptを再利用して `RECEIPT_VERIFIED` とする。
3. 同じ `receipt_id` で主要内容が異なる場合は `RECEIPT_ID_CONFLICT` とし、既存receiptを上書きしない。
4. receipt書込要求がタイムアウトした場合は `RECEIPT_REQUESTED_UNKNOWN` とする。**再書込の前に必ず同じ `receipt_id` を読戻す。** 存在すれば重複追記しない。
5. receipt書込が明示的に失敗した場合は `RECEIPT_WRITE_FAILED` とし、最新receiptファイルを再取得して他の追記を保持したうえで、時間に余裕がある場合だけ**最大1回**再試行する。force更新は禁止する。
6. receipt書込成功後は同じ日次作業ブランチから `receipt_id` と主要内容を確認する。確認できなければ `RECEIPT_READBACK_FAILED` とする。
7. receipt未保存・成否不明・失敗・読戻し失敗のまま回答する場合は、本体状態とは別に `receipt_persist_status` を明示し、引継ぎ票へ `receipt_id`、artifact ID、receipt path、状態、未完了工程を保持する。
8. 後続チャットはreceiptを新規生成する前に同一 `receipt_id` を検索し、既存receiptを再利用できるか確認する。結果確認後にreceiptを作成して発走前適格性を遡及させてはならない。

## receipt自身の確認

receipt書込後は同じ日次作業ブランチから `receipt_id` と主要内容の一致を確認する。確認結果を同じreceiptへ追記せず、receiptの確認receiptも作成しない。

receiptの確認に失敗した場合は `RECEIPT_READBACK_FAILED` とし、成功扱いにしない。
