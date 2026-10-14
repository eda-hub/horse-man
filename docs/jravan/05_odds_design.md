# Odds forecast and retention design

## 3種類のオッズ
1. `observed_odds`: 実際に取得した時点オッズ
2. `predicted_final_odds`: 予想時点でシステムが推定した最終オッズ
3. `actual_final_odds`: 確定後の最終オッズ

この3つを混在させない。

## ルール上の位置付け
オッズ観測・最終オッズ予測は市場分析の入力であり、価格だけを理由に `10_prediction` のProduction基準順位・基準確率・印を変更しない。Prediction固定後の任意sidecarとして扱い、未実行でもPredictionと回顧を完了できる。

## 最終オッズ予測
最終オッズ予測はAIではなくOdds Forecast Engineが担当する。Predictionとは独立して、市場との乖離や価格予測精度を評価するために使用する。固定ルールによる仮想収益検証を行う場合も、Production固定後にだけ接続する。

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
- Production FINAL時点で参照したobserved snapshot（参照した場合）
- predicted final odds
- market validation時snapshot（sidecar実行時）
- actual final odds
- 予測誤差・市場乖離の評価に必要な最小情報

## baseline_forecast_idとの関係
オッズ更新だけではProductionの `baseline_forecast_id` を更新しない。価格更新は市場評価snapshotとして別履歴に残す。実購入意思やユーザー予算は保存必須項目にしない。

## 回顧
馬の予想とオッズ予測を別々に評価する。任意の仮想収益検証を実行した場合だけ、その固定ルールの成績を別系列で評価する。全見送り相当レースの仮想精算を必須にはしない。


## 任意の市場検証sidecar

市場検証は次を満たす。

- Productionの `baseline_forecast_id` を親に持つ。
- Production順位・確率・印を変更できない。
- method_version、data_cutoff、使用odds snapshot、fixed_atを保存する。
- ユーザー購入額・購入有無・実購入払戻を入力にしない。
- 未実行でもPrediction KPIの対象/適格性を変えない。
- 固定ルールによる仮想券を評価する場合、結果後に券種・金額・組み合わせを変更しない。
