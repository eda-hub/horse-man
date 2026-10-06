# Ability uncertainty / latent-upside review design

## 目的

結果後の回顧で、無印馬の好走をすべて「見落とし」と扱うのではなく、発走前に保存した情報から次を区別できるようにする。

1. 事前情報から拾う余地があったのに評価へ十分反映できなかった馬
2. 中心能力評価は低いが、推定不確実性が大きく上振れ余地を持っていた馬
3. 事前時点では合理的に除外でき、結果だけを見て救済すべきでない馬
4. 結果後にしか説明できない馬

競馬判断の正本は `docs/manual/` とし、本書は将来のローカル予想・回顧システムにおける検討事項とする。現行Productionの順位・印・確率を変更するルールではない。

## 問題設定

現行manualには `10_prediction.md` の「未知と弱点を区別する」原則があり、E-09では馬個体適性を比較用に追う。一方、現状は主に上位馬・価格候補・展開キー馬を詳しく見るため、最終的に無印となった馬について、

- どこまで能力が分かっていたか
- どの部分が本当に未知だったか
- 低評価だったのか、証拠不足だったのか
- 上振れを示す事前証拠があったか

を全馬共通形式で残す仕組みが弱い。

結果後に「あの材料があったから拾えた」と言い始めると後知恵になるため、能力不確実性は**発走前に固定**する必要がある。

## 基本原則 — 中心能力と不確実性を分ける

各馬について、少なくとも概念上は次を分ける。

- `ability_center`: 現時点で最も妥当な中心能力評価
- `ability_uncertainty`: その中心評価自体の不確実性
- `upside_evidence`: 中心評価より上へ振れることを支持する事前証拠
- `downside_evidence`: 能力発揮を抑える事前証拠

重要なのは、

**不確実性が高い = 強い馬 / 上位順位に置く馬**

とはしないことである。

低い中心能力 + 高い不確実性だけでは上位評価の根拠にならない。上振れを示す独立した事前証拠を確認し、中心確率・確率レンジ・シナリオへどこまで反映するかを別途判断する。市場検証を行う場合もProduction固定後の任意sidecarとする。

## 不確実性の種類

### 1. Epistemic uncertainty — 情報不足による能力未知

例：

- キャリアが浅い
- 同等クラスとの比較材料が少ない
- 初距離 / 初コース / 初馬場
- 大幅な条件替わり
- 昇級直後で能力上限が未観測
- 近走で急成長して過去平均が現在能力を表しにくい

これは「弱い」とは別に扱う。

### 2. Scenario uncertainty — 今回の展開での発揮幅

例：

- 位置取りを取れるか不明
- ペース形状が複数あり、適性差が大きい
- 馬群 / 砂被り / コーナリング等で結果が分岐する

E-04 / E-09 / コース要求×馬個体適性の検討事項と接続する。

### 3. Observed volatility — 既に観測された不安定さ

好走と凡走を繰り返している等、十分な観測がある不安定さは「未知」と混同しない。

原因が既知の不安定さはリスクであり、情報不足とは別に保存する。

## 発走前の全馬一次スキャン

詳細分析の情報コストを増やしすぎないため、E-09の詳細対象とは別に、全出走馬へ最小限の一次スキャンを行うことを検討する。

最低限の候補field：

- `baseline_rank`
- `win_probability`
- `place_probability`
- `top3_probability`
- `evidence_coverage`: LOW / MEDIUM / HIGH
- `ability_uncertainty`: LOW / MEDIUM / HIGH
- `upside_evidence`: NONE / WEAK / MODERATE / STRONG
- `scenario_sensitivity`: LOW / MEDIUM / HIGH
- `unmarked_reason`
- `latent_upside_candidate`: true / false

`unmarked_reason` は例えば次を区別する。

- `LOW_BASE_ABILITY`: 比較材料が十分あり中心能力が低い
- `NEGATIVE_FIT`: 今回条件への適性・展開が明確に不利
- `INSUFFICIENT_UPSIDE_EVIDENCE`: 未知はあるが上振れ根拠が不足
- `HIGH_UNCERTAINTY_LOW_CENTER`: 中心能力は低いが推定幅が大きい
- `LOW_RANK_OUTSIDE_MARKS`: 能力評価は残ったがProduction順位上、表示印の対象外

これを発走前に保存することで、結果後の説明を結果に合わせて作り直すことを防ぐ。

## latent-upside candidate の考え方

印とは別の診断タグとして扱う。

候補化は「未知だから」ではなく、原則として次が重なる場合に検討する。

1. 能力推定の不確実性が高い
2. 上振れ方向を支持する事前証拠がある
3. その証拠が同じ原因の言い換えだけではない

上振れ証拠の例：

- 直近で時計・ラップ・位置取り・末脚が複数方向に改善
- 上級条件でも通用しうるレース内容
- 類似条件への明確な適性証拠
- E-09で今回条件が能力再現を助ける
- 血統仮説と実走改善が一致
- 複数シナリオのうち少なくとも1つで上位争いまで到達する合理的経路がある

