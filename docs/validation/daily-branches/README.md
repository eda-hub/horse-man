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
3. 対象日次ブランチが**すでに存在する場合は再作成・ref更新・resetを行わない**。まず既存branchとmain側の両方から、対象 `baseline_forecast_id` に属する全snapshotの `snapshot_id`、`previous_snapshot_ref`、主要内容を列挙する。
4. baselineが存在することだけで移行完了としない。branch側とmain側の**snapshot ID集合と参照履歴を比較**する。
5. 同じ `snapshot_id` が両方に存在し主要内容も一致する場合は重複追加しない。同じIDで内容が異なる場合は `SNAPSHOT_ID_CONFLICT` としてHARD STOPし、どちらかを上書きしない。
6. branch側にS01があり、main側に同じbaselineのS02・S03等の後続snapshotがある場合は、`previous_snapshot_ref` が解決できる順序で不足snapshotだけを古い順にappend-only移行する。S01が存在することを理由にS02以降を捨てない。
7. main側の後続snapshotが参照する `previous_snapshot_ref` がbranch側・移行対象集合のどちらにも解決できない場合は `SNAPSHOT_HISTORY_GAP` としてHARD STOPし、参照を推測補完しない。
8. branch側にmainより新しいsnapshotがある場合も削除・巻戻ししない。main側にだけ存在するsnapshotを補完した後、両側の履歴が分岐して一意な直列履歴を作れない場合は `SNAPSHOT_HISTORY_DIVERGED` としてHARD STOPする。
9. snapshotに対応する既存のpreservation・persistence receipt・recordsがmain側にあり、対象snapshotの証跡として必要な場合は、それぞれのID・参照関係を同じ方法で照合し、不足分だけを保持して移行する。結果後情報を発走前証跡へ変換しない。
10. 現在の `main` にはなくGit履歴だけに対象予想が存在する場合、対象記録が確認できる最新のmain系commitを移行元として特定し、同じsnapshot ID・参照履歴照合を行う。記録内容・ID・時刻を推測で復元しない。
11. 移行後、日次ブランチから対象baselineの全snapshotを再取得し、`snapshot_id` 集合、`previous_snapshot_ref`、主要内容が移行対象を欠落なく保持していることを確認してから継続する。
12. 移行後の更新・snapshot・回顧は日次ブランチへ保存し、`main` へ直接追記しない。
13. 移行元commit、working_branch、対象baseline、移行したsnapshot ID一覧、既存branchを再利用したかを日次ブランチの引継ぎ情報へ保持する。

導入前のmain記録そのものを削除・書換えしない。移行は今後の書込先を切り替える処理であり、過去の保存場所を遡及的に変更する処理ではない。

### 移行例

移行先branchに `P001-S01` があり、mainに同じ `baseline_forecast_id=P001` の `P001-S01` と後続 `P001-S02` がある場合：

1. S01の内容一致を確認する。
2. S02の `previous_snapshot_ref=P001-S01` が解決できることを確認する。
3. S02だけを既存branchへappend-only移行する。
4. 移行後にS01→S02の参照履歴を読戻す。

「P001がbranchに存在する」だけで移行を終了してはならない。

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
- migrated_snapshot_ids（導入前main記録を移行した場合）
- snapshot_history_status: COMPLETE / GAP / DIVERGED / CONFLICT
- receipt_id / receipt path / receipt_persist_status
- 未完了工程
- HARD STOP / FAIL-SOFT状態

後続実行は、引継ぎ票がある場合はそのbranchとIDを読戻してから継続する。引継ぎ票がない場合は本書の「所属ブランチ探索」に従う。どちらの場合も記憶だけでProduction・買い目・Shadowを再生成しない。

## マージ

回顧・必要記録が完了した後に通常のPRレビューで `main` へ反映する。マージ済みかどうかと、発走前に日次ブランチへ保存済みだったかは別の事実として扱う。後日のマージ時刻を発走前保存時刻として扱わない。
