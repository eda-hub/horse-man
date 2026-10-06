# DuckDB database design

## スキーマ
- `core`: JRA基本データ
- `market`: オッズ・馬体重・馬場等の時系列
- `feature`: 予想用特徴量
- `prediction`: Production/Shadow予想・根拠・任意の市場検証sidecar
- `review`: 回顧・検証サイクル・AI・ルール提案・バックテスト
- `ops`: job、watermark、backup、health、source provenance

## ER概要
```text
core.race 1---N core.runner N---1 core.horse
core.runner 1---0..1 core.runner_result
core.horse 1---N core.pedigree
core.race 1---N market.race_condition_snapshot
core.runner 1---N market.weight_snapshot
core.race 1---N market.odds_snapshot
ops.source_registry 1---N ops.data_provenance
core/market records 1---N ops.data_provenance
core.race 1---N prediction.prediction_run
prediction.prediction_run 1---N prediction.runner_prediction
prediction.prediction_run 1---N prediction.prediction_evidence
prediction.prediction_run 1---N prediction.rule_application
prediction.prediction_run 1---0..N prediction.market_validation_run
feature.feature_run 1---N feature.opponent_strength_snapshot
feature.feature_run 1---N feature.meeting_trend_snapshot
feature.feature_run 1---N feature.condition_stat_snapshot
prediction.prediction_run N---0..1 review.validation_cycle
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

### core.runner_result
`race_id, horse_id, finish_position, finish_time_ms, corner1_position..corner4_position, last3f_ms, last3f_rank, confirmed_at`

### core.pedigree
`horse_id, generation, position, ancestor_registration_no, ancestor_name, relationship`

### market.odds_snapshot
`odds_snapshot_id PK, race_id, captured_at, bet_type, selection_key, odds, odds_min, odds_max, source, snapshot_kind`

### market.weight_snapshot
`weight_snapshot_id PK, race_id, horse_id, horse_no, horse_weight, weight_diff, first_observed_at, captured_at, provider_timestamp nullable, source, acquisition_method, record_hash`

- `first_observed_at`: 当該WHをシステムが最初に確認した時刻。Event受信・catch-upのどちらでも必須。
- `captured_at`: 当該snapshotをDBへ保存した時刻。
- `provider_timestamp`: provider recordに時刻が有効値として存在する場合だけ保存し、空・0等をシステム時刻で捏造しない。
- `acquisition_method`: `EVENT / POLL / CATCH_UP / FALLBACK`。
- `record_hash`: provider recordのrevision識別とidempotent ingestに使用する。同一record再取得で重複行を増やさず、provider側の訂正があれば別revisionとして保存する。

馬体重readinessはsnapshot単体の `captured_at` だけでは決めず、現在の `core.runner.entry_status` に対するcoverage、race/date整合、取得障害情報と組み合わせて判定する。

### market.race_condition_snapshot
`race_id, captured_at, weather_code, turf_condition, dirt_condition`

### market.race_event
取消、騎手変更、発走時刻変更等をeventとして保持する。

### ops.source_registry
`source_id PK, source_name, source_class, origin_group, authority_level, domains_json, is_primary, enabled, notes`

- `source_class`: `OFFICIAL_JRA_VAN / OFFICIAL_JRA / BREEDING_DB / WEATHER_PROVIDER / MEDIA_ORIGINAL / WEB_AGGREGATOR / INTERNAL_DERIVED` 等。
- `origin_group`: 独立した上流情報かを判定するためのグループ。サイト名が違っても同一上流とみなす場合は同じgroupへ寄せる。
- `authority_level`: データ種別ごとの優先順位を実装するための補助属性。単純な全用途共通順位として使わず `docs/jravan/11_source_provenance.md` のdomain別policyと組み合わせる。

### ops.data_provenance
`provenance_id PK, entity_type, entity_key, field_name, source_id FK, source_record_key, source_timestamp nullable, first_observed_at, captured_at, acquisition_method, upstream_origin nullable, is_derived, derived_from_json nullable, record_hash nullable, conflict_status`

客観データ・snapshot・derived featureについて、必要な粒度で「どのsource recordから来たか」を追跡する。

- `entity_type/entity_key`: `race`, `runner`, `horse`, `result`, `weight_snapshot`, `odds_snapshot`, `pedigree`, `workout`, `feature` 等を対象とする。
- `field_name`: field単位でsourceが異なるケースを追跡するために使う。
- `is_derived=true` の場合は `derived_from_json` に元record/provenance IDを保持する。
- 同じ値が複数Webサイトに存在しても、同一 `origin_group` なら独立した複数証拠として数えない。
- provider間で値が不一致の場合は上書き多数決をせず `conflict_status` を残す。

### feature.feature_run
`feature_run_id, race_id, data_cutoff, feature_version, created_at`

### feature.runner_feature
頻出特徴量は列、実験的特徴量は`features_json`へ格納する。血統系統、インブリード、脚質分類、近走集計等のderived featureは、可能な限りraw dataから内部再計算し、`ops.data_provenance` で元データへ遡れること。

### feature.opponent_strength_snapshot
直近最大5走の相手レベルを予想時点で再現する。

`opponent_strength_id PK, feature_run_id, race_id, horse_id, source_race_id, lookback_index, as_of, race_class, field_size, finish_position, margin, pace_context_json, compared_runners_json, subsequent_results_cutoff, strength_features_json, provenance_json`

- `as_of` と `subsequent_results_cutoff` は予想時点を越えてはならない。
- 対戦相手の「その後の成績」は `as_of` までに確定した結果だけを使う。
- 後日再計算する場合も元の `data_cutoff` を固定し、未来情報で過去Predictionを再評価しない。

### feature.meeting_trend_snapshot
開催期間中の傾向を、長期コース傾向・当日傾向・単一レース展開と分離して保持する。

`meeting_trend_id PK, feature_run_id, meeting_id, meeting_day, racecourse, surface, distance_bucket nullable, data_cutoff, sample_count, gate_stats_json, running_style_stats_json, corner_position_stats_json, pace_stats_json, path_stats_json, track_condition, confidence, provenance_json`

小標本の印象をProductionへ直結させず、初期はShadow featureとして利用する。

### feature.condition_stat_snapshot
新馬・未勝利・条件クラス・性別条件等を任意集計できる統計snapshot。

`condition_stat_id PK, feature_run_id, entity_type, entity_id, racecourse nullable, surface nullable, distance_bucket nullable, class nullable, age_condition nullable, sex_condition nullable, race_type nullable, period_start, period_end, data_cutoff, starts, wins, top2, top3, metrics_json, provenance_json`

`entity_type` は `SIRE / DAM_SIRE / TRAINER / JOCKEY / COURSE / OTHER` 等を想定する。新馬戦では種牡馬・厩舎等の統計を使えるが、小標本や市場期待未補正の単純勝率だけで強いProduction加点を行わない。

### prediction.prediction_run
最低限次を持つ。

`prediction_id PK, race_id, baseline_forecast_id, forecast_kind(PRODUCTION/SHADOW), stage(PRE/DAY/FINAL), parent_prediction_id nullable, data_cutoff, manual_release, manual_manifest_hash, manual_module_hashes_json, feature_version, engine_version, validation_cycle_id nullable, created_at, finalized_at, status`

- `baseline_forecast_id` は `docs/manual/00_core.md` 契約に従う。
- ProductionとShadowを `forecast_kind` で明確に分離する。
- Shadowは対応するProductionの `parent_prediction_id` を必須とする。
- PRE/DAY/FINALはデータ時点であり、Ownerモジュールの意味を変更しない。
- FINAL/固定済Productionはimmutable。

### prediction.runner_prediction
`prediction_id, horse_id, mark, baseline_rank, overall_score, ability_score, suitability_score, pace_score, pedigree_score, win_probability, top2_probability, top3_probability, probability_low nullable, probability_high nullable, prediction_confidence`

印は `baseline_rank` から導出する。4位以下にも勝利可能性を認め、確率・レンジ・シナリオは印とは別列で保持する。

### prediction.prediction_evidence
`evidence_id PK, prediction_id, horse_id, factor, fact, source_ref, observed_at, direction, strength, applies_to, provenance_id nullable, notes nullable`

- 少なくともProduction上位馬について、順位・確率を説明できる根拠を保持する。
- `observed_at <= prediction_run.data_cutoff` を必須とする。
- 同一原因を血統・展開・適性等へ二重計上しないよう、`provenance_id` と `applies_to` で追跡する。

### prediction.rule_application
`prediction_id, horse_id nullable, module, rule_id, effect_type, input_snapshot, output_delta, evidence_json`
Production/Shadowどちらで使われたルールかを `prediction_run` と合わせて追跡する。`evidence_json` には可能な範囲で使用したprovenance IDまたはsource record keyを持たせ、第三者の予想印・独自ランキングがProduction evidenceへ混入していないことを監査可能にする。

### prediction.market_validation_run
任意の市場・仮想収益検証sidecar。

`market_validation_id PK, prediction_id, method_version, observed_odds_snapshot_id nullable, predicted_final_odds_snapshot_id nullable, data_cutoff, fixed_at, status, metrics_json, created_at`

- Production固定後にのみ作成する。
- 実購入の有無・予算・財布事情を入力にしない。
- Prediction KPIの完了条件にしない。
- 固定ルールによる仮想検証を行う場合だけ、券種・selection・仮想stake・結果を `metrics_json` または将来の専用子テーブルへ保持する。

### 旧Bettingテーブルの互換

既に存在する `prediction.bet_recommendation / bet_decision / bet_settlement` 相当の履歴を移行で削除しない。次期schemaでは新規Productionの必須書込先にせず、旧manual releaseのread-only履歴として参照する。旧実購入・BET/SKIP・仮想精算を次期Prediction KPIへ自動混入しない。

### review.validation_cycle
`validation_cycle_id, cycle_no, manual_release, started_at, ended_at, status, target_rules_json, planned_sample_count, actual_sample_count`
`docs/manual/50_review.md` の検証サイクルと対応させる。

### review.review_session
Prediction、結果、decision、validation cycleを紐付ける。

## Source provenance
データ取得元・fallback・独立性の契約は `docs/jravan/11_source_provenance.md` を正とする。

- JRA-VAN/JRAで取得可能な客観事実は一次情報を通常経路とする。
- Web aggregatorは障害時fallbackまたはcross-checkとして明示的に扱う。
- 同じJRA由来事実を複数サイトが転載していても独立観測件数を増やさない。
- 民間サイトの予想印・総合指数・AI予想をProduction基準能力のevidenceとして保存しない。

## ルール版の再現性
単一の `rule_version` だけでなく、`manual_release`、manifest hash、利用モジュールごとのhashを保存する。Git commit SHAも取得できる場合は併記する。

## 時点再現
各snapshot、feature、predictionには取得/利用時刻を持たせる。バックテストは `available_at <= data_cutoff` を必須条件とする。馬体重の `available_at` は原則 `first_observed_at` を使用し、provider timestampが欠損していても結果後の情報を事前利用したことにならないようにする。

## Git記録との関係
`docs/yosou/jra_racing/` と `docs/validation/` は現行Git運用の正本/作業領域である。DB導入後の同期方式が正式決定するまで、DB保存を理由にこれらを削除・置換しない。

## データ重要度
A: Production FINAL、baseline ID、順位・確率・根拠、結果、回顧、manual release/module hash、重要snapshot、critical provenance — 原則削除不可
B: Shadow/検証データ — 検証ライフサイクルに従いDB保持方針を別途設定
C: feature、集計 — 再生成可能。ただし再生成に必要なraw provenanceは保持する
D: cache — 削除可
