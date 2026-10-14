# 28番：任意市場sidecarの価格状態と試行履歴

価格なしのPrediction・Recommendationは完結する。市場はFINAL固定後に独立artifact・receiptで保存し、予想・推奨の再作成や必須ゲートにしない。唯一の市場Ownerは既存60_market、保存入口は既存 `cycle04_workflow.py --record-market`。

## 新規保存形式

新規の分析は `schema_version: market-analysis-v2`。race_id/race_date_jst/data_cutoff/marketを持つ。marketのstatus/decision/reason/odds/expected_value/attempted_at_jst/acquired_at_jst/source_refは既存契約を再利用する。

| 取得状態 | 判断・値 | 試行履歴 |
|---|---|---|
| NOT_ATTEMPTED | NOT_EVALUATED、価格/期待値null | attempts空、試行/取得/停止時刻null、source_ref null |
| FAILED | NOT_EVALUATED、価格/期待値null | 1件以上の失敗。試行ごとの取得先・理由・開始/終了を保持、取得時刻null |
| DEADLINE_STOPPED | NOT_EVALUATED、価格/期待値null | 試行前の期限到達は履歴空、試行済みは失敗を保存。期限≦停止≦cutoff |
| ACQUIRED | NOT_EVALUATED / POSITIVE_EV / INSUFFICIENT_EV | 最後の試行だけ成功、観測≦取得≦cutoff。取得先/取得時刻は最終試行と一致 |

取得済み未評価の期待値はnullを許容し、未算定を0や不足へ変換しない。評価済みには有限の期待値を要求し、POSITIVE_EVは正数、INSUFFICIENT_EVは0以下。市場の取得適格性は価格・出所・保存の独立結果であり、正の期待値や性能を自動認証しない。

`market.acquisition` は `schema_version: market-acquisition-v1`、attempts、deadline_at_jst、stopped_at_jstを持つ。各attemptには1開始の連番attempt_no、source_ref、started_at_jst、finished_at_jst、result（FAILED/ACQUIRED）、reason、observed_at_jstを保存。FAILEDの観測時刻はnull。連番重複・欠番・未来/逆行/重複時間・成功後の追加試行・期限超過を拒否。HTTP原応答hash/再試行/代替取得の実装と締切超過finishの保全は [29番の仕様](market-acquisition.md)。

旧market-analysis-v1は読取互換を保持し、履歴なしを未確認として表示。古い履歴を捏造しない。新v2から履歴を省略したもの、未知schemaは拒否。履歴があるv1にも同じ履歴整合を適用。

## 操作

1. 任意市場の依頼がある場合に、取得先・各試行・観測/取得時刻・締切と理由を独立v2分析へ保存する。
2. 既存artifact保存/receipt読戻しを完了する。分析のcutoffと保存/receipt時刻は発走前、FINAL scopeへ対応する。
3. 日次branchで `python scripts/cycle04_workflow.py --root ROOT --date YYYY-MM-DD --record-market ENTRY_JSON` を実行する。ENTRY_JSONはrace_idと既存market_ref形式。
4. `python scripts/market_sidecar.py ANALYSIS_JSON` で日本語状態・理由・出所/時刻・全試行を確認する。読取専用で価格取得や書込は行わない。

保存writerと日次readerは成功/保留双方の独立artifact hash・receipt・v2履歴を検査する。検査失敗時に既存日次台帳を書き換えない。市場の再保存はレビュー前だけ許可する。予想/推奨の原bytesとKPIを保持する。

## 受入と残件

新規18回帰：4取得状態/3判断、失敗後成功の履歴保全、価格欠測と不足の分離、未試行・取得/失敗矛盾、schema/必須履歴、source/理由、未来/逆行/観測・連番/時間重複/成功後試行、上位source/時刻、締切、非有限/bool/期待値矛盾、旧履歴未確認、日本語表示、価格なし完結、4状態保存の予想/推奨不変、不正入力時台帳不変、保留市場の原本hash不一致を検査。既存第4回帰56件成功。合成試験を実価格取得や2開催実測へ転用しない。

R-20261011-01の過去原因不明、HTTP/JV-Linkの取得経路・代替・応答hash/再試行は29番で実装受入済み。Windows実サービス接続と2開催実測はOPENのまま引き継ぐ。今回の状態分類完了を価格取得課題全体の完了としない。旧予想/receipt/KPI/研究data、正式Owner、既存workflowを変更しない。
