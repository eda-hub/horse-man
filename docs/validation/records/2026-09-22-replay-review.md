# 2026-09-22 候補7レース Replay回顧

- review_type: `REPLAY_REVIEW`
- reviewed_at_jst: `2026-09-23T18:26:36+09:00`
- target_date: `2026-09-22`
- working_branch: `prediction/2026-09-22`
- manual_release: `v1.6.1`
- scope_count: 7
- scope: `04R / 07R / 08R / 09R / 10R / 11R / 12R`
- formal_kpi_aggregation: `NOT_APPLICABLE`
- live_cycle_success: `NOT_APPLICABLE`
- result_usage_before_review: `PROHIBITED`
- review_status: `REPLAY_REVIEW_COMPLETED`

## KPI境界

本試験は結果確定後のReplayであり、今回作成した最終予想・Shadow・買い目を前向きKPIへ算入しない。
4R・8R・12Rには歴史的な発走前snapshotがあるが、現行checker用receiptがないため今回のmachine KPIは `INELIGIBLE` のままとする。
7R・9R・10R・11RのReplay生成物は結果後生成なので `REPLAY_REFERENCE_ONLY` とする。

## 結果

| R | 1着 | 2着 | 3着 | Production結果 | 回顧判定 |
|---|---|---|---|---|---|
| 4R | 4 | 7 | 3 | ◎4=1着 ○7=2着 ▲3=3着 △6=5着 | 予想PASS / 正式見送り |
| 7R | 7 | 12 | 14 | ◎7=1着 ○1=5着 ▲3=8着 | 中心PASS / 相手・馬券PARTIAL |
| 8R | 7 | 1 | 13 | ◎7=1着 ○5=12着 ▲12=4着 | 中心PASS / 正式見送り |
| 9R | 4 | 14 | 10 | ◎3=10着 ○6=15着 ▲5=14着 | 予想FAIL |
| 10R | 9 | 1 | 2 | ◎5=5着 ○2=3着 ▲6=7着 | 予想FAIL |
| 11R | 14 | 3 | 12 | ◎12=3着 ○5=4着 ▲3=2着 ☆2=10着 | 予想PARTIAL |
| 12R | 13 | 12 | 15 | ◎3=5着 | 予想FAIL / 正式見送り |

## 予想参考集計

- ◎勝利: 3/7（4R・7R・8R）
- ◎3着内: 4/7（4R・7R・8R・11R）
- 勝ち馬がProduction上位3頭内: 3/7（4R・7R・8R）
- 7レース21個の馬券内枠に対し、Production印が捕捉した馬券内枠: 8/21
- これらはReplay回顧の参考値であり、正式サイクルKPIへ算入しない。

## 馬券参考集計

### 買い判定Replay案

- 7R: 10,000円 → 0円
- 9R: 検証用10,000円 → 0円
- 10R: 10,000円 → 0円
- 11R: 10,000円 → 6,750円相当（ワイド3-12、1,500円 × 4.5）
- 合計: 40,000円 → 6,750円相当
- 参考回収率: 16.875%
- `KPI_INELIGIBLE / REPLAY_REFERENCE_ONLY`

### 見送り

- 4R: 正式0円。参考反実仮想10,000円案は馬連4-7とワイド4-7が的中し39,600円相当。
- 8R: 正式0円。参考反実仮想10,000円案は0円。
- 12R: 正式0円。反実仮想買い目は作成していない。
- 反実仮想は正式ROIへ算入しない。

## レース別回顧

### 4R
- error_classification: NONE
- counterfactual_check: SAME
- 予想: PASS。印上位3頭が1〜3着。
- 価格: UNDETERMINED。ReplayでE-08を再構成しない。
- 馬券: NOT_APPLICABLE。正式見送り。
- 再検証: C評価かつ情報不足でも上位構造が明瞭な場合の購入閾値。単発結果で見送り規約は変更しない。

### 7R
- error_classification: J
- counterfactual_check: SAME
- 予想: PARTIAL。◎7の中心評価は正しく、○1・▲3は馬券外。
- 価格: PARTIAL。
- 馬券: FAIL。Replay固定案は0円。
- 再検証: 強い◎がいるレースでの相手候補抽出。今回だけでProduction印を増やすルール変更はしない。

