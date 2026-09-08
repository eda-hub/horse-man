# Odds forecast and retention design

## 3種類のオッズ
1. `observed_odds`: 実際に取得した時点オッズ
2. `predicted_final_odds`: 予想時点でシステムが推定した最終オッズ
3. `actual_final_odds`: 確定後の最終オッズ

この3つを混在させない。

## 最終オッズ予測
現行運用を維持し、予想段階で最終オッズを予測して買い目を作る。AIではなくOdds Forecast Engineが担当する。

初期版は、発走までの時間、現在人気、オッズ帯、レース種別等から過去変動率を集計する統計補正で開始する。十分な履歴が溜まった後にLightGBM等を検討する。

## 点予測ではなくレンジ
`center / low / high` を出し、中心EVだけでなく悲観ケースEVも表示できるようにする。

## 保存レベル
- 全レース: actual FINALを保存
- 重賞: T-60 / T-30 / T-15 / T-5 / FINAL
- 予想対象: 必要に応じ5-10分程度または判断時snapshot
- 研究対象: 一時的に高頻度保存可能

当面の重点券種は単勝・複勝・馬連・ワイド。三連系の高頻度全組合せ保存は行わない。

## 永久保存対象
- FINAL予想に使用したobserved snapshot
- predicted final odds
- decision時snapshot
- actual final odds
- 推奨買い目、BET/SKIP判断

## 回顧
馬の予想、オッズ予測、買い目、購入/見送りを別々に評価する。見送り後に推奨馬券が大きく的中した場合は `MISSED_OPPORTUNITY` 等として分析可能にする。
