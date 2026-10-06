# Prediction feature expansion design

## 目的

次期Predictionで検証する新しい予想材料を、Productionへ直接埋め込まず、共通のfeature契約とShadow比較で実装できるようにする。

対象:

1. 直近最大5走の相手レベル
2. 開催期間中のレース傾向
3. 新馬戦専用評価
4. 競馬場・距離・クラス・年齢・性別等の条件別統計

## 共通契約

すべてのderived featureは最低限次を持つ。

- `feature_run_id`
- `feature_version`
- `race_id`
- `horse_id`（馬単位の場合）
- `data_cutoff`
- `source/provenance`
- `sample_count`
- `coverage`
- `confidence`
- `missing_reason`（欠測時）
- 計算に使用した条件・期間

### 禁止事項

- `data_cutoff` より未来に確定した結果を利用しない。
- 結果を見た後に条件・集計期間を追加して当該レースのfeatureを適格化しない。
- 欠測を0や平均値で無言補完しない。
- 同じ事実を複数featureへ二重加点しない。
- 人気・オッズだけをProduction能力順位へ逆流させない。

## 1. 近5走相手レベル

### 目的

着順・クラス名だけでは表現できない「どの程度の相手と、どのような内容で走ったか」を構造化する。

### 対象

各馬の直近最大5走。5走未満なら利用可能な走数だけを使い、欠測を埋めない。

### 入力

各過去走について最低限:

- source_race_id
- race_date
- class
- surface / distance / racecourse
- field_size
- finish_position
- margin
- corner positions
- last3f / last3f rank
- pace / lap context（取得可能な場合）
- 勝ち馬・接戦馬・負かした馬
- 対戦相手の `data_cutoff` 時点までに確定した成績

### feature候補

初期版では単一総合点を正本にせず、成分を分離して保持する。

- `field_strength_context`
- `top_opponent_quality`
- `beaten_horse_quality`
- `close_finish_quality`
- `subsequent_performance_signal`
- `class_transition_context`
- `pace_adjusted_performance_context`
- `evidence_coverage`

### 時点制約

2026-10-01のPredictionを再現する場合、2026-10-02以降の対戦相手結果を使用しない。

`subsequent_performance_signal` は「元レース後」かつ「Prediction data_cutoff以前」に確定した成績だけを使用する。

### 初期運用

Production固定後にShadow featureとして計算し、

- 上位3頭勝ち馬捕捉率
- ◎3着内率
- Brier Score
- 順位改善/悪化
- 無印好走馬の事前捕捉
- 取得率・取得時間

を比較する。

## 2. 開催期間傾向

### 分離する時間軸

```text
長期コース傾向
  ≠ 今開催の傾向
  ≠ 当日の傾向
  ≠ 当該レース固有展開
```

### 集計軸

- meeting_id / meeting_day
- racecourse
- surface
- distance / distance_bucket
- track_condition
- gate
- running style
- corner positions
- last3f rank
- pace class
- inner/outer path（取得可能な場合）
- weather

### 信頼度

`sample_count` と条件一致度を必ず保持する。

単一レースや1〜2例から「内有利」「先行有利」等を強いProduction補正へ変換しない。初期版はShadowのみ。

## 3. 新馬戦専用評価

実走データのない新馬では、通常馬の「馬自身の直接実走を最優先」をそのまま適用できないため、専用feature集合を作る。

### 候補

- sire新馬成績
- sire × surface
- sire × distance bucket
- sire × racecourse
- dam sire関連成績
- trainer新馬成績
- trainer × surface / distance
- trainer × jockey
- jockey新馬成績
- workout
- horse weight / body information
- sex
- breeder等、追加価値を検証可能な属性

### 統計の要件

率だけを保存せず、

- starts
- wins
- top2
- top3
- aggregation period
- condition
- data_cutoff

を同時に保持する。

2戦2勝等の小標本を「得意」と断定しない。ブランド名・リーディング順位だけを自動加点しない。

## 4. 条件別統計

別テーブルを条件ごとに増殖させず、race属性の組み合わせで集計する。

最低限:

- 新馬
- 未勝利
- 1勝
- 2勝
- 3勝
- OPEN
- Listed
- G3 / G2 / G1
- 古馬混合
- 年齢限定
- 牝馬限定
- 特別
- 定量 / 別定 / ハンデ

追加軸:

- racecourse
- surface
- course_type
- distance / distance bucket
- meeting_day
- field_size
- track_condition

## 5. コーナー・通過位置

`core.runner_result` の1〜4角だけに固定せず、コース上存在する通過コールを正規化できる構造を用意する。

最低限:

- race_id
- horse_id
- call_no / corner_no
- position
- position_group
- gap（取得可能な場合）
- source/provenance

コース・距離別の「どこで位置を取る必要があるか」「どの位置から好走しやすいか」の研究に利用するが、集団傾向だけで馬個体の直接実走を上書きしない。

## 6. Production昇格

新規featureは次の順で扱う。

```text
raw / normalized data
 -> feature生成
 -> Shadow前向き固定
 -> 結果比較
 -> 複数レース・複数条件で非劣化確認
 -> 追加価値確認
 -> manual変更proposal
 -> 人間承認
 -> 別PRでProduction昇格
```

複数featureを同時にProductionへ入れて改善要因を識別不能にしない。

## 7. 実装Phase

- Phase 2: 必要raw data・master・result・course情報の取得
- Phase 3: feature生成とShadow出力
- Phase 4: feature根拠・Shadow差分のUI表示
- Phase 8: 前向き/バックテスト評価、data cutoff監査、昇格判定

Phase 2のデータ取得が不足する場合、Phase 3でWeb値を無断補完してProductionへ流さない。取得不能はcoverage/missing reasonとして保持する。
