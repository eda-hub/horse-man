# Prediction engine design

## パイプライン

```text
JRA data
 -> normalized core/market
 -> feature generation
 -> common rules + race-specific rules
 -> ability / suitability / pace / pedigree / trend scores
 -> total evaluation
 -> marks ◎○▲☆△
 -> probability estimation
 -> odds forecast
 -> bet recommendation
 -> user BET / SKIP
```

## AI非依存
AIが停止していても、特徴量生成、rule評価、marks、確率、買い目候補、結果精算は動作すること。

## Rule形式
ルールは将来YAML/JSONで構造化する。

```yaml
rule_id: STS_014
scope:
  race: セントウルS
type: PLUS
condition:
  previous_distance_m: 1200
weight: 2.0
confidence: medium
evidence:
  sample_size: 68
```

Rule typeは `PLUS / MINUS / EXCLUDE / REQUIRED / REFERENCE` を基本とする。

## スコア
単一指数だけにせず、最低でも `ability / suitability / pace / pedigree / trend` を保持する。総合scoreは説明可能な合成とする。

## Prediction stage
- PRE: 枠、過去走、血統等
- DAY: 馬場、天候、当日情報を追加
- FINAL: 馬体重、取得オッズ、最終オッズ予測を反映

## 記録
FINAL確定時に、各馬評価、適用rule IDs、feature_run_id、odds snapshot、engine version、rule hashを保存する。

## 購入判断との分離
予想と買う/買わないは別。SKIPでも推奨買い目と理論投資額は保持する。

## 評価指標
Prediction Performance、Bet Performance、Decision Performanceを分離する。
