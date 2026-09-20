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

## 3. 保存先

日別に、

`YYYY-MM-DD.md`

へappend-onlyで保存する。

既存snapshotを編集して現在値だけにしない。正式更新では新しいsnapshotを追記し、前snapshotを参照する。

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
- fixed_at_jst
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

## 6. 保存失敗

発走前にGit保存できない場合は、予想回答を発走に遅らせない。

チャットには正式内容とともに `PRE_RACE_SNAPSHOT_PERSIST_FAILED` を明示する。

結果後に同じ内容をGitへ追加しても「発走前Git保存済み」にはならない。KPI適格性は `docs/validation/README.md` の要件で独立判定する。

## 7. 役割分離

- `snapshots/`：発走前の不変証跡
- `records/`：結果後の正式回顧・KPI・実購入・エラー分類
- `cycle_02.md`：サイクル集計
- `docs/yosou/`：重賞等の翌年用レース固有知識

本ディレクトリを結果後回顧の保存先として使用しない。
