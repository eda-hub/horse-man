# v1.7.0 初回・最終・回顧の標準実行テンプレート

## 開始

eda-hub/horse-manのmainからmanual READMEを取得し、同一参照commitで必要Owner・v1.7.0を確認する。`run_release_readiness.py --require-main`でmain有効化を確認する。対象開催日と実発走予定・依頼scope・既存基準を確認し、prediction/YYYY-MM-DDを再利用する。

## 初回

公式番組と依頼scopeから `cycle04-official-scope-v1` の全対象を登録する。予定144Rから勝手に補完しない。開始前に予想/推奨scopeの宣言をGit保存・読戻ししてから予想を作る。全対象馬の事実→評価→全頭確率→順位→印・根拠・確信度を固定し、初回全scopeと選定/未取得を残す。

## 最終

選定候補の既存基準・静的入力を再利用し、当日馬体重/取消/馬場等を取得試行する。候補追加・用途変更は発走前のselection-history revisionと独立receiptを保存する。重賞属性だけで対象を増やさない。

1. 宣言の読戻し後、FIX bytesと独立manifestを `seal_prediction.py` で作成する。
2. FIX manifestをGit保存・読戻してから同じbytesの本体を独立JSONへ保存する。
3. 本体とreceiptをGit保存・読戻しし、同じartifact/time/hashで個別確認する。
4. Production固定後、価格なしで `recommendation.py --prepare/--generate/--seal` の独立推奨を保存する。推奨なし/印のみ/未完了を別状態にし、購入確認や予算を入力にしない。
5. 本体、receipt、FIX hash、個別確認、gate、該当Shadowを独立検査する。全体audit成功を個別完了としない。
6. `cycle04_workflow.py --record-prediction`で日別台帳へ接続し、検査した台帳を同日branchへGit保存・読戻す。

保存/取得障害でも予想回答を発走時刻まで無限に待たせず、未完了範囲と原因を日本語で示す。結果後に宣言・買い目・時刻を生成して適格にしない。

## 回顧

公式結果を同じrace/dateと取得時刻で保存し、 `cycle04_workflow.py --review` に誤差分類・良好部分保護・次の検証を与える。初回scope全件を対象に未最終/推奨なしも回顧し、 `--summary` でPrediction/推奨/Shadow/任意市場を独立集計する。回顧完了は日別→サイクル集計のGit読戻しまで。

実購入・払戻なしでPredictionと推奨的中を評価する。0適格・未測定を0%にせず、未来値・旧☆・旧Betting・研究Replayを新KPIへ混ぜない。

## 利用者への回答

順位/印/確率/根拠/確信度、推奨または理由付き推奨なし、対象ごとの本体/個別完了/不足を日本語で示す。内部IDや工程コードをそのまま列挙しない。

## Shadow初回・最終の適用状態の固定

初回と最終のPrediction gateを別phaseの固定履歴として登録する。日別writer/preview用entryには各phaseの `shadow_applicability`（`status`, `reason`, `item_ids`）を必ず入れる。項目が存在する場合は `APPLICABLE` としてgateの全項目IDを一致させる。対象条件を実際に確認して非該当なら `NOT_APPLICABLE`、未確認なら `UNKNOWN`（保留）とし、単なる空の `shadow_items` だけでは非該当としない。

初回に存在した項目を最終gateから外すときは、`previous_item_dispositions` に消えたIDごとの `status` と具体的な `reason` を全件記録する。初回の原本とreceipt、固定gateのSHAと当時の比較状態は変更・削除しない。最終のShadow対象外/不足は日別最新Shadow KPIだけに反映し、独立Productionと価格不要推奨の完了判定へ流用しない。プレビューはwriterと同じ検証を通す。

回顧では `shadow_history` と `shadow_history_gaps` をphase別に読み、同一gate・baseline・cutoff・項目IDの固定比較キーで重複を除外する。初回比較と最終比較を混ぜず、未実施や証跡不明は保留/不足とする。
