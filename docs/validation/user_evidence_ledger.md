# 第2検証サイクル — U-02 ユーザー提供情報台帳

- **状態**: 進行中
- **開始日**: 2026-09-17
- **基準Production**: v1.6.1
- **詳細プロトコル**: `records/2026-09-17_user_supplied_evidence_protocol.md`
- **蓄積知見seed**: `records/2026-09-17_user_accumulated_heuristics_seed.md`
- **用途**: 現行サイクル内の実データ保存。恒久ルールの正本ではない

## 運用

予想前にユーザー提供情報を受け取った場合、**予想中は本台帳を更新しない**。ユーザー原文と、Productionへの採否・影響先は発走前チャットで固定する。

結果後の回顧開始時に、発走時刻より前のチャット履歴から事前snapshotを抽出し、その時点で `user_evidence_id`、対象、claim、情報種別、元ソース、事前確認状態、Production利用有無を本台帳へ登録する。その後、同じ回顧作業内で factual validity、predictive_relevance、decision contribution を記録する。

結果後に初めて得た情報はこの台帳の事前情報として遡及登録しない。発走前チャットを参照できない場合は結果から復元せず、そのレースは `PRE_RACE_SNAPSHOT_UNAVAILABLE` としてU-02前向き集計から除外する。

### BACKFILL_SEEDの扱い

2026-09-17に受領した過去蓄積の条件別知見40グループは、レース固有の発走前情報ではないため本台帳の「登録情報件数」へそのまま加えない。

- 原文カタログとして `records/2026-09-17_user_accumulated_heuristics_seed.md` に保存する。
- 該当レースで実際に使う場合は、結果確認前のチャットで採否・影響先が分かるように固定する。
- 回顧時に、その発走前チャットを根拠として原子的なclaimへ分解し、本台帳へ登録する。
- 過去レースへ遡って成功・失敗件数を付けない。

## Evidence ledger

| race / baseline | user_evidence_id | pre_race_chat_ref | 対象 | claim | evidence_type | upstream_source | precheck | production_usage | influence_area | factual_validity | predictive_relevance | contribution | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|

## 集計

| 指標 | 現在値 |
|---|---:|
| BACKFILL_SEED claim group | 40 |
| 前向き登録情報件数 | 0 |
| PRE_RACE_SNAPSHOT_UNAVAILABLE race | 0 |
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
