# DuckDB database design

## スキーマ
- `core`: JRA基本データ
- `market`: オッズ・馬体重・馬場等の時系列
- `feature`: 予想用特徴量
- `prediction`: 予想・買い目・購入判断・精算
- `review`: 回顧・AI・ルール提案・バックテスト
- `ops`: job、watermark、backup、health

## ER概要

```text
core.race 1---N core.runner N---1 core.horse
core.runner 1---0..1 core.runner_result
core.horse 1---N core.pedigree
core.race 1---N market.race_condition_snapshot
core.runner 1---N market.weight_snapshot
core.race 1---N market.odds_snapshot
core.race 1---N prediction.prediction_run
prediction.prediction_run 1---N prediction.runner_prediction
prediction.prediction_run 1---N prediction.bet_recommendation
prediction.prediction_run 1---1 prediction.bet_decision
prediction.bet_recommendation 1---0..1 prediction.bet_settlement
prediction.prediction_run 1---N review.review_session
review.review_session 1---N review.review_message
review.review_session 1---N review.rule_proposal
review.rule_proposal 1---N review.backtest_run
```

## 主要テーブル
### core.race
`race_id PK, race_date, course_code, meeting_no, meeting_day, race_no, race_name, grade_code, surface, track_code, distance_m, scheduled_post_time, actual_post_time, status, created_at, updated_at`

### core.horse
`horse_id PK, blood_registration_no UNIQUE, horse_name, birth_date, sex_code, color_code, sire_id, dam_id, dam_sire_id, created_at, updated_at`

### core.runner
`race_id PK/FK, horse_id PK/FK, gate_no, horse_no, assigned_weight, jockey_code, jockey_name_snapshot, trainer_code, trainer_name_snapshot, owner_code, owner_name_snapshot, breeder_code, breeder_name_snapshot, entry_status`

コード再利用リスクを考慮し、過去レースの名称はsnapshotも保持する。

### core.runner_result
`race_id, horse_id, finish_position, finish_time_ms, corner1_position..corner4_position, last3f_ms, last3f_rank, confirmed_at`

### core.pedigree
`horse_id, generation, position, ancestor_registration_no, ancestor_name, relationship`
5代血統を検索可能な形で保持する。

### market.odds_snapshot
`race_id, captured_at, bet_type, selection_key, odds, odds_min, odds_max, source, snapshot_kind`

### market.weight_snapshot
`race_id, horse_id, captured_at, horse_weight, weight_diff`

### market.race_condition_snapshot
`race_id, captured_at, weather_code, turf_condition, dirt_condition`

### market.race_event
取消、騎手変更、発走時刻変更等をeventとして保持する。

### feature.feature_run
`feature_run_id, race_id, data_cutoff, feature_version, created_at`

### feature.runner_feature
頻出特徴量は列、実験的特徴量は`features_json`へ格納する。

### prediction.prediction_run
`prediction_id, race_id, stage(PRE/DAY/FINAL), data_cutoff, rule_version, rule_hash, feature_version, engine_version, created_at, finalized_at, status`
FINALはimmutable。

### prediction.runner_prediction
`prediction_id, horse_id, mark, overall_score, ability_score, course_score, pedigree_score, pace_score, trend_score, win_probability, place_probability, confidence`

### prediction.bet_recommendation
推奨買い目。見送りでも削除しない。

### prediction.bet_decision
`BET` / `SKIP_ODDS` / `SKIP_RISK` / `SKIP_USER` / `SKIP_OTHER` と判断理由、判断時オッズsnapshotを保持。

### prediction.bet_settlement
理論精算と実購入精算を区別して集計可能にする。

## 時点再現
各snapshot、feature、predictionには取得/利用時刻を持たせる。バックテストは `available_at <= data_cutoff` を必須条件とする。

## データ重要度
A: FINAL予想、判断、結果、回顧、rules version、重要snapshot — 原則削除不可
B: feature、集計 — 再生成可能
C: cache — 削除可
