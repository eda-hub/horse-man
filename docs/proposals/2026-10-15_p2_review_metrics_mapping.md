# PR88 回顧Owner項目と独立指標の対応表

対象：v1.7.0 第4サイクル。現在のOwnerは `docs/manual/50_review.md`。変更根拠の「強い新事実」を結果から判定しない。

| 既存の保存先 | 現状の不足 | 実装先／判定 |
|---|---|---|
| `races[*].review.error_classification` | 保護・再検証・改善対象を分離しない | 共通validatorで3種を状態・理由・必要入力付き保存 |
| `reviewed_scope` | 回顧下書きを表せない | DRAFTを未完了に置き、COMPLETEのみ完了集合へ |
| `races[*].review` | 改訂の固定履歴がない | originalと独立review revision原本を参照する追記履歴 |
| `prediction_history[*]` | 固定時点の無印成績を未集計 | marks/公式着順のphase別1着・2着・3着内 |
| `additional_review_metrics.initial_to_final` | 選択revision・事前変更根拠と未結合 | 固定gate hash/baseline/cutoff単位の比較と欠測 |
| `recommendation_result` | 推奨不的中の原因分類不足 | settle出力と固定票から複数ラベル・券とレースの分母 |
| `chat_review_package`・`cycle04_completion` | Owner不足の扱いが不一致 | 同一検証・不足理由の伝搬。正常一巡とOwner審査は分離 |

- 歴史的な旧schemaのレビューは読み取り可能なまま、Owner不足と表示する。欠けた分類を自動補完しない。
- `NO_RECOMMENDATION`、`EXPLICIT_MARKS_ONLY`、`PENDING` と取消/無効票を的中率の0標本へ換算しない。
- 独立集計は推奨生成の入力へ戻さず、価格・購入・払戻を要求しない。
- 「無印好走」の合成閾値と「強い新事実」の採用判定は新設しない。正式な合成率が必要ならOwnerの追加決定が必要。
- 試験の合成raceと今後の実JRA結果を混同しない。
