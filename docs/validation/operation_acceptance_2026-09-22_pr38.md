# PR #38 実装受入確認 — 2026-09-22

## 対象

- PR: #38
- repository: `eda-hub/horse-man`
- 実装ブランチ: `docs/prediction-start-daily-branch-plan-20260922`
- 正式ルール参照元: `main` の `docs/manual/README.md`
- 検証種別: 文書契約の静的受入確認
- レース回顧: **未実施**
- 実レースsnapshot作成: **未実施**

## 静的確認結果

| 確認項目 | 結果 |
|---|---|
| `eda-hub/horse-man` の直接指定 | PASS |
| `docs/manual/README.md` を正本入口とする | PASS |
| 未マージPR・将来コードをProductionへ混入させない | PASS |
| 日次作業ブランチ `prediction/YYYY-MM-DD` の命名・再利用 | PASS |
| 予想関連の `main` 直接書込み禁止 | PASS |
| タスク開始時刻と発走予定時刻の分離 | PASS |
| `PERSIST_NOT_ATTEMPTED` と実保存失敗の分離 | PASS |
| `PERSIST_REQUESTED_UNKNOWN` の読戻し解決 | PASS |
| FIXED後の回答前保存・読戻しゲート | PASS |
| 回顧側の保存状態分類との整合 | PASS |
| 見送り・投資額0円・REUSEDも保存対象 | PASS |
| 別チャット引継ぎでbranch / ID / 保存状態を保持 | PASS |
| 未試行・実行不能・成否不明を `PRE_RACE_SNAPSHOT_PERSIST_FAILED` から除外 | PASS |
| snapshot本体と保存確認receiptを分離 | PASS |
| `TIMING_UNVERIFIED` / `LATE_PRESERVATION` を通常snapshotから分離 | PASS |
| preservationから発走前復旧時は新snapshot IDで再保存 | PASS |
| 導入前main記録の初回移行手順 | PASS |
| 引継ぎ票欠落時のIDベース所属ブランチ探索 | PASS |

## レビュー指摘への是正

1. **保存失敗コード条件**
   - `PRE_RACE_SNAPSHOT_PERSIST_FAILED` は `PERSIST_WRITE_FAILED` の場合だけ使用する。
   - `PERSIST_NOT_ATTEMPTED`、`PERSIST_UNAVAILABLE`、`PERSIST_REQUESTED_UNKNOWN`、`PERSISTED_READBACK_UNVERIFIED` は保存失敗コードへ変換しない。
   - 読戻し失敗は `PRE_RACE_SNAPSHOT_READBACK_FAILED` と分離した。

2. **不変snapshotと保存確認証跡**
   - snapshot本体から `persist_verified_at_jst`、最終 `persist_status`、保存commit SHAを除外した。
   - 読戻し完了後に `docs/validation/persistence-receipts/YYYY-MM-DD.md` へ別IDでappend-only追記する。
   - receipt確認結果をreceipt自身へ再書込みしないため、再帰的な更新を発生させない。

3. **時刻未判定・発走後の保全**
   - 通常snapshotは発走予定時刻確認済みかつ本体読戻し完了が発走前の場合だけ作成する。
   - 未判定は `TIMING_UNVERIFIED`、遅延は `LATE_PRESERVATION` として `docs/validation/preservation/` に保存する。
   - 発走前に時刻確認が復旧した場合だけ、新しいsnapshot IDで通常snapshotを作成し、`previous_preservation_ref` で関連付ける。

4. **既存main記録と引継ぎ票欠落**
   - 導入前main記録は既存ID・内容を保持したまま日次ブランチへ移行する手順を追加した。
   - 引継ぎ票がない場合は `baseline_forecast_id` / `race_id` から候補日次ブランチ、近接branch、main、Git履歴の順に探索する。
   - 複数branchへ同一IDが存在し正本を決められない場合は `PREDICTION_BRANCH_AMBIGUOUS`、見つからない場合は `PREDICTION_BRANCH_NOT_FOUND` として無言再生成を禁止した。

## 実運用で未実施の確認

PR #38計画の58ケースすべてを実レースで実行したものではない。特に以下は実運用または安全な模擬実行での追加確認対象とする。

- 初回予想時の日次ブランチ実作成と、同日別チャットからの再利用
- 並行チャットでの同一snapshot追記競合
- 保存APIタイムアウト時の `PERSIST_REQUESTED_UNKNOWN` からの読戻し解決
- 発走境界直前・直後の時刻判定
- 実レースでの回答前保存ゲート

実レースの記録をテスト目的で変更しないため、本確認では実レースsnapshot・結果・払戻・KPI・回顧を作成していない。

## セルフレビュー

- 正式ルールの参照元 `main` と、予想記録の書込先である日次ブランチを分離した。
- 旧契約の「mainへ直接snapshot保存できなければ失敗」は削除し、mainへの直接書込み禁止へ置き換えた。
- 保存未試行、実行不能、成否不明、書込失敗、読戻し未確認、読戻し失敗、読戻し確認済みを別状態にし、失敗コードの適用条件を明示的失敗だけへ限定した。
- snapshot本体、保存確認receipt、時刻未判定・遅延preservationを別の不変記録として分離した。
- 導入前main記録と引継ぎ票欠落の探索・移行手順を追加した。
- 予想判断基準、確率生成、券種、資金配分、Production/Shadow境界は変更していないため `manual_release=v1.6.1` を維持する。
- `30_betting.md` は既に `00_core.md` のsnapshot契約を参照しており、48.2.1の監査項目も要件を満たすため変更していない。
