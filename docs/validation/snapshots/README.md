# 発走前不変snapshot

本ディレクトリは、チャット予想で正式固定したProduction / Betting / Shadowの**結果確認前の最小証跡**を保存する。

## 1. 目的

- baseline_forecast_idとProduction内容を後日の回顧で確実に参照できるようにする。
- 既存Productionの無断再生成を防ぐ。
- 初期→最終差分、購入前監査、Shadow完了状態を結果後に捏造・再構成しない。
- チャット履歴の参照可能性だけに正式KPIを依存させない。

## 2. 保存タイミング

分析途中では保存しない。

原則：

**分析・監査完了 → 正式内容FIXED → 本ディレクトリへ保存 → 同内容をチャット送信**

とする。

全体選別は対象全レースを1回のsnapshotへまとめてよい。個別最終・買い目更新は当該レースだけを追記してよい。

## 3. 保存先と正規参照先

日別に、

`YYYY-MM-DD.md`

へappend-onlyで保存する。

正式ルールの参照元は `main` だが、snapshotの書込先と読戻し先は当該作業日の**日次作業ブランチ `prediction/YYYY-MM-DD`** とする。JSTの初回予想時に1本だけ作成し、同日の別レース・別チャットでは再利用する。翌日の回顧・再開も元予想が属する日次ブランチを継続して使用し、日付が変わったことだけを理由に移動しない。

`main` への予想関連の直接コミットは禁止する。日次作業ブランチへ保存できない場合も `main` へフォールバックしない。

既存snapshotを編集して現在値だけにしない。正式更新では新しいsnapshotを追記し、前snapshotを参照する。

保存前には**同じ日次作業ブランチ**の対象日ファイルの最新内容を再取得し、他の実行コンテキストによる追記を保持する。保存後は同じブランチから読戻して `snapshot_id` と主要内容の一致を確認する。書込APIの成功応答だけでは保存完了としない。

`snapshot_id` は `00_core.md` の正本定義に従う。

- 個別レース：`<baseline_forecast_id>-SNN`
- 全体選別：`YYYYMMDD-WHOLE-SNN`

後続snapshotは `previous_snapshot_ref` で直前snapshotを参照する。

## 4. 最低項目

### Production

- snapshot_id
- snapshot_type
- race_id
- baseline_forecast_id
- manual_release
- manual_ref_commit
- contract_effective_date
- task_started_at_jst
- scheduled_post_time_jst と出所
- current_time_jst
- fixed_at_jst
- persist_requested_at_jst
- persist_verified_at_jst
- persist_status
- working_branch
- information_cutoff_jst
- previous_snapshot_ref
- production_status: NEW / REUSED / UPDATED
- 順位・印
- 勝率 / 連対率 / 3着内率
- 予想確信度
- 選別区分・購入優先度（該当時）
- 当日馬体重取得状態
- 市場を能力順位へ使用していないことの状態
- 変更時は変更対象、非価格理由、証拠強度、情報時刻

### Betting

固定買い目がある場合：

- 購入確信度
- 買い / 見送り
- 使用価格と取得時刻
- 固定10,000円案
- 最大馬依存額・率
- 券種成立確率と合理的レンジ下側
- 軸崩れシナリオ
- 監査後判断：維持 / 配分変更 / 総投資削減 / 見送り
- 判断理由

### Shadow

- 適用対象
- 完了 / 未完了 / 非該当
- 完了した場合だけ発走前比較内容
- 未完了理由が発走前に判明していればその理由

## 5. 禁止事項

- 結果後に発走前snapshotを新規作成して適格化する
- 結果・払戻・着順を書く
- 結果後コメントを発走前根拠として追記する
- 古いsnapshotを上書き・削除する
- 未確認を見送り・非該当へ置換する
- Shadow欠落を理由にProduction snapshotを無効化する

## 6. 保存・再送・競合・読戻し

保存処理は次で判定する。

1. 当該 `prediction/YYYY-MM-DD` の対象日ファイルを取得する。
2. 同じ `snapshot_id` がなければ末尾へ追記する。
3. 同じID・同じ内容があれば重複追記せず既存snapshotを再利用する。
4. 同じID・異なる内容があれば `SNAPSHOT_ID_CONFLICT` とし、上書きしない。
5. 保存後に**同じ日次作業ブランチ**から読戻し、IDと主要内容が一致した場合だけ `PERSIST_VERIFIED` とする。
6. 競合等では最新内容を取り直し、他の追記を保持して最大1回だけ再試行する。force更新は禁止する。
7. タイムアウト等で書込成否が不明な場合は `PERSIST_REQUESTED_UNKNOWN` とし、同一IDの読戻しで解決する。

保存状態は、`PERSIST_NOT_ATTEMPTED` / `PERSIST_REQUESTED_UNKNOWN` / `PERSIST_WRITE_FAILED` / `PERSISTED_READBACK_UNVERIFIED` / `PERSIST_READBACK_FAILED` / `PERSIST_VERIFIED` を区別する。FIXED後に保存呼出し自体を行っていない `PERSIST_NOT_ATTEMPTED` を保存失敗やGitHub障害と表現しない。

見送り、正式投資額0円、ProductionのREUSED、短い回答指定でも、正式FIXEDした内容は回答前保存ゲートの対象とする。

発走前に保存・読戻しまで完了できない場合は、予想回答を発走に遅らせない。

チャットには正式内容とともに実際の保存状態を明示する。実際の書込失敗または発走前までに `PERSIST_VERIFIED` へ到達できない場合は `PRE_RACE_SNAPSHOT_PERSIST_FAILED` を使用し、読戻し不一致は `PRE_RACE_SNAPSHOT_READBACK_FAILED`、同一ID衝突は `SNAPSHOT_ID_CONFLICT` を併記してよい。未試行に失敗コードを付けない。

結果後に同じ内容をGitへ追加しても「発走前Git保存済み」にはならない。KPI適格性は `docs/validation/README.md` の要件で独立判定する。

## 7. 役割分離

- `snapshots/`：発走前の不変証跡
- `records/`：結果後の正式回顧・KPI・実購入・エラー分類
- `cycle_02.md`：サイクル集計
- `docs/yosou/`：重賞等の翌年用レース固有知識

本ディレクトリを結果後回顧の保存先として使用しない。


## 8. 別チャット・別モデルへの引継ぎ

引継ぎ時は会話要約だけに依存せず、少なくとも次を短い引継ぎ票として渡す。

- repository: `eda-hub/horse-man`
- manual_ref_commit
- 対象race_id
- baseline_forecast_id
- 最新snapshot_id
- working_branch
- snapshot path
- persist_status
- persist_requested_at_jst / persist_verified_at_jst
- snapshot保存commit SHA
- 未完了工程
- 発生中のHARD STOP / FAIL-SOFT状態

後続実行は引継ぎ票の `working_branch` からsnapshotを再取得してから継続する。取得不能時に基準予想・買い目・Shadowを記憶から再生成しない。正式ルール自体はその時点の `main` のmanualを参照し、既存予想に記録済みの `manual_ref_commit` も保持する。
