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
- race単位のcycle_id / race_date_jst（対象レースの公式開催日）/ 初回scope・候補台帳のsnapshot参照 / 追加選定revision
- initial_snapshot_ref / latest_snapshot_ref（core 0.0.12の内容参照。履歴参照とは別）
- validation_candidates / purchase_candidates / selected_final_scope
- 項目別の取得引継ぎ参照（00_core 0.0.12）と未実施段階
- 未完了工程
- HARD STOP / FAIL-SOFT状態

後続実行は、引継ぎ票がある場合はそのbranchとIDを読戻してから継続する。引継ぎ票がない場合は本書の「所属ブランチ探索」に従う。どちらの場合も記憶だけでProduction・買い目・Shadowを再生成しない。

## マージ

回顧・必要記録が完了した後に通常のPRレビューで `main` へ反映する。マージ済みかどうかと、発走前に日次ブランチへ保存済みだったかは別の事実として扱う。後日のマージ時刻を発走前保存時刻として扱わない。


## 第3サイクルの集計引継ぎ

候補台帳・取得引継ぎは元branchの正式snapshotから回収する。前日予想で作成したbranchも翌日以降の最終・回顧で維持する。branchの日付は初回作業日であり、サイクル適用は `50_review` 0.12.3の開催日・cycle_idで判定する。初回scopeを最終件数へ縮めず、候補降格後も選定履歴を保持する。日別recordとcycle_03の集計revisionは `50_review` 0.14.3に従い、双方を読戻す。PR統合前には最新mainの他日record・集計を照合し、日付×KPI×race_idで再計算する。別日のscope・集計を古い全体内容で消さない。


## 保存拒否と発走時計の是正（2026-10-17、実装後の新規試行に適用）

正式レースでの発走前保存は次の順序を必須とする。未マージのPR・計画を既存本番で有効と自己申告しない。

1. 対象開催日とrace ID、公式scope、公式発走変更chain、日次branchと作業対象pathを確認する。実際のChatGPT/GitHub連携の権限と利用経路を確認する。未確認なら成功と表現しない。
2. 書込み直前・本体読戻し直後・receipt読戻し直後に、現在UTCを取得して `prediction_clock.py` / `verify_prediction_persistence.py --clock-status --date YYYY-MM-DD --clock-race-id RACE_ID` で判定する。第4運用入口は `cycle04_workflow.py --clock-status --date YYYY-MM-DD --clock-race-id RACE_ID`。JST表示、残秒、根拠、状態を返す。実時計が取れない環境では読取専用の計算値を用意できても、実測と混同せず時刻未判定とする。公式scopeと発走変更chainの読取りが終わった**後**に判定時計を新規取得する。取得前の時計を読取り後まで流用しない。時計が5秒超古い、オフセット/秒精度がない、monotonicとの乖離が2秒超、境界不明なら未判定。予定到達は実発走確認済みではない。
3. 正式intentは分析前にGit保存・固定commitから同一bytes読戻しする。FIX独立manifest→本体→receipt→個別検査の順序を守る。自己申告のreadback、ローカル保存、Actions成功だけで正式完了にしない。
4. 固定bytesとSHA-256を保持し、障害を `prediction_persistence_io.py` の拒否分類・操作記録に残す。権限/branch制約、SHA競合、通信/timeout、CI失敗、安全性拒否、理由不明を分ける。拒否された操作を別経路や高権限で迂回しない。通信系のみ、同一原本の遠隔読取り後に最大2回まで許可済みの保存を再試行する。独立した許可済み経路がなければ切替不可と明記する。
5. 実行環境にPythonと承認済みGitHub Contents API認証情報がある場合は、`python3 scripts/prediction_persistence_io.py --date YYYY-MM-DD --race-id RACE_ID --path RELATIVE_PATH --payload-file FIXED_FILE --operation-id UNIQUE_ID --write` を使用できる。同一bytesの既存原本はcommit固定で読戻し、再書込みせず存在確認済みとして扱う。固定原本と異なる内容は `--allow-update` を指定しても上書きせず、新しいrevision/pathで独立保存する。トークンや権限の自動取得・branch自動作成はしない。ChatGPTのGitHub連携利用時は同等の書込→返却commit固定読戻しを連携ツールで実行し、Pythonアダプター成功と取り違えない。
6. 失敗時は固定原本と秘匿済み障害記録を実行環境に保全し、GitHub正式保存は未完了と表示する。branch初期確認段階の拒否（HTTP 403等）でも `--local-incident` へ要求ID・応答分類・API到達状態を保存する。ローカルログ保存失敗も別途表示する。機密文字列を公開リポジトリに記録しない。事故記録の正式保存先は `docs/validation/persistence-incidents/YYYY-MM-DD/` だが、これは当時のreceiptを代替しない。旧データ・過去の証跡を遡及補完しない。

固定原本の保存前には `--race-id`、`--date`、日次branch、対象path、JSON本文のrace ID／開催日／発走予定を照合し、公式scope／発走変更chainから**当該レース**について取得した時刻判定のID・日付・予定時刻とも一致させる。11Rの原本に12Rの時計を使うこと、異なる日付・snapshot IDのパスへ固定することは不可。複数レースの一括intentは最早発走時刻と等しい公式時計を指定する。推奨の独立宣言は `docs/validation/recommendation-intents/YYYY-MM-DD/`、推奨認証は `docs/validation/recommendation-gates/YYYY-MM-DD/`、Prediction固定gateは `docs/validation/recommendation-prediction-gates/YYYY-MM-DD/` に限って新規原本保存を許可する。古い原本や同名gateを異内容上書きせず、新revision・historyによる別pathを使用する。

**ID互換・共有receiptの例外・障害記録復旧**：レースIDは `20261018-TOK-11`（TOK/KYO/NII短縮形式）と `2026-10-18-TOKYO-11`（TOKYO/KYOTO/NIIGATA長形式）を同じ開催日・場・レース番号へ正規化して照合する。第4の公式scopeに別表記で登録されている場合は登録済みの実キーを解決して公式時計を取得し、同一レースの二重登録があれば未判定として停止する。異なるレースを混用してはならない。正式推奨は共有 `docs/validation/persistence-receipts/YYYY-MM-DD.md` へ、先行するR01および他レースのreceiptを**1 byteも変更せず**R02を新規追記する。CLIは共有ファイルの既存bytesに追加レコードを末尾連結した完成版を `--payload-file` に渡し、`--append-receipt --write` を明示する。既存blob SHAと原本bytesの両方を再照合し、整合する場合だけ条件付き更新し、返却commitの読戻しを実施する。R02の `previous_receipt_ref`、artifact、内容SHA、保存/読戻し時刻を一致確認する。R01など過去の固定証跡や推奨本体JSONへの変更は引き続き禁止。 `incident_record()` で生成した障害JSONはrace ID・開催日・branchを保持し、`persistence-incidents/YYYY-MM-DD/` へ復旧後（発走後を含む）に新規保存・読戻し可能。ただし事故記録の保全は発走前保存、receipt認証、KPI適格を代替しない。

時計判定・保存成功・読戻し一致・宣言/FIX順序・個別完了・正式KPIは独立した項目として表示する。現在の時計が発走後というだけで、過去の固定commitによる発走前保存を遅延へ書換えない。実チャット/予約/再開の経路試験は合成CIと別に記録する。安全性拒否の内部理由はログ未取得につき未確定のまま扱う。