### 8R
- error_classification: NONE
- counterfactual_check: SAME
- 予想: PASS。◎7が勝利。
- 価格: UNDETERMINED。
- 馬券: NOT_APPLICABLE。正式見送り。反実仮想案も0円。
- 保護: 12の-20kgだけで順位を機械変更しなかった点と、C評価の見送り。

### 9R
- error_classification: B / secondary F
- counterfactual_check: UNDETERMINED
- 予想: FAIL。上位3頭が全て大敗。
- 価格: PARTIAL。
- 馬券: FAIL。Replay案0円。
- 実走では◎3が逃げ、○6が直後、▲5も前方で、前寄り評価が共倒れ。pace/位置取りの事前評価を次回前向きで再検証する。
- Replayで抽出した14等の一致は正式改善実績へ数えない。

### 10R
- error_classification: A / secondary E
- counterfactual_check: UNDETERMINED
- 予想: FAIL。勝ち馬9をProduction外とし、○2だけ3着。
- 価格: PARTIAL。
- 馬券: FAIL。Replay案0円。
- 再検証: 芝キャリアが浅い上昇馬・若駒の能力上限評価。Replay U-01/E-09一致は正式KPIへ数えない。

### 11R
- error_classification: G / secondary E
- counterfactual_check: UNDETERMINED
- 予想: PARTIAL。▲3=2着、◎12=3着だが勝ち馬14を外した。
- 価格: PARTIAL。
- 馬券: PARTIAL。自然候補として残したワイド3-12が的中したが、10,000円に対し6,750円相当でトリガミ。
- 保護: ◎-▲の自然候補を事前候補群から落とさない現行監査。
- 再検証: 1800m直接適性・軽ハンデ・成長余地、3角からの早め進出を前向きに評価する。

### 12R
- error_classification: UNDETERMINED
- counterfactual_check: SAME
- 予想: FAIL。◎3=5着。
- 価格: UNDETERMINED。
- 馬券: NOT_APPLICABLE。正式見送り。
- 保護: 相手候補を能力根拠なしで市場価格から追加しなかったこと。
- 再検証: 単独◎で終わる場合の発走前相手候補情報取得。

## 非劣化ガード

### 保護
- 市場価格をProduction順位へ逆流させない。
- Production/Shadowを分離する。
- 見送りと反実仮想を別帳簿にする。
- 非◎縦目は独立正期待値がない限り採用しない。
- 全券種の採否理由を残す。
- 単発結果だけで印数や基本予想を増やさない。

### 再検証
- 強い◎に対する相手候補抽出。
- 前圧が強いレースのpace/位置取り評価。
- 能力上限未確定馬・成長馬の捕捉。
- コース/距離直接適性と軽ハンデが同方向の馬。
- 見送り候補の購入閾値。

### 改善対象
- 現時点で予想モデルの即時改訂は行わない。
- 機械ゲートについては本回顧試験でA〜Lエラー分類と予想/価格/馬券3層採点の必須化を追加した。

## 回顧完了判定

- scope 7/7: COMPLETE
- result source/retrieved_at: COMPLETE
- error classification: COMPLETE
- prediction/price/betting layer assessment: COMPLETE
- counterfactual: COMPLETE
- non-degradation: COMPLETE
- KPI eligibility: 7/7判定済み
- formal KPI aggregation: NOT_APPLICABLE
- cycle aggregation: NOT_APPLICABLE
- review_state: `REPLAY_REVIEW_COMPLETED`


## 強化後の買い目証跡境界

PRレビュー指摘を受け、non-anchor verticalのformal `FIXED` 条件を強化した。

- 許可理由コードは `INDEPENDENT_POSITIVE_EV` のみ。
- `probability_low` と `odds` は、発走前に保存した `betting-evidence-v1` と完全一致が必要。
- そのevidence artifact自身について、同一 `persistence-receipt-v1` レコード内で `PERSIST_VERIFIED` / `RECEIPT_VERIFIED` / `PRE_RACE_ELIGIBLE` と発走前の保存確認時刻を必要とする。
- 本Replayで後から作成した保守確率はこの条件を満たさない。

このため7R・9R・10R・11Rの買い目案は `REPLAY_REFERENCE_ONLY` として保持し、強化後machine gateでは `betting.status=BLOCKED` とする。回顧の参考計算は残すが、正式買い目KPIや前向き有効性の根拠には使用しない。
