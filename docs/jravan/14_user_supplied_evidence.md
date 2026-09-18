# User-supplied evidence provenance / validation design

## 目的

将来のローカル予想・回顧システムで、チャットやUIからユーザーが提供した独自収集情報を、通常のJRA-VAN/JRAデータやWeb取得情報と混同せず保存・検証できるようにする。

競馬判断の正本は `docs/manual/` とし、本書はデータ構造・provenance・事後検証の将来実装契約だけを扱う。ユーザー提供情報を理由に、実装側が独自のProduction評価ルールを追加してはならない。

### 現行チャット運用との境界 — 2026-09-18

本書の `prediction.user_evidence` 等は将来のローカル実装候補であり、ChatGPT上の予想時にGitへ逐次保存することを要求しない。

- 現行チャット予想では、発走前のユーザー発言と予想回答をpre-race snapshotとする。
- 予想中は記録目的のGit書き込みを行わず、結果後の回顧でチャット履歴から必要なevidence recordを構築してGitへ保存する。
- 将来ローカルシステムでpre-race eventを自動保存する場合も、予想応答のクリティカルパスを長時間ブロックしない方式とする。
- チャット履歴を参照できないレースは結果から事前evidenceを復元せず、前向き検証対象から除外する。


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

## 12. 過去蓄積知見の一括取り込み — BACKFILL_SEED

U-02開始前からユーザーが蓄積していた、コース・距離・枠・血統・脚質・馬場・騎手・厩舎等の条件別知見は、通常のレース固有evidenceとは別に `BACKFILL_SEED` として保存する。

候補field:

```text
seed_id
received_at
scope
claim_group_raw
information_theme[]
upstream_source nullable
source_origin_status
precheck_status
unresolved_terms[]
```

BACKFILL_SEEDには次の制約を置く。

1. 過去レースへ遡って成功・失敗を採点しない。
2. 元ソース・対象期間・母集団が不明なら `UNKNOWN / UNVERIFIED` を維持する。
3. 同一claim group内の複数主張を、利用時に原子的claimへ分解する。
4. 今後該当レースで実際に使う場合だけ、発走前に通常の `user_evidence_id` を発行する。
5. 略号・表記が曖昧な場合は原文を保持し、推測正規化しない。
6. BACKFILL_SEEDの存在自体をProduction加点理由にしない。

将来の検証では、特に血統・枠・騎手・厩舎heuristicについて、人気・事前能力・クラス・馬場・開催時期・使用コース・頭数等の交絡を可能な範囲で分離する。

これにより、過去知見を捨てずに保持しつつ、結果既知データへの後付け最適化を防ぎ、前向きに再現性を評価できる。
