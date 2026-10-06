# ChatGPT 次期予想タスクテンプレート（v1.7.0予定）

> 状態: 次期契約用。main の現行releaseが `v1.7.0` へ切り替わるまではProductionへ使用しない。

## 目的

実購入・Bettingを必須工程にせず、発走前のProduction予想を順位・確率・印・根拠とともに固定し、結果後に予想精度を回顧できる状態へする。

## 発走前に必須の出力

- race_id / race_date / scheduled_post_time
- manual_release / manual_ref_commit
- baseline_forecast_id
- Production順位
- 印（◎○▲△。印は順位から導出）
- 少なくとも上位3頭の勝率・連対相当確率・3着内率
- 予想確信度 A/B/C/D
- 少なくとも上位3頭の主要根拠
- 根拠ごとの出所・観測時刻・方向・強度
- 初回予想から順位を変更した場合の変更事実・証拠強度・時刻
- 適用Shadowの対象/非該当/未完了
- snapshot / receipt

## 根拠契約

各根拠は最低限次を持つ。

- factor
- fact
- source_ref
- observed_at_jst
- direction: plus / neutral / minus / uncertain
- strength: strong / medium / weak

単一の弱いコメント、単一オッズ変動、単発の当日レース結果、単なる再考だけで大幅な順位変更を行わない。

## 印の契約

- 1位 ◎
- 2位 ○
- 3位 ▲
- 4位以下 △（順位順）
- 4位以下にも勝利可能性を認める
- 勝利可能性は確率・レンジ・シナリオで表現し、印を上げるために順位を操作しない
- 人気・妙味だけで印を変更しない

## 市場情報

オッズはProduction能力順位へ逆流させない。

任意の市場・仮想収益検証を行う場合も、Production固定後のsidecarとして扱い、予想タスク完了条件には含めない。

## 保存

1. 予想作成前の保存宣言を現行のpersistence契約に従って作成する。
2. 発走前にProduction snapshotとreceiptを保存・読戻しする。
3. `prediction-compliance-v2` gateを作成する。
4. checkerで適格性を確認する。
5. 保存・監査が未完了でも予想内容を結果後に捏造・補完しない。

## 回顧

結果確定後は少なくとも次を評価する。

- ◎勝率 / 連対 / 3着内
- 上位3頭内の勝ち馬捕捉
- 確率精度
- 順位変更の改善 / 悪化
- 無印好走馬の事前捕捉不足
- 根拠不足による誤評価
- 適用Shadowの追加価値

実購入の有無・金額・払戻はPrediction KPIの入力にしない。
