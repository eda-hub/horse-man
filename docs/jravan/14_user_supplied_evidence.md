# User-supplied evidence provenance / validation design

## 目的

将来のローカル予想・回顧システムで、チャットやUIからユーザーが提供した独自収集情報を、通常のJRA-VAN/JRAデータやWeb取得情報と混同せず保存・検証できるようにする。

競馬判断の正本は `docs/manual/` とし、本書はデータ構造・provenance・事後検証の将来実装契約だけを扱う。ユーザー提供情報を理由に、実装側が独自のProduction評価ルールを追加してはならない。

## 1. 基本原則

1. ユーザー提供情報は捨てず、**独立したevidence record**として保持する。
2. 「ユーザーが言った」という事実と、元の情報源を分ける。
3. 元ソースが分かる場合、ユーザーを上流sourceとして置き換えず、実際の発言元・媒体・観察主体を保持する。
4. 事実、観察、コメント、解釈、予測を分離する。
5. factual validity と predictive relevance を別fieldで評価する。
6. 単発の的中・不的中からsource weightを自動更新しない。
7. user単位の単純な「信頼度スコア」を作らず、情報種別・上流source・テーマ・条件ごとに集計する。
8. 結果後にclaimを再解釈して書き換えない。pre-race snapshotを不変にする。

## 2. source class拡張候補

`docs/jravan/11_source_provenance.md` の将来拡張として、最低限次を区別することを検討する。

- `USER_RELAYED`: ユーザーが外部の情報をチャット/UI経由で伝達
- `USER_OBSERVATION`: ユーザー自身の現地・映像・パドック等の観察
- `USER_INTERPRETATION`: ユーザー自身の分析・解釈

ただし `USER_RELAYED` では、可能なら別fieldに本来の `upstream_source_class` / `upstream_source_name` / `origin_group` を保持する。

例:

```text
submitted_via = USER_RELAYED
upstream_source_class = MEDIA_ORIGINAL
upstream_source_name = <媒体名>
origin_group = <原取材系統>
```

同じ調教師コメントを複数サイト経由でユーザーが収集した場合、origin_groupが同一なら複数の独立証拠として数えない。

## 3. evidence record案

将来の保存先候補として `prediction.user_evidence` または同等のevent tableを持つ。

候補field:

```text
user_evidence_id
race_id
horse_id nullable
baseline_forecast_id
captured_at
submitted_channel
claim_text
claim_summary
evidence_type
submitted_via
upstream_source_class
upstream_source_name
upstream_url nullable
origin_group nullable
source_origin_status
precheck_status
production_usage
influence_area
created_before_post_time
```

`claim_text` は可能なら原文を保持し、正規化した `claim_summary` と分ける。

## 4. evidence_type

最低限:

- `FACT`
- `OBSERVATION`
- `COMMENT`
- `INTERPRETATION`
- `FORECAST`

これにより、例えば「1600mへ距離延長する」というFACTと、「距離延長で追走が楽になる」というINTERPRETATIONを同じ判定軸で採点しない。

## 5. 事前verification

結果確認前に確認できる範囲で、

- `VERIFIED`
- `PARTIAL`
- `UNVERIFIED`
- `CONFLICT`

を保持する。

verificationには可能な限り既存source provenanceを使う。JRA/JRA-VANで確認可能な客観事実は公式値へ照合し、主観観察を「公式に確認できない=誤り」としない。

## 6. review record案

結果後は `review.user_evidence_review` または同等テーブルで、事前recordを参照して次を保存する。

```text
user_evidence_id
reviewed_at
factual_validity
predictive_relevance
decision_contribution
observed_outcome
review_notes
review_rule_version
```

### factual_validity

- `CONFIRMED`
- `PARTIAL`
- `REFUTED`
- `UNVERIFIABLE`
- `NOT_APPLICABLE`

### predictive_relevance

- `POSITIVE`
- `NEUTRAL`
- `NEGATIVE`
- `UNRESOLVED`
- `NOT_APPLICABLE`

### decision_contribution

- `HELPFUL`
- `NEUTRAL`
- `HARMFUL`
- `NOT_USED`

## 7. 集計単位

将来のsource/evidence calibrationは、user単位ではなく原則次で行う。

```text
evidence_type
× upstream source / origin_group
× information_theme
× race_condition_bucket
```

`information_theme` 候補:

- training
- paddock_body
- stable_comment
- distance_fit
- course_fit
- pace_position
- growth_form
- prior_trouble
- track_condition
- equipment_change

十分なサンプル数を満たさないcategoryは率で昇格・降格させない。

## 8. Productionへの接続

ユーザー提供情報は、`docs/manual/` に既に存在する評価概念のevidenceとしてのみProductionへ渡す。

例:

- 調教情報 → 状態評価
- 条件替わり解釈 → 適性 / 今回発揮能力
- 過去不利情報 → レース内容評価
- 位置取り観察 → 展開 / 実戦再現性

第三者の予想印・AI評価・総合指数は、ユーザー経由であってもそのまま基準能力の独立evidenceへ昇格させない。

過去のevidence review集計をProductionのweightへ反映する場合は、`50_review.md` の昇格基準を満たし、別PRで明示的にOwnerルールへ反映する。

## 9. model / feature実装時

将来的なモデルでは、user evidenceを直接ラベル化して学習へ流し込まず、まず構造化・検証済みfeatureへ変換する。

例:

```text
user says: 前走は直線で進路がなく脚を余した
↓
verified prior-trouble evidence
↓
structured feature candidate: prior_trip_compromised = true
provenance = user evidence + verified race record/video note
```

変換不能な主観情報はraw evidenceとして保存し、無理に数値featureへしない。

## 10. 監査

最低限、次を検査可能にする。

- 結果後にpre-race claimが変更されていないこと
- upstream sourceが既知なのにUSERだけへ潰されていないこと
- 同一origin_groupの重複加点がないこと
- `UNVERIFIED` / `CONFLICT` 情報が事実確定扱いされていないこと
- 第三者予想がProduction能力根拠へ侵入していないこと
- user evidenceの過去成績だけで自動weight変更していないこと

## 11. プライバシー / 保存範囲

競馬予想に必要な情報だけを保存し、ユーザーの個人情報・決済情報・Wallet関連情報等をevidence recordへ混入させない。

情報源の記録に必要なのは媒体・発言元・URL・観察種別等であり、予想に不要な個人属性を保存しない。