単なる人気薄、キャリア浅、初条件だけでは候補化しない。

## 数理実装を行う場合

将来的なモデルでは馬の能力を1点だけでなく分布として扱うことを検討する。

概念例：

```text
horse performance ~ distribution(center, uncertainty)
```

中心値だけで順位付けする一方、分布を使ったシミュレーションから、

- P(win)
- P(top2)
- P(top3)
- 上位到達確率の幅

を推定する。

実装候補は、

- Bayesian / hierarchical modelによるposterior uncertainty
- bootstrap / ensembleによるモデル間分散
- 条件別モデルのdisagreement
- OOD / 類似サンプル不足の検知

等を比較する。

単純な「過去着順の分散が大きい」だけで能力不確実性とはしない。

## 印との関係

印は引き続き**中心期待値と主要シナリオ**を表す。

したがって、低い中心能力だが上振れ余地のある馬を、未知度だけで△や☆へ自動昇格させない。

概念上は、

```text
Production marks = central expectation
latent-upside tag = uncertainty / tail diagnostic
```

と役割を分離する。

これにより、印を増やして予想を曖昧にすることなく、結果後に「事前に上振れ余地を認識していたか」を確認できる。

## Production順位・確率との関係

latent-upside候補は印や順位を自動変更するタグではない。

発走前に、

- 中心能力
- 勝率・連対相当確率・3着内率
- 確率レンジ
- ability uncertainty
- scenario sensitivity
- 上振れ方向の独立根拠

を分離して保持する。

例えばProduction4位以下でも合理的な勝利シナリオを持つ馬は、その勝利可能性を確率レンジやscenarioとして保存し、勝利可能性だけを理由に▲以内へ順位を操作しない。

初期Shadow検証では、

- Production中心順位
- uncertainty-aware Shadow順位/確率
- latent-upside candidate集合

を同じdata cutoffで固定し、結果後に比較する。

評価は「拾えば当たっていた」ではなく、長期的に、

- 上位3頭勝ち馬捕捉率
- 無印2着以内 / 3着馬の事前捕捉率
- Brier Score等の確率精度
- 候補率
- false positive率
- Production順位からの変更件数
- 変更による改善 / 悪化

を確認する。

### 任意market validationとの関係

価格・仮想収益まで研究する場合は、Productionとuncertainty Shadowを発走前固定した後の任意sidecarで行う。市場価格をlatent-upside候補の事前採否へ逆流させず、sidecar未実行でも本検証のPrediction評価を完了できるようにする。

## 回顧時の無印好走馬分類

無印馬が2着以内、または重要な3着へ好走した場合、結果だけで一律に能力評価ミスとしない。

発走前snapshotから次へ分類することを検討する。

### `SIGNAL_MISSED`

事前に複数の上振れ証拠があり、中心能力・確率へ十分反映できていなかった。

→ 能力評価 / 適用漏れの改善候補。

### `UNCERTAINTY_UNDERMODELED`

中心評価が低いこと自体は合理的だったが、情報不足・条件替わり等による推定幅を狭く扱いすぎていた。

→ 能力中心値より、不確実性推定・tail probabilityの改善候補。

### `RATIONAL_EXCLUSION`

事前情報は十分で中心能力が低く、上振れ証拠も不足していた。結果は事前確率の低い事象として説明可能。

→ 結果だけで改善候補にしない。

### `POST_HOC_ONLY`

好走理由が結果後の情報でしか成立しない。

→ 予想改善根拠にはしない。

## 検証KPI候補

本検討をShadowで開始する場合、少なくとも次を計測する。

- 無印2着以内馬のうち `latent_upside_candidate` が事前捕捉した割合
- 無印3着馬の事前捕捉率
- latent-upside候補全体の2着内率 / 3着内率
- latent-upside候補率 / 1レース平均候補数
- 候補のfalse positive率
- uncertainty-aware Shadowによる上位3頭捕捉率差
- uncertainty-aware ShadowによるBrier Score差
- Production順位変更の改善 / 悪化率
- `SIGNAL_MISSED / UNCERTAINTY_UNDERMODELED / RATIONAL_EXCLUSION / POST_HOC_ONLY` の構成比
- 不確実性LOW/MEDIUM/HIGH別の実際の予測誤差

特に、捕捉率だけを改善目標にしない。全馬を候補化すれば捕捉率は上がるため、**候補数・誤検出率・順位精度・確率精度を同時に評価**する。

## 現行manualへの反映方針

現時点では `docs/manual/` のProductionルールへ直接追加しない。

理由：

- 現行 `10_prediction.md` には「未知 ≠ 弱点」が既にある
- 現行 `50_review.md` には合理的に切った馬の好走を結果だけで改善候補にしないガードがある
- 新たに必要なのは中心能力を変えるルールより、発走前の不確実性snapshotと回顧分類である

十分な前向きサンプルで追加価値が確認できた場合に、既存の馬個体適性評価 / reviewのどこへ統合するかを別途審査する。市場検証へ接続する場合もPredictionとは別責務とする。
