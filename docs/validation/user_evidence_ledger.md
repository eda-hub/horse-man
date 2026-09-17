# 第2検証サイクル — U-02 ユーザー提供情報台帳

- **状態**: 進行中
- **開始日**: 2026-09-17
- **基準Production**: v1.6.1
- **詳細プロトコル**: `records/2026-09-17_user_supplied_evidence_protocol.md`
- **用途**: 現行サイクル内の実データ保存。恒久ルールの正本ではない

## 運用

予想前にユーザー提供情報を受け取った場合、結果確認前に最低限 `user_evidence_id`、対象、claim、情報種別、元ソース、事前確認状態、Production利用有無を固定する。

結果後の回顧で、同じ `user_evidence_id` に factual validity、predictive relevance、decision contribution を追記する。

結果後に初めて得た情報はこの台帳の事前情報として遡及登録しない。

## Evidence ledger

| race / baseline | user_evidence_id | 対象 | claim | evidence_type | upstream_source | precheck | production_usage | influence_area | factual_validity | predictive_relevance | contribution | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|

## 集計

| 指標 | 現在値 |
|---|---:|
| 登録情報件数 | 0 |
| FACT | 0 |
| OBSERVATION | 0 |
| COMMENT | 0 |
| INTERPRETATION | 0 |
| FORECAST | 0 |
| VERIFIED | 0 |
| PARTIAL | 0 |
| UNVERIFIED | 0 |
| CONFLICT | 0 |
| factual CONFIRMED | 0 |
| factual REFUTED | 0 |
| predictive POSITIVE | 0 |
| predictive NEGATIVE | 0 |
| contribution HELPFUL | 0 |
| contribution HARMFUL | 0 |

率を出す場合は分母を必ず併記し、少数サンプルの高率・低率だけで評価を変えない。

## サイクル終了時

情報種別 × 元ソース / origin group × 情報テーマ × 条件の単位で再現性を確認する。

- 再現性あり: 将来の確認優先度・evidence weight調整候補
- 条件依存: 適用条件を限定して継続検証
- 不明: 判断保留
- 悪化傾向: source取り違え、解釈飛躍、重複、観測タイミングを調査

Productionの正式な重み変更はこの台帳から自動実行せず、`50_review.md` の昇格基準に従って別審査する。
