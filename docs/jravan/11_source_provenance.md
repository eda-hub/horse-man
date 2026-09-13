# Source provenance and source-bias policy

## 目的

予想に使うデータの**正しさ・時点整合・出典系統**を管理し、特定サイトへの過度な依存や、同じ上流データを転載する複数サイトを「独立した複数根拠」と誤認することを防ぐ。

この文書は競馬判断ルールを変更しない。予想の意味・優先順位は `docs/manual/` を正とし、本書はデータ取得・出典・provenanceのシステム契約を定義する。

## 基本原則

1. **事実データは一次情報を優先する。** JRA-VAN/JV-LinkまたはJRA公式で取得可能な項目を、民間Webサイトの転載値で通常運用しない。
2. **サイト数ではなく上流の独立性を数える。** 2〜3サイトで同じ値が表示されても、上流が同一JRAデータの転載である可能性がある場合は独立証拠として加算しない。
3. **客観データと編集情報を分離する。** 馬柱、着順、時計、通過順、上がり、斤量、馬体重、オッズ等の客観値と、記者印、指数、寸評、調教評価、予想コメントを同じ種類の証拠として扱わない。
4. **第三者の予想・印・独自指数をProduction能力評価へ逆輸入しない。** 使用する場合は研究・比較用Shadowまたは参考表示に限定し、`10_prediction` の基礎能力順位の根拠にはしない。
5. **不足時のfallbackは明示する。** 一次情報が取れずWeb補助ソースを使用した場合、`source_class`, `origin_group`, `acquisition_method`, `observed_at` を残す。
6. **不一致は多数決で解決しない。** authority、timestamp、対象race/horseの一致、revisionを確認し、一次情報を優先する。

## 情報種別ごとの優先順位

| データ種別 | Primary | Secondary / cross-check | Web fallbackの扱い |
|---|---|---|---|
| 出走馬、枠、馬番、斤量、騎手、取消・変更 | JRA-VAN / JRA | 相互照合 | netkeiba等は障害時の確認のみ |
| 当日馬体重・増減 | JV-Link速報WH (`0B11`) | JRA公式 | 動的GUIは緊急fallback。静的HTML空欄を未発表判定に使わない |
| 当日馬場・天候・発走時刻 | JRA-VAN / JRA | 公式発表の相互照合 | 民間サイトは補助 |
| 速報・確定オッズ | JRA-VAN / JRA | 相互照合 | netkeiba等は緊急fallback。オッズは能力順位に使わない |
| 過去成績、時計、着差、通過順、上がり | JRA-VAN / JRA | JBIS等でspot check | netkeiba/競馬ラボ等は取得補助。第三者指数は別扱い |
| 血統・5代系統 | JRA-VAN BLDN | JBIS等の血統DB | netkeibaは補助。系統分類・インブリード判定は内部derived featureとして再計算 |
| 調教時計 | JRA-VAN SLOP/WOOD | 公式/信頼できる原データ | メディアの「A/B/C」「絶好」等の主観評価は別フィールド |
| 厩舎・騎手・馬主・生産者 | JRA-VAN master / JRA | JBIS等 | 民間サイトは表記確認のみ |
| 天気予報 | 公的/専門気象provider | 別の気象provider | 競馬サイトの天気表示を一次予報にしない |
| 陣営コメント・取材情報 | 発言元が明確な媒体 | 複数媒体で原文確認 | コメントは発言内容以上へ拡大解釈しない |

## Source class / origin group

最低限、sourceを次の概念で分類する。

### source_class
- `OFFICIAL_JRA_VAN`: JRA-VAN/JV-Link
- `OFFICIAL_JRA`: JRA公式Web/公式発表
- `BREEDING_DB`: JBIS等の血統・生産系DB
- `WEATHER_PROVIDER`: 気象provider
- `MEDIA_ORIGINAL`: 独自取材・コメント・記事
- `WEB_AGGREGATOR`: netkeiba、競馬ラボ等の馬柱・集約表示
- `INTERNAL_DERIVED`: 当システムが一次データから計算したfeature

### origin_group
`origin_group` は「独立した上流か」を判定するためのグループであり、サイト名と同義ではない。

例：
- JRA公式とJRA-VANは別取得経路として照合できるが、同じ競走事実を扱う場合は“2票”の多数決には使わない。
- netkeibaと競馬ラボに同一の着順・時計があるだけでは独立観測2件と数えない。
- 独自取材コメントは、原発言者・取材媒体が異なる場合だけ独立情報として扱える。

上流が不明なWebデータは `origin_group=UNKNOWN_AGGREGATED` とし、独立性を仮定しない。

## Chat予想時の暫定運用

ローカルJRA-VANシステムが未稼働、またはチャットから直接予想する場合も同じ原則を適用する。

1. まずJRA公式/JRA一次情報を探す。
2. JRA公式で動的値を取得できない場合、ブラウザGUI取得を含むWeb fallbackを使用してよい。
3. Web fallbackで得た馬体重・オッズ・馬柱は `WEB_FALLBACK` とみなし、可能な限り別系統の一次/準一次情報でspot checkする。
4. netkeibaの馬柱、競馬ラボの馬柱、Umanity等を同時に参照しても、それだけで根拠の独立性が増したとは扱わない。
5. 予想本文では第三者の「指数順位」「印」「AI予想」を自分の能力評価根拠として引用しない。引用する場合は市場・世評比較と明示する。
6. 発走前FINALでは、使用したcritical sourceの一覧とreadinessを保存可能な形にする。

## Derived data

血統系統、インブリード、脚質分類、近走上昇度、コース適性、展開feature等は、可能な限り一次raw dataから内部計算する。

- `sire line`, `dam-sire line`, `Northern Dancer xN` 等は血統rawから再計算する。
- `last3f_rank`, `pace_position_band`, `course_repeatability` 等もraw resultから再計算可能にする。
- Webサイト独自の血統分類・脚質ラベルをそのまま内部正本にしない。

Derived featureには `derived_from` と使用したsource recordを追跡できるようにする。

## 不一致処理

同じfieldに複数sourceで不一致がある場合は次の順で処理する。

1. race/horse/date/record keyの取り違えがないか確認。
2. source timestamp / captured_at / provider revisionを確認。
3. JRA-VAN/JRAの最新公式値を優先。
4. 公式同士で解消しない場合は値を推測せずconflictとして保存。
5. conflictがFINAL必須項目なら `data_readiness=DEGRADED` とする。

## 予想への利用禁止・制限

Production基準能力を作る際、次を直接の加点・減点材料にしない。

- netkeiba等の予想印・AI印
- 民間サイトの総合ランキング
- 出所不明の独自指数
- 人気順位そのもの
- 「複数サイトが推している」という集団評価

これらは市場期待・世評・Shadow研究として別保存することはできるが、能力評価へ逆流させない。

## 監査指標

開催日・検証サイクルごとに最低限次を確認する。

- critical fieldのPrimary source coverage率
- Web fallback利用率
- `UNKNOWN_AGGREGATED` 利用率
- source conflict件数
- fallbackによって印・確率が変わったレース数
- 同じorigin_groupを複数独立根拠として数えた違反件数
- 第三者指数/予想がProduction evidenceへ混入した件数（0件が目標）

この監査は予想的中率とは別に評価し、データ出典品質の問題を予想ロジックの良否と混同しない。
