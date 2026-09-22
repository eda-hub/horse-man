# 日次作業ブランチ運用

チャット予想の正式記録は、JSTの初回作業日に対応する `prediction/YYYY-MM-DD` へ保存する。

## 作成と再利用

- 初回予想開始時に `prediction/YYYY-MM-DD` の存在を確認する。
- 存在しなければ、その時点の `main` 最新commitから1本だけ作成する。
- 同日の別レース・別チャット・再開では同じブランチを再利用する。
- 競合や取得エラーを「不存在」とみなして同名ブランチを作り直さない。
- 日付変更だけを理由に、進行中の予想・回顧を新しい日次ブランチへ移さない。
- 予想関連の書込みを `main` へ直接行わない。

## 参照境界

- 正式ルール: `main` の `docs/manual/README.md` から参照する。
- 予想・snapshot・結果記録・回顧: 元予想が属する日次作業ブランチで継続する。
- 日次ブランチ内に未承認のmanual変更があっても、正式Productionルールとして採用しない。

## 引継ぎ票

別チャット・別モデルへ継続するときは、最低限次を保持する。

- repository: `eda-hub/horse-man`
- working_branch
- race_id
- baseline_forecast_id
- latest_snapshot_id
- snapshot path
- manual_release / manual_ref_commit
- persist_status
- persist_requested_at_jst / persist_verified_at_jst
- snapshot保存commit SHA
- 未完了工程
- HARD STOP / FAIL-SOFT状態

後続実行は、引継ぎ票のbranchとIDを読戻してから継続する。記憶だけでProduction・買い目・Shadowを再生成しない。

## マージ

回顧・必要記録が完了した後に通常のPRレビューで `main` へ反映する。マージ済みかどうかと、発走前に日次ブランチへ保存済みだったかは別の事実として扱う。後日のマージ時刻を発走前保存時刻として扱わない。
