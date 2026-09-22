# 保存確認証跡

本ディレクトリは、`docs/validation/snapshots/` または `docs/validation/preservation/` に保存した**不変本体の保存・読戻し結果**を別エントリで記録する。

## 原則

- 本体を保存後の情報で更新しない。
- 本体の読戻し結果が確定してから、日別 `YYYY-MM-DD.md` へ `persistence_receipt` をappend-only追記する。
- receiptは本体の適格性を後から変更するための文書ではなく、保存工程の事実を追跡する証跡である。
- receiptが後日作成されても、本体の発走前適格性を遡及して作らない。

## 最低項目

- `receipt_id`
- `artifact_type`: SNAPSHOT / PRESERVATION
- `artifact_id`: snapshot_id または preservation_id
- `working_branch`
- `artifact_path`
- `persist_requested_at_jst`
- `persist_verified_at_jst`（読戻し完了時。未完了なら null）
- `persist_status`
- 本体保存commit SHA（取得できた場合）
- 読戻し結果
- `scheduled_post_time_jst` と出所
- `timing_eligibility`

## 状態と失敗コード

- `PERSIST_NOT_ATTEMPTED`、`PERSIST_UNAVAILABLE`、`PERSIST_REQUESTED_UNKNOWN` は保存失敗ではない。
- `PRE_RACE_SNAPSHOT_PERSIST_FAILED` は、実際に送信した本体書込要求が明示的に失敗した `PERSIST_WRITE_FAILED` の場合だけ使用する。
- `PRE_RACE_SNAPSHOT_READBACK_FAILED` は、本体書込成功後の読戻しが失敗・不一致となった `PERSIST_READBACK_FAILED` の場合だけ使用する。

## receipt自身の確認

receipt書込後は同じ日次作業ブランチから `receipt_id` の存在を確認する。確認結果を同じreceiptへ追記せず、receiptの確認receiptも作成しない。
