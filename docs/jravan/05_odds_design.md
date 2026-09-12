# Odds forecast and retention design

## 3種類のオッズ
1. `observed_odds`: 実際に取得した時点オッズ
2. `predicted_final_odds`: 予想時点でシステムが推定した最終オッズ
3. `actual_final_odds`: 確定後の最終オッズ

この3つを混在させない。

## ルール上の位置付け
オッズ観測・最終オッズ予測は価格判断の入力であり、価格だけを理由に `10_prediction` のProduction基準順位・基準確率を変更しない。`docs/manual/00_core.md` でProduction/Shadow共通入力として認められた価格観測・価格予測の範囲に従う。

## 最終オッズ予測
現行運用を維持し、予想段階で最終オッズを予測して買い目候補を作る。AIではなくOdds Forecast Engineが担当する。

初期版は、発走までの時間、現在人気、オッズ帯、レース種別等から過去変動率を集計する統計補正で開始する。十分な履歴が溜まった後にMLを検討する。

## 点予測ではなくレンジ
`center / low / high` を出し、中心EVだけでなく悲観ケースEVも表示できるようにする。予測誤差もレース後に独立評価する。

## 保存レベル
- 全レース: actual FINALを保存
- 重賞: T-60 / T-30 / T-15 / T-5 / FINAL
- 予想対象: 必要に応じ5-10分程度または判断時snapshot
- 研究対象: 一時的に高頻度保存可能

高頻度で全券種・全組合せを永久保存しない。保存対象券種は `30_betting` の現行運用と実際の分析用途に合わせて段階拡張する。

## 永久保存対象
- Production FINAL/購入判断に使用したobserved snapshot
- predicted final odds
- decision時snapshot
- actual final odds
- 推奨買い目候補、BET/SKIP判断

## baseline_forecast_idとの関係
オッズ更新だけではProductionの `baseline_forecast_id` を更新しない。価格更新は市場評価・推奨候補・購入判断snapshotとして別履歴に残す。

## 回顧
馬の予想、オッズ予測、買い目構築、購入/見送りを別々に評価する。見送り後の理論損益も計算する。
