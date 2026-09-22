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
- 保存未試行、成否不明、書込失敗、読戻し未確認、読戻し失敗、読戻し確認済みを別状態にした。
- 予想判断基準、確率生成、券種、資金配分、Production/Shadow境界は変更していないため `manual_release=v1.6.1` を維持する。
- `30_betting.md` は既に `00_core.md` のsnapshot契約を参照しており、48.2.1の監査項目も要件を満たすため変更していない。
