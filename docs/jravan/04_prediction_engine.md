# Prediction engine design

## 正本
Prediction Engineは独自ルールを発明しない。競馬判断の正本は `docs/manual/` とし、現行release・Owner・決定権を実装へ写像する。

## Productionパイプライン
```text
JRA data
 -> normalized core/market
 -> feature generation
 -> docs/manual release verification
 -> 00_core execution contract
 -> 10_prediction Production baseline
 -> 20_conditional formal adjustments (該当時)
 -> FINAL readiness check (T-20以降)
 -> Production baseline freeze / baseline_forecast_id
 -> odds observation / final-odds forecast
 -> 30_betting market evaluation / ticket candidates
 -> user BET / SKIP
```

価格情報は市場評価・購入判断には使うが、`10_prediction` の能力順位・基準確率を価格だけで変更しない。

## Shadowパイプライン
```text
fixed Production
 -> copy baseline context
 -> 40_shadow / 51B / Experimental delta
 -> shadow forecast
 -> optional shadow ticket comparison
 -> result comparison
```
Shadowから同一レースのProductionへ書き戻さない。

## Result / Review
結果確定後はProduction、Shadow、実購入を `50_review` の観点で比較し、同じ `baseline_forecast_id` で追跡する。

## Rule実装方式
`docs/manual/` を別YAMLへコピーして新しい正本を作らない。実行可能ロジックはPythonコード/設定として実装してよいが、各実装単位を `module + rule_id` に紐付ける。

各Predictionには次を保存する。
- `manual_release`
- `manual_manifest_hash`
- 使用module hashes
- rule IDs
- engine version
- feature version
- data cutoff
- `data_readiness`
- 必須当日データごとの source timestamp / freshness / missing reason

manifestと必須moduleの `manual_release` が一致しない場合はfail closedする。

## スコアと確率
内部特徴量や説明用scoreは保持してよいが、最終的な意味・優先順位は `10_prediction.md` を正とする。最低限、基礎能力/今回発揮能力、適性、展開、確率、予想確信度の説明を再現できること。

## データ時点
- PRE: 事前取得可能な非価格情報中心
- DAY: 当日馬場・天候・関連レース実測等を追加
- FINAL: 発走20分前以降の馬体重・直前非価格情報・市場情報を揃えた運用snapshot

FINALの必須非価格情報は、当日馬体重と増減、最新馬場・天候、取消/競走除外、騎手・斤量・発走時刻等の変更eventとする。必須項目が欠ける場合は推測で補完せず `data_readiness=DEGRADED` とし、欠損をPredictionへ保存する。

`DEGRADED` の場合でも予想継続は可能だが、欠損が馬体重・馬場等の今回発揮能力に影響しうる情報なら予想確信度の上限を下げ、購入確信度も別途下げる。後からデータが取得できても固定済みFINALを結果に合わせて上書きせず、取得遅延eventとして回顧に残す。

PRE/DAY/FINALは同一ルール体系の時点snapshotであり、チャットが変わっただけ、またはオッズだけが変わっただけでは `baseline_forecast_id` を再発行しない。

## 購入判断との分離
予想側は推奨候補・買い条件・見送り条件を提示する。ユーザーの購入馬、券種、予算は `30_betting` の二段階購入設計に従い、能力評価を変更せず指定条件内で購入設計を最適化する。

## AI非依存
AIが停止していてもProduction予想、Shadow比較、買い目候補、結果精算は動作すること。

## 評価指標
Prediction Performance、Market/Odds Forecast Performance、Bet Performance、Decision Performance、Shadow Validation Performanceを分離する。加えてFINAL data readinessを記録し、`READY` と `DEGRADED` の予想精度・購入成績を分離して比較できるようにする。
