# 時刻未判定・遅延固定内容の保全

本ディレクトリは、正式内容をFIXEDしたが**発走前適格snapshotとして確定できない内容**を失わないための保全領域である。

## 保存対象

日別 `YYYY-MM-DD.md` にappend-onlyで保存する。

- `TIMING_UNVERIFIED`：対象レースの発走予定時刻を外部根拠で確認できない。
- `LATE_PRESERVATION`：**書込要求送信前の時点ですでに発走予定時刻以後**。

これらを `docs/validation/snapshots/` へ保存して正常な発走前証跡として扱わない。

## 最低項目

- `preservation_id`
- race_id / 開催日 / 競馬場 / R
- baseline_forecast_id
- manual_release / manual_ref_commit
- fixed_at_jst
- information_cutoff_jst
- scheduled_post_time_jst と出所（不明なら UNVERIFIED）
- `timing_eligibility`: TIMING_UNVERIFIED / LATE_PRESERVATION
- working_branch
- FIXEDしたProduction / Betting / Shadowの必要内容
- 元snapshot候補IDがあればその値。ただし通常snapshotとして扱わない。

保存後の読戻し時刻・保存状態・commit SHAは本体へ追加せず、`docs/validation/persistence-receipts/` へ別証跡として追記する。

## 復旧

`TIMING_UNVERIFIED` の後で発走予定時刻を確認できた場合：

1. **新しいsnapshot書込要求を送る直前がまだ発走前**：preservationはそのまま残し、新しいsnapshot_idで `SNAPSHOT_CANDIDATE` を作成する。通常snapshotに `previous_preservation_ref` を付け、最終時刻適格性はpersistence receiptで判定する。
2. **すでに発走後**：preservationのまま維持する。通常snapshotへ移さない。
3. **最後まで時刻未確認**：TIMING_UNVERIFIEDのまま維持する。

後日の確認だけでpreservationを発走前snapshotへ名前変更・移動・遡及適格化してはならない。
