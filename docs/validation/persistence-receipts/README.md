# 保存確認証跡

本ディレクトリは、`docs/validation/snapshots/` または `docs/validation/preservation/` に保存した**不変本体の保存・読戻し結果**を別エントリで記録する。

## 原則

- 本体を保存後の情報で更新しない。
- 本体保存要求後、保存・読戻し状態を日別 `YYYY-MM-DD.md` へ `persistence_receipt` としてappend-only追記する。読戻し未完了でも状態を隠さず記録できる。
- receiptは本体の適格性を後から変更するための文書ではなく、保存工程の事実を追跡する証跡である。
- receiptが後日作成されても、本体の発走前適格性を遡及して作らない。

## receipt IDと状態遷移

receiptはartifactごとの系列として管理し、既存receiptを上書きしない。

- `receipt_series_id`: snapshotなら `<snapshot_id>-R`、preservationなら `<preservation_id>-R`
- `receipt_id`: `<artifact_id>-RNN`（例: `...-R01`, `...-R02`）
- `previous_receipt_ref`: R02以降で直前receiptを参照する

同じreceiptエントリの書込再試行・タイムアウト確認では**同じ `receipt_id`**を使う。読戻し未完了のR01を後から成功状態へ書き換えず、状態が進んだ場合はR02のような新しいreceiptを追記し、`previous_receipt_ref` で連結する。

これにより、`READBACK_PENDING` → `PRE_RACE_ELIGIBLE` / `READBACK_AFTER_POST_INELIGIBLE` の遷移を、不変receiptの上書きなしで記録する。

## 最低項目

- `receipt_id`
- `receipt_series_id`
- `previous_receipt_ref`（R02以降）
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
- `timing_eligibility`: READBACK_PENDING / PRE_RACE_ELIGIBLE / READBACK_AFTER_POST_INELIGIBLE / TIMING_UNVERIFIED / LATE_PRESERVATION

## 時刻適格性の判定保留

snapshot候補で本体読戻しが完了していない場合は、`timing_eligibility=READBACK_PENDING` とする。

- `persist_verified_at_jst=null`
- `timing_eligibility=READBACK_PENDING`
- 発走予定時刻が確認済みでも、読戻し成功時刻が存在しない間は発走時刻との比較を行わない。
- `READBACK_PENDING` を `PRE_RACE_ELIGIBLE` または `READBACK_AFTER_POST_INELIGIBLE` と推測変換しない。
- 本体読戻しが成功した時点で、その実測 `persist_verified_at_jst` と `scheduled_post_time_jst` を比較し、新しいreceipt revisionへ最終 `timing_eligibility` を記録する。
- 読戻し失敗・未実施・成否不明のままなら `READBACK_PENDING` を維持し、前向きKPIへ適格化しない。

preservationの `TIMING_UNVERIFIED` / `LATE_PRESERVATION` は保存先事前ルーティングの状態であり、snapshot候補の `READBACK_PENDING` とは混同しない。

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
2. 同じ `receipt_id` がすでに存在し、主要内容も一致する場合は重複追記せず、そのreceiptを再利用する。receiptファイル上の存在確認ができた場合のreceipt保存状態は `RECEIPT_VERIFIED` とするが、artifactの読戻し完了や時刻適格性まで意味しない。
3. 同じ `receipt_id` で主要内容が異なる場合は `RECEIPT_ID_CONFLICT` とし、既存receiptを上書きしない。
4. receipt書込要求がタイムアウトした場合は `RECEIPT_REQUESTED_UNKNOWN` とする。**再書込の前に必ず同じ `receipt_id` を読戻す。** 存在すれば重複追記しない。
5. receipt書込が明示的に失敗した場合は `RECEIPT_WRITE_FAILED` とし、最新receiptファイルを再取得して他の追記を保持したうえで、時間に余裕がある場合だけ**最大1回**再試行する。force更新は禁止する。
6. receipt書込成功後は同じ日次作業ブランチから `receipt_id` と主要内容を確認する。確認できなければ `RECEIPT_READBACK_FAILED` とする。
7. receipt未保存・成否不明・失敗・読戻し失敗のまま回答する場合は、本体状態とは別に `receipt_persist_status` を明示し、引継ぎ票へ `receipt_id`、artifact ID、receipt path、状態、未完了工程を保持する。
8. 後続チャットは新しいreceipt revisionを生成する前に、同じ `receipt_series_id` の最新receiptを検索する。同一revisionの再送なら同じ `receipt_id` を再利用し、状態が進んだ場合だけ次のRNNを追記する。結果確認後にreceiptを作成して発走前適格性を遡及させてはならない。

## receipt自身の確認

receipt書込後は同じ日次作業ブランチから `receipt_id` と主要内容の一致を確認する。確認結果を同じreceiptへ追記せず、receiptの確認receiptも作成しない。

receiptの確認に失敗した場合は `RECEIPT_READBACK_FAILED` とし、成功扱いにしない。


## 機械監査用receiptレコード

前向きKPIや `betting-evidence-v1` のmachine gateで使用するreceiptは、
日別Markdown内に次の**独立した構造化レコード**として保存する。

```persistence-receipt-v1
{
  "receipt_id": "20260926-NAK-01-P001-S01-R02",
  "artifact_id": "20260926-NAK-01-P001-S01",
  "artifact_path": "docs/validation/snapshots/2026-09-26.md",
  "artifact_persist_status": "PERSIST_VERIFIED",
  "receipt_persist_status": "RECEIPT_VERIFIED",
  "persist_verified_at_jst": "2026-09-26T09:51:00+09:00",
  "scheduled_post_time_jst": "2026-09-26T10:10:00+09:00",
  "timing_eligibility": "PRE_RACE_ELIGIBLE"
}
```

checkerは `receipt_id` が一致する**1レコードだけ**を読み、
そのレコード内の `artifact_id`、`artifact_path`、保存状態、時刻適格性を照合し、`persist_verified_at_jst < scheduled_post_time_jst` もchecker自身で確認する。
別receiptレコードに書かれた `PRE_RACE_ELIGIBLE` を根拠として流用しない。

machine-eligibleにするreceiptでは、
`artifact_persist_status=PERSIST_VERIFIED`、
`receipt_persist_status=RECEIPT_VERIFIED`、
`timing_eligibility=PRE_RACE_ELIGIBLE`
をすべて同一レコード内に持つ。
