# Source provenance and source-bias policy

## 目的と適用範囲

予想システムに取り込むデータの**正しさ・時点整合・出典系統**を管理し、特定サイトへの過度な依存や、同じ上流データを転載する複数サイトを「独立した複数根拠」と誤認することを防ぐ。

本書は `DECISIONS.md` / `docs/jravan/` 配下の**将来ローカルシステム実装契約**であり、競馬判断ルールやChatGPT上の情報取得手順を定義しない。

- 競馬判断・チャット予想の実行要件は `docs/manual/` を正本とする。
- 本書はローカルシステム内のsource registry、provenance、fallback、conflict処理、監査方式だけを定義する。
- 本書をChatGPT予想時の取得プレイブックとして読み込まない。
- `docs/manual/` と意味が衝突する場合は `docs/manual/` を優先し、本書側を修正する。

## 基本原則

1. **事実データは一次情報を優先する。** JRA-VAN/JV-LinkまたはJRA公式で取得可能な項目を、民間Webサイトの転載値で通常運用しない。
2. **サイト数ではなく上流の独立性を数える。** 複数サイトで同じ値が表示されても、同一の上流データなら独立証拠として加算しない。
3. **客観データと編集情報を分離する。** 馬柱、着順、時計、通過順、上がり、斤量、馬体重、オッズ等の客観値と、記者印、指数、寸評、調教評価、予想コメントを同種のデータとして扱わない。
4. **fallbackを通常経路へ昇格させない。** 一次情報が取れず補助ソースを使った場合は、出典と取得方法を保存する。
5. **不一致は多数決で解決しない。** authority、timestamp、race/horse key、revisionを確認し、解消しなければconflictとして保持する。
6. **競馬判断のOwnerを侵食しない。** Productionへ渡すfeature/evidenceは `docs/manual/` のOwner境界に従い、実装側が独自の評価ルールを追加しない。

## 情報種別ごとのシステム取得優先順位

| データ種別 | Primary | Secondary / cross-check | 障害時fallback |
|---|---|---|---|
| 出走馬、枠、馬番、斤量、騎手、取消・変更 | JRA-VAN / JRA | 相互照合 | Web aggregatorは確認用途のみ |
| 当日馬体重・増減 | JV-Link速報WH (`0B11`) | JRA公式 | 補助Webは障害調査時のみ |
| 当日馬場・天候・発走時刻 | JRA-VAN / JRA | 公式発表の相互照合 | 民間サイトは補助 |
| 速報・確定オッズ | JRA-VAN / JRA | 相互照合 | 補助Webは緊急fallback |
| 過去成績、時計、着差、通過順、上がり | JRA-VAN / JRA | JBIS等でspot check | Web aggregatorは取得補助 |
| 血統・5代系統 | JRA-VAN BLDN | JBIS等の血統DB | Webは補助。系統分類は内部再計算 |
| 調教時計 | JRA-VAN SLOP/WOOD | 公式/信頼できる原データ | メディア主観評価は別field |
| 厩舎・騎手・馬主・生産者 | JRA-VAN master / JRA | JBIS等 | 民間サイトは表記確認のみ |
| 天気予報 | 公的/専門気象provider | 別の気象provider | 競馬サイト表示を一次予報にしない |
| 陣営コメント・取材情報 | 発言元が明確な媒体 | 原文のcross-check | 出典不明転載を独立情報としない |

この表は**ローカルシステムの取得設計**であり、チャット実行時にJV-Link等が利用可能であることを意味しない。

## Source class / origin group

### source_class

最低限、次を区別する。

- `OFFICIAL_JRA_VAN`: JRA-VAN/JV-Link
- `OFFICIAL_JRA`: JRA公式Web/公式発表
- `BREEDING_DB`: JBIS等の血統・生産系DB
- `WEATHER_PROVIDER`: 気象provider
- `MEDIA_ORIGINAL`: 独自取材・コメント・記事
- `WEB_AGGREGATOR`: 馬柱・集約表示サイト
- `INTERNAL_DERIVED`: 当システムが一次データから計算したfeature

### origin_group

`origin_group` は「独立した上流か」を判定するためのグループであり、サイト名と同義ではない。

- JRA公式とJRA-VANを照合に使っても、同じ競走事実を単純な“2票”として多数決しない。
- 複数Web aggregatorに同一の着順・時計があっても、それだけで独立観測を増やさない。
- 独自取材コメントは、原発言者・取材経路が独立している場合に限り独立情報として扱う。
- 上流が不明なWebデータは `origin_group=UNKNOWN_AGGREGATED` とし、独立性を仮定しない。

## Derived data

血統系統、インブリード、脚質分類、近走上昇度、コース適性、展開feature等は、可能な限り一次raw dataから内部計算する。

- `sire line`, `dam-sire line`, `Northern Dancer xN` 等は血統rawから再計算する。
- `last3f_rank`, `pace_position_band`, `course_repeatability` 等もraw resultから再計算可能にする。
- Webサイト固有の血統分類・脚質ラベルをそのまま内部正本にしない。

Derived featureには `derived_from` と使用したsource recordを追跡できるようにする。

## 不一致処理

同じfieldに複数sourceで不一致がある場合は次の順で処理する。

1. race/horse/date/record keyの取り違えがないか確認する。
2. source timestamp / captured_at / provider revisionを確認する。
3. JRA-VAN/JRAの最新公式値を優先する。
4. 公式同士で解消しない場合は値を推測せずconflictとして保存する。
5. conflictがFINAL必須項目なら `data_readiness=DEGRADED` とする。

## Production境界の実装監査

実装は `docs/manual/` のOwner境界を守る。特に、第三者の予想印・AI予想・出所不明の独自指数・民間サイトの総合順位等を、実装都合でProduction基準能力のevidenceへ混入させない。

これらを研究・比較表示として保持する場合も、Productionへの入力経路と物理的に分離し、`prediction.rule_application` 等から侵入していないことをテスト可能にする。

## 監査指標

開催日・検証サイクルごとに最低限次を確認する。

- critical fieldのPrimary source coverage率
- Web fallback利用率
- `UNKNOWN_AGGREGATED` 利用率
- source conflict件数
- fallbackによって使用dataが変わった件数
- 同じorigin_groupを複数独立根拠として数えた違反件数
- `docs/manual/` で許可されていない第三者評価がProduction evidenceへ混入した件数（0件目標）

この監査は予想的中率とは別に評価し、データ出典品質の問題を予想ロジックの良否と混同しない。
