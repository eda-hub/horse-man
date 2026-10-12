# 個別Prediction・Recommendationの完了確認（26番）

`scripts/task_completion.py`は実際の保存済みファイルを読み、既存validatorへ接続して、対象ごとの不足を日本語で表示する。予想・推奨本体、receipt、FIX時の内容との一致、個別完了確認、実行ゲート、適用Shadow、全体監査を独立した項目にする。結果は読取専用であり、元ファイル・過去証跡・KPI適格性を変更しない。

| 項目 | 照合する証跡・判定 |
|---|---|
| 本体 | 指定したsnapshotの存在・読取・既存形式確認。未保存を未試行/書込失敗と推測しない |
| receipt | 同じartifactへの参照、実際の保存/読戻し時刻、発走前境界。推奨では内容hashも照合 |
| FIX時の内容との一致 | FIX時に別途保持したhashと現在の対象bytes。旧Markdownは該当section、JSONはファイル全体 |
| 個別完了確認 | 予想は同じsnapshotの事前宣言・scope・receipt・FIX hashを既存検証で確認。推奨はFIX hashと既存の独立gate検証 |
| 実行ゲート | 対象レース・artifactに対応する既存gateをvalidatorで再確認。複数レース予想は全対象gateを確認 |
| 適用Shadow | Predictionのgateに明示したscopeと実際の証跡。空scope/明示対象外以外を自動的に対象外としない |
| 全体監査 | 個別完了の代用ではない。APIで別項目として保持し、全体監査だけの成功で個別成功へ変換しない |

未実施の確認は`null`、実際の失敗/不足は`false`、成功は`true`、明示した対象外は`NOT_APPLICABLE`。通常表示は日本語、内部コード・原文diagnostic・参照先は明示した`--status-json`に保持する。確認実行時刻は現在のJSTで記録し、過去の確認時刻へ遡らせない。

## 予想の確認

```bash
python scripts/verify_prediction_persistence.py --root . --date YYYY-MM-DD \
  --snapshot-id SNAPSHOT_ID --completion-status --intent-id INTENT_ID \
  --fixed-content-sha256 FIX時に保持したHASH
```

事前宣言IDまたはFIX時hashがないとき、個別完了は未実施のまま。現在のファイルから新しく計算したhashを過去のFIX時証拠と扱わない。従来の`--task-complete`は本体保存の個別確認範囲と終了値を維持し、その成功だけで実行ゲート/Shadowを含む全工程完了とは表示しない。全必須工程を確認する場合は`--completion-status`を使う。

Shadowが適用されていて未実施/保留/証跡不足なら、その項目だけを不足にする。本体保存やPredictionの既存KPIを失敗へ書き換えない。完了したがKPI不適格のShadowも実際の証跡を照合し、適格へ昇格しない。

## 推奨の確認

```bash
python scripts/recommendation.py --root . --verify GATE_PATH \
  --completion-status --completion-artifact-path RECOMMENDATION_PATH \
  --fixed-content-sha256 FIX時に保持したHASH
```

本体pathを独立に指定し、gateが欠落しても本体とreceiptの確認結果を保持する。FIX時hashなしの通常`--verify`成功は、個別全完了と表示しない。現在の推奨契約には推奨固有Shadowはないため、この項目を契約上の対象外とする。Prediction側のShadow不足を推奨KPIへ転用せず、推奨の不足もPrediction側へ転用しない。元Predictionの正式性は従来の固定Production gate検証に従う。

新モードは個別対象の必須工程が完了したとき終了0、不足があれば終了1。`--status-json`は新モードでだけ使用できる。既存`--audit`は監査ログの機能と判定を維持する。全体監査の未実施や他対象の不足を、独立した個別対象の結果へ混ぜない。

## 検証・境界

`scripts/test_task_completion.py`は実際のfixtureファイルと既存validatorを使い、監査だけ成功/本体欠落/receipt欠落/内容不一致/ゲート欠落/適用Shadow未実施・証跡欠落・成功/Shadow scope欠落/推奨独立性/両CLIを検査する。合成fixtureのACTIVE契約は実リポジトリの切替ではない。v1.6.1・Draft/PENDING・既存予想・receipt・manualを保持し、欠落した過去証跡を生成しない。
