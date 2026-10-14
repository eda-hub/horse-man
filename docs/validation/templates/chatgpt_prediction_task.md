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

## サイクル終了時の追加確認

各日で初回scope・初回FIX/個別完了・選定revision・最終予想/独立推奨・公式結果・回顧を対象ごとに照合する。未選定の初回と選定済み未最終を分け、推奨なし/明示的印のみは個別保存検査が完了していれば正常として扱う。推奨PENDINGの無言置換、取得不足の0埋め、後日の宣言・receipt再生成をしない。

`cycle04_workflow.py --summary`で工程不足と独立KPIを表示する。4日全件の正常一巡は、Git保存/読戻し済みの各日・集計固定参照を与えた`check_cycle04.py --require-complete --completion-manifest ...`が成功した場合だけとする。未実施を残して終えるなら、Owner/審査者・全不足・保護対象・次試験の実際の審査記録をGit保存し、`--closure-review`で別途検査する。自己承認・性能昇格はしない。
