# 日次作業ブランチ運用

チャット予想の正式記録は、JSTの初回作業日に対応する `prediction/YYYY-MM-DD` へ保存する。

## 作成と再利用

- 初回予想開始時に `prediction/YYYY-MM-DD` の存在を確認する。
- 存在しなければ、その時点の `main` 最新commitから1本だけ作成する。
- 同日の別レース・別チャット・再開では同じブランチを再利用する。
- 競合や取得エラーを「不存在」とみなして同名ブランチを作り直さない。
- 日付変更だけを理由に、進行中の予想・回顧を新しい日次ブランチへ移さない。
- 予想関連の書込みを `main` へ直接行わない。

## 導入前のmain記録を初回移行する

本契約導入前に `main` へ直接保存された進行中の予想には `working_branch` が存在しない。この場合、既存予想を捨てて新しいProductionを作り直さず、次の順序で初回移行する。

1. `baseline_forecast_id` を第一キー、なければ `race_id`・開催日・競馬場・Rを補助キーとして、`main` の `docs/validation/snapshots/`、`docs/validation/records/`、関連する予想記録を確認する。
2. 対象作業日の `prediction/YYYY-MM-DD` が**存在しない場合だけ**、現在の `main` に対象予想が存在するなら、その時点の最新 `main` commitを基点として日次ブランチを作成する。
3. 対象日次ブランチが**すでに存在する場合は再作成・ref更新・resetを行わない**。まず既存branchのsnapshot / preservation / recordsを読取り、対象 `baseline_forecast_id` がすでに存在するか確認する。
4. 既存日次ブランチに対象IDが存在する場合は、その記録を正として再利用する。main側の同一IDを重複追加しない。
5. 既存日次ブランチに対象IDがなく、main側に導入前記録が存在する場合は、既存branchの他記録を保持したまま**対象IDに必要な記録だけ**を移行する。ファイル全体をmain版で置換せず、append-only・ID競合規則に従う。
6. 現在の `main` にはなくGit履歴だけに対象予想が存在する場合、対象記録が確認できる最新のmain系commitを移行元として特定する。記録内容・ID・時刻を推測で復元しない。
7. 日次ブランチ側に対象予想が保持されていることを読戻し、`baseline_forecast_id` と主要内容の一致を確認してから継続する。
8. 移行後の更新・snapshot・回顧は日次ブランチへ保存し、`main` へ直接追記しない。
9. 移行元commit、working_branch、対象ID、既存branchを再利用したかを日次ブランチの引継ぎ情報へ保持する。

導入前のmain記録そのものを削除・書換えしない。移行は今後の書込先を切り替える処理であり、過去の保存場所を遡及的に変更する処理ではない。

## 引継ぎ票がない場合の所属ブランチ探索

引継ぎ票が欠落していても、記憶から予想を再生成せず次の順序で探索する。

1. `baseline_forecast_id` に日付が含まれる場合、そのJST日付の `prediction/YYYY-MM-DD` を第一候補にする。含まれない場合はrace_id・開催日から候補日を決める。
2. 第一候補ブランチの `snapshots/`、`preservation/`、`persistence-receipts/`、`records/` から `baseline_forecast_id` / `race_id` を照合する。
3. 見つからない場合は、近接日の `prediction/*` ブランチを列挙し、同じIDを検索する。ブランチ名だけで所属を確定しない。
4. 日次ブランチで見つからない場合は `main` の現行内容とGit履歴を検索し、導入前main記録かを確認する。該当する場合は上記「導入前のmain記録を初回移行する」に従う。
5. 1つのIDが複数の作業ブランチに存在し、正本を一意に決められない場合は `PREDICTION_BRANCH_AMBIGUOUS` としてHARD STOPし、どちらかを推測で選ばない。
6. どのブランチ・main履歴にも見つからない場合は `PREDICTION_BRANCH_NOT_FOUND` とし、新しい正式Productionで無言置換しない。

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
- snapshot / preservation の保存commit SHA
- migration_source_commit（導入前main記録を移行した場合）
- migration_target_reused: true / false
- receipt_id / receipt path / receipt_persist_status
- 未完了工程
- HARD STOP / FAIL-SOFT状態

後続実行は、引継ぎ票がある場合はそのbranchとIDを読戻してから継続する。引継ぎ票がない場合は本書の「所属ブランチ探索」に従う。どちらの場合も記憶だけでProduction・買い目・Shadowを再生成しない。

## マージ

回顧・必要記録が完了した後に通常のPRレビューで `main` へ反映する。マージ済みかどうかと、発走前に日次ブランチへ保存済みだったかは別の事実として扱う。後日のマージ時刻を発走前保存時刻として扱わない。
