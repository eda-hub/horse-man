# 次期予想アーキテクチャ変更実装計画

- 作成日: 2026-10-06
- 対象リポジトリ: `eda-hub/horse-man`
- 現行Production基準: `manual_release=v1.6.1`
- 現行検証サイクル: 第3検証サイクル（2026-09-26〜2026-10-12）
- 状態: 実装計画。未マージの本計画を現行Productionルールとして使用しない。
- 適用原則: 第3検証サイクル中は現行Productionの判断基準・印体系・Betting必須工程を変更しない。正式切替はサイクル終了審査後の別PRで行う。

## 1. 目的

horse-man の責任範囲と予想生成手順を簡素化し、以下を実現する。

1. 予想そのものの精度・再現性・説明可能性を最優先にする。
2. 実購入、購入金額、実購入記録を予想システムの中核責任から外す。
3. 根拠の弱い単発情報で印や順位が揺れることを防ぐ。
4. 一方で、強い新情報が得られた場合には根拠を示して柔軟に予想を更新できるようにする。
5. 通常レースと重賞で基本予想の骨格を共通化し、重賞固有の過去傾向がProductionを過度に支配しないようにする。
6. 新しい予想材料は原則として前向きShadow検証を経てからProductionへ昇格する。
7. 将来のJRA-VAN / DuckDB実装へ接続できるデータ構造を定義する。

## 2. 今回の変更方針

次期horse-manの標準フローを次のように定義する。

```text
事実収集
  ↓
各馬の根拠評価
  ↓
勝率・連対率・3着内率・不確実性
  ↓
Production順位
  ↓
印
  ↓
発走前固定
  ↓
結果照合
  ↓
回顧
  ↓
ルール改善候補
```

馬券購入はこのフローへ含めない。

オッズは、能力順位を変更する材料ではなく、市場との乖離分析、価格予測評価、任意の仮想収益検証に利用する。実際に何を購入するか、いくら購入するか、実際に購入したかはユーザー判断とする。

## 3. 変更しないもの

次の原則は維持する。

- AIを予想エンジン本体にしない。
- Production / Shadowを完全分離する。
- 結果を見た後に発走前Productionを遡及変更しない。
- `baseline_forecast_id` による同一予想追跡を維持する。
- 市場価格だけで能力順位・印・基準確率を変更しない。
- 見送り相当の低確信レースも、予想精度の検証対象から消さない。
- 過去snapshot・過去回顧・旧☆印を新体系へ遡及変換しない。
- バックテスト・再演では `data_cutoff` より未来の情報を使用しない。

## 4. 実装タイミング

### 4.1 第3サイクル終了前に実施してよいもの

現行 `v1.6.1` のProduction判断を変更しない範囲に限定する。

- 本計画書の追加
- 既存「☆印廃止案」の適用時期・依存関係の更新
- 第3サイクル終了審査で確認する変更候補の登録
- 次期DB / feature設計の文書化
- 新規Shadow候補の取得項目・リーク防止条件・評価KPIの定義
- 現行ルールの意味を変えない説明・参照整理

### 4.2 第3サイクル終了審査後に正式変更するもの

- 実購入・購入記録を中核フローから削除
- ☆印廃止
- 印体系の単純化
- 「根拠→評価→確率→順位→印」の順序を正式契約化
- 重賞Productionを通常レースと同一骨格へ統一
- 重賞過去傾向をProduction固定後の比較層へ限定
- Betting前提のmanual / validation / WebUI / JRA-VAN設計の再構成
- `AGENTS.md` と `DECISIONS.md` の購入・見送り・仮想精算・監査契約を次期責任範囲へ整合
- execution gateの次期schema、`scripts/check_prediction_compliance.py`、関連テストを次期契約へ対応
- 次期manual releaseへの更新

**切替の原子性**：次期manual releaseを有効化するPRでは、manualだけを先行更新しない。少なくともmanual、validationテンプレート、execution gate schema/説明、checker、checkerテスト、`AGENTS.md`、`DECISIONS.md` の次期契約を同じ切替単位で整合させる。これらのいずれかが未対応なら新releaseを現行Productionとして有効化しない。

### 4.3 次期サイクル以降にShadow検証するもの

- 近5走の相手レベル評価
- 開催期間中のレース傾向
- 新馬戦専用評価
- 競馬場・距離・コース条件統計
- クラス・年齢・性別条件別統計

## 5. 変更1: horse-manの責任範囲再定義

### 5.1 廃止対象

以下はhorse-manの正式責任範囲から外す。

- ユーザーの実購入意思の状態管理
- 実購入金額
- 実購入券種・組み合わせ
- 実購入収支
- 実購入ROI
- ユーザー予算に応じた最終馬券最適化
- 実購入完了確認を前提とするフロー

### 5.2 残す対象

- Production予想
- 順位
- 印
- 勝率・連対率・3着内率
- 予想確信度
- 各評価の根拠
- 初回→最終の変更履歴
- 結果
- 予想誤差分類
- 回顧
- Shadow比較
- オッズ予測の性能評価
- 必要に応じた固定ルールによる仮想収益検証

### 5.3 仮想馬券検証

仮想馬券はPrediction Performanceと分離した**任意の市場検証sidecar**として残す。次期標準予想・回顧の必須工程にはしない。

- 実購入とは接続しない。
- ユーザーの予算・財布事情を入力としない。
- Production予想を結果後に変更して仮想券を組み替えない。
- 固定ルールを前向きに適用する場合だけ性能評価へ利用する。
- 「見送り相当のレースだから必ず仮想精算する」という必須契約は次期仕様では廃止する。
- sidecarを実行しないレースでもPrediction KPIと回顧を完全に成立させる。
- 将来sidecar自体を削除してもPrediction層へ影響しない疎結合構造にする。

### 5.4 実購入履歴と既存記録の扱い

次期仕様では、**新しい実購入履歴をhorse-manの正式台帳へ記録する機能を廃止する**。実購入の有無、券種、金額、払戻、実購入ROIをPredictionの入力・完了条件・KPIにしない。

一方、過去サイクルで既に保存された実購入・BET/SKIP・仮想精算記録は削除・変換しない。

- 旧記録は旧契約の履歴としてread-onlyで参照可能にする。
- 旧記録を次期Prediction KPIへ自動混入しない。
- 一般的なUser Noteへ利用者が購入メモを書いた場合も、システムはそれを実購入台帳として解釈・集計しない。
- 旧契約の監査・再現では、その記録当時のmanual release / gate schema / KPI contractを使用する。

この変更により、現行 `AGENTS.md` の購入／見送り履歴、見送りを含む仮想精算、Betting gate必須化と、`DECISIONS.md` のBET/SKIP・手動購入記録・Betting監査に関する決定は次期仕様と衝突する。正式切替時に13.8の方針で同時更新する。

## 6. 変更2: ☆印廃止

既存 `docs/proposals/2026-09-20_retire_star_mark_next_cycle.md` を基礎とする。

### 6.1 次期基本印体系

原則として以下を使用する。

```text
1位: ◎
2位: ○
3位: ▲
4位: △1
5位: △2
6位: △3
```

選択頭数はレース構造に応じて6頭未満を認める。

### 6.2 原則

- 人気薄だから☆を付ける処理を廃止する。
- 妙味・価格は印へ混ぜない。
- **印はProduction順位に従って付与し、印の意味に合わせるために順位を操作しない。**
- 合理的な勝利シナリオを持つ馬が4頭以上いる混戦でも、4位以下は順位どおり△1以降とする。
- 4位以下の勝利可能性は、勝率、確率レンジ、不確実性、勝利シナリオ等の独立項目で表現し、「勝てる可能性があるから▲へ昇格」という処理をしない。
- △は順位付きの下位候補であり、「勝利可能性なし」を意味しない。
- 過去の☆は変更しない。
- サイクル横断比較では印記号だけでなくProduction順位を正本として扱う。

既存の☆廃止proposalに「勝てる主要候補なら▲までに置く」等の表現が残る場合は、正式実装前に本原則へ合わせて修正する。

## 7. 変更3: 根拠を必須にする予想契約

### 7.1 基本原則

印を直接付与・除外しない。

必ず次の順序を守る。

```text
新しい事実
  ↓
影響する評価項目を特定
  ↓
評価方向と強さを決定
  ↓
確率・不確実性を更新
  ↓
Production順位を再整合
  ↓
結果として印が変わる
```

### 7.2 各評価根拠の最低項目

可能な範囲で次を構造化する。

- `factor`: 基礎能力 / 近走内容 / 相手レベル / 適性 / 展開 / 状態 / 血統 / 騎手 / 厩舎 / その他
- `fact`: 評価根拠となる確認済み事実
- `source_ref`: 出所
- `observed_at`: 情報時点
- `direction`: plus / neutral / minus / uncertain
- `strength`: strong / medium / weak
- `applies_to`: 能力 / 今回発揮能力 / 不確実性 / 展開等
- `notes`: 二重計上防止・留保

### 7.3 順位変更

初回→最終で順位を変更した場合は最低限、

- 変更前順位
- 変更後順位
- 新たに判明した事実
- 変更対象となった評価要素
- 証拠強度
- 情報時刻
- 既存評価を上回ると判断した理由

を保存する。

単一の弱いコメント、単一オッズ変動、単発の当日レース結果、単なる再考だけでは大幅な順位変更を行わない。

### 7.4 柔軟性

一貫性のために順位を固定すること自体を目的にしない。

取消、騎手変更、重大な状態変化、明確な馬場変化、複数の独立根拠が一致した新情報等が得られた場合は、根拠を示して順位・確率を変更できる。

## 8. 変更4: 近5走の相手レベル評価

現行の「相手関係を評価する」を体系化する。

### 8.1 対象

各馬の直近最大5走について評価する。

### 8.2 取得候補

- レースクラス
- 出走頭数
- 着順
- 着差
- 通過順
- 上がり
- ペース・ラップ文脈
- 勝ち馬
- 接戦馬
- 負かした馬
- 対戦相手の当時までの能力情報
- 対戦相手のその後の成績
- 同等以上の相手との実走実績

### 8.3 データリーク防止

`as_of` を必須とする。

予想時点より未来の対戦相手成績を利用しない。

例: 2026-10-01時点の予想では、2026-10-02以降に判明した対戦相手の結果を相手レベル判定へ使用しない。

バックテストでも同じ制約を適用する。

### 8.4 導入方法

初期はProductionへ直接加点しない。

- Production: 現行相手関係評価
- Shadow: 近5走相手レベルを体系化した評価

として同一レースで比較する。

### 8.5 主な評価指標

- 上位3頭内に勝ち馬を含めた率
- ◎3着内率
- Brier Score
- 無印好走馬の事前捕捉率
- 相手レベル補正による順位改善 / 悪化件数
- 既存Productionと同順位だった割合
- 取得不能率
- 取得時間

## 9. 変更5: 重賞Productionの通常レース化

### 9.1 方針

重賞であっても基本Productionは通常レースと同じ予想骨格で作成する。

```text
通常Production情報収集
  ↓
基本予想
  ↓
確率・順位・印FIX
  ↓
重賞固有過去傾向を取得
  ↓
比較用Shadow
```

### 9.2 重賞で追加取得してよい直接情報

馬自身に直接紐づく次の情報は、通常Productionの深掘り情報として利用してよい。

- 過去走
- 同条件実績
- 血統
- 枠×脚質
- 騎手
- 厩舎
- 当日一次情報

### 9.3 Productionへ直接使用しない重賞固有集団傾向

- 過去N年の年齢傾向
- 枠傾向
- 前走ローテ集計
- 人気構造
- レース固有血統集計
- その他レース単位の歴史的集団傾向

これらはProduction固定後に比較し、Shadowとして追加価値を検証する。

### 9.4 受入条件

- 過去傾向を見てから通常Productionを作り直さない。
- 重賞でも通常レースと同じ基本評価項目を欠落させない。
- 重賞傾向が有効だった事例だけで正式昇格しない。
- Productionと重賞傾向Shadowを同一条件で比較できる。

## 10. 変更6: 開催期間中のレース傾向

### 10.1 目的

一般的な競馬場・コース傾向とは別に、「今回の開催」で実際に生じている傾向を検証する。

### 10.2 階層

```text
長期コース傾向
開催期間傾向
当日傾向
当該レース固有展開
```

を分離する。

### 10.3 収集候補

- 競馬場
- 開催日
- 開催何日目
- 芝 / ダート
- 距離
- コース
- 馬場状態
- 枠
- 4角位置
- 脚質
- 上がり順位
- ペース分類
- 内外進路
- 勝ち馬・連対馬・3着馬
- 当日天候
- 含水率等、取得可能な公式情報

### 10.4 初期運用

小標本の過剰反応を防ぐためShadow扱いとする。

1〜2レースだけで「内有利」「先行有利」等をProductionへ強く反映しない。

## 11. 変更7: 新馬戦専用評価

### 11.1 方針

新馬は馬自身の実走データが存在しないため、通常馬と同一の証拠優先順位をそのまま適用しない。

新馬専用の評価レイヤーを設ける。

### 11.2 取得候補

- 父
- 母父
- 血統構成
- 種牡馬の新馬戦成績
- 種牡馬×芝/ダート
- 種牡馬×距離帯
- 種牡馬×競馬場
- 厩舎の新馬戦成績
- 厩舎×芝/ダート
- 厩舎×距離帯
- 厩舎×騎手
- 騎手の新馬戦成績
- 調教
- 馬体重・馬体情報
- 性別
- 生産者等、追加価値を検証可能な属性

### 11.3 導入方法

初期は新馬専用Shadowとして既存予想と比較する。

血統・厩舎の一般成績だけで強いProduction評価へ直結させない。

## 12. 変更8: コース・距離・条件別統計基盤

個別条件ごとに別テーブルを大量作成せず、race属性として保持し任意集計できる形にする。

### 12.1 race属性候補

- racecourse
- surface
- course_type
- distance
- class
- age_condition
- sex_condition
- weight_condition
- field_size
- track_condition
- race_type
- meeting_id
- meeting_day

### 12.2 クラス分類

最低限以下を識別できるようにする。

- 新馬
- 未勝利
- 1勝クラス
- 2勝クラス
- 3勝クラス
- OPEN
- Listed
- G3
- G2
- G1

追加属性として、

- 古馬混合
- 年齢限定
- 牝馬限定
- ハンデ
- 別定
- 定量
- 特別競走

等を保持する。

### 12.3 コーナー / 通過情報

必要に応じてraceとは別の構造で保持する。

- corner_no
- horse_id
- position
- position_group
- gap
- source

これにより競馬場・距離・条件ごとの位置取り傾向を分析可能にする。

## 13. manual変更対象

正式切替時に最低限以下を確認・変更する。

### 13.1 `docs/manual/README.md`

- 標準フローから実購入を削除
- Prediction / Review中心へ再構成
- 次期manual releaseを定義
- 依頼別入口を更新
- 重賞も共通Productionを先に実行することを明記

### 13.2 `docs/manual/00_core.md`

- horse-man責任範囲を更新
- Production固定契約からBetting必須依存を分離
- snapshot最低項目を次期印体系・根拠構造へ更新
- 実購入状態を削除
- 過去snapshot互換性を保持

### 13.3 `docs/manual/10_prediction.md`

- ☆廃止
- 印体系のOwner定義更新
- 根拠→確率→順位→印の処理順を正式化
- 根拠最低項目
- 近5走相手レベルShadowとの接続
- 購入確信度・購入優先度等のPrediction非Owner項目を整理

### 13.4 `docs/manual/20_conditional.md`

- 重賞の基本Productionが通常予想と同じであることを強化
- 重賞固有集団傾向はProduction固定後の比較に限定
- 直接情報と集団傾向を明確に分離

### 13.5 `docs/manual/30_betting.md`

次のいずれかへ再構成する。

第一候補:
- `30_market_validation.md` 等へ役割変更
- オッズ、市場乖離、任意仮想収益検証だけを担当

または、
- 互換参照のためファイル名は維持し、実購入関連節を廃止して市場評価専用Ownerへ縮小

正式実装前に参照箇所数を調査して決定する。

### 13.6 `docs/manual/40_shadow.md`

- 買い目Shadowへの依存を整理
- 予想順位・確率・根拠差分の比較を中心にする
- 近5走相手レベル
- 開催傾向
- 新馬専用評価
- 重賞過去傾向
を独立比較できるようにする

### 13.7 `docs/manual/50_review.md`

Prediction Performanceを主軸へ変更する。

主KPI候補:

- ◎勝率
- ◎連対率
- ◎3着内率
- 上位3頭内勝ち馬捕捉率
- 上位k頭捕捉率
- Brier Score
- 順位変更改善率 / 悪化率
- 無印好走馬率
- 根拠不足変更件数
- 強い新情報による変更成功 / 失敗
- Shadow別追加価値

実購入ROIは削除する。

仮想収益検証は任意sidecarのKPIとしてPrediction KPIとは別系列にする。

### 13.8 `AGENTS.md` / `DECISIONS.md`

正式切替PRでリポジトリ全体の上位契約も同時に更新する。

`AGENTS.md` は少なくとも次を見直す。

- FINAL予想と結果・回顧の履歴保存は維持する。
- 「買い目候補、ユーザーの購入/見送り判断」を新規必須履歴から外す。
- 「見送りレースも仮想精算」を「低確信レースもPrediction回顧から除外しない」へ置換する。
- execution gateの必須対象を次期Prediction / Shadow契約へ更新する。
- Betting固有のgate、evidence、KPI契約を次期標準予想の必須条件から外す。
- 旧releaseのrecordを旧契約で検証・保持する互換方針を追加する。

`DECISIONS.md` は過去ADRを書き換えて履歴を消すのではなく、**次期契約を定める新しいADRを追加し、旧ADRのどの部分をsupersedeするかを明示する**。

少なくとも以下を対象にする。

- ADR-004: FINAL immutableのうち買い目候補必須部分
- ADR-005: BET / SKIPを同格最終判断とする契約
- ADR-010: 手動購入記録までをシステム対象とする契約
- ADR-016: Production / Shadow分離のうち正式買い目前提表現
- ADR-020: 機械ゲートのBetting必須項目
- ADR-021: Betting evidence / receipt契約

Production / Shadow分離、FINAL immutable、時点再現性、機械監査そのものは廃止せず、次期Prediction中心契約へ再定義する。

## 14. validation変更対象

### 14.1 `docs/validation/templates/chatgpt_prediction_task.md`

- 固定仮想買い目の必須化を削除
- Production順位・確率・印・根拠固定を中心に変更
- 変更理由の読戻し確認を追加

### 14.2 `docs/validation/templates/cycle03_execution.md`

第3サイクル履歴は変更しない。

次サイクル用に新テンプレートを作成し、

- 購入候補
- 投資
- 払戻
- 実購入

をPrediction主台帳から外す。

### 14.3 `docs/validation/README.md`

新規Shadow候補を登録し、Productionへ逆流しないことを明記する。

### 14.4 execution gate / checker / 監査互換

現行 `scripts/check_prediction_compliance.py` は `SUPPORTED_RELEASE = 'v1.6.1'`、`schema_version=prediction-compliance-v1` を前提とし、Productionに加えてBetting/Shadow KPI、Betting object、reviewの `prediction / price / betting` layerを要求する。このままmanual releaseだけを更新すると新releaseの正式保存・監査が成立しないため、正式切替の必須変更対象とする。

対象:

- `scripts/check_prediction_compliance.py`
- `scripts/test_check_prediction_compliance.py`
- `docs/validation/execution-gates/README.md`
- 次期execution gate schema / sample
- 日別record・cycle ledgerとの認証リンク
- 必要に応じて `scripts/verify_prediction_persistence.py` とそのテスト
- `scripts/check_cycle03.py` / `test_check_cycle03.py` は第3サイクル旧契約の履歴checkerとして意味を変更せず保持し、次サイクル契約へ流用しない
- `scripts/check_betting_performance.py` / `test_betting_kpi_split.py` は旧契約または任意市場sidecar用として責任範囲を明示し、次期Prediction適格性の必須checkerにしない

#### 次期gateの原則

- 次期Prediction標準契約では `production` を必須、適用対象の `shadow` を独立判定する。
- Betting / actual purchaseは標準Prediction gateの必須フィールド・必須KPIにしない。
- 任意の市場検証sidecarを実行した場合のみ、そのsidecar固有schema / KPIを別契約で検証する。
- reviewの必須layerからBettingを外し、Prediction中心の回顧が単独で完了できるようにする。
- snapshot / receipt / pre-race timing / data cutoff / manual_ref_commit等の時点証跡は維持する。

#### 旧契約互換

**既存 `prediction-compliance-v1` の意味を新仕様に上書きしない。**

checkerは少なくとも `schema_version + manual_release` で検証契約をdispatchできる構造へ変更する。

- `v1.6.1 + prediction-compliance-v1`: 現行のBetting要件を含む旧validatorで検証する。
- 次期release + 次期gate schema: Prediction中心の新validatorで検証する。
- **現行運用のFORWARD記録**はrepoの現行manual releaseとの一致を要求する。
- **履歴監査**はgate自身の `manual_release + schema_version` で旧validatorを選択し、repoの現行manual releaseが次期版であることだけを理由に旧gateを失敗させない。
- 旧validatorの契約意味はコード・fixtureで凍結し、現在のmanual本文を新仕様として読み替えて旧記録へ適用しない。
- 旧gateを新schemaへ自動変換しない。
- 旧recordに不足していた証跡を新releaseの規則で後付けして適格化しない。
- 未知のrelease/schema組み合わせはfail closedとする。

次期schemaの具体的なversion名は実装PRで確定するが、既存 `prediction-compliance-v1` を再利用して意味だけ変更することは禁止する。

#### release切替ゲート

次期manual releaseを現行化する前に以下をすべて満たす。

1. 新旧両validatorのテストが通る。
2. v1.6.1 fixtureが旧契約のままPASSする。
3. 次期fixtureがBetting情報なしでPrediction正式性を検証できる。
4. 次期fixtureへ旧Betting項目を入れてもPrediction必須契約へ逆流しない。
5. release/schema不一致・未知version・未来情報・発走後保存を拒否する。
6. validation templateとgate schemaが同じ必須項目を要求する。
7. CI / 実行手順が新checkerを呼び出す。
8. manual、validation、checkerのいずれかだけが先行した状態でmainへ切り替わらない。

## 15. 重賞・海外テンプレート変更対象

### 15.1 `docs/yosou/jra_racing/_template.md`

大幅変更は不要。

追加候補:

- Production予想とは独立した年次傾向ノートであることを明記
- 当年予想要約はProduction固定記録の参照に限定
- 過去傾向をProductionへ直接反映しないことを再確認

### 15.2 `docs/yosou/kaigai/_template.md`

- 「購入市場」を「市場・オッズ情報」へ変更
- 実購入前提の表現を削除

### 15.3 各重賞個別ファイル

過去ファイルを一括書換えしない。

次回更新時に新テンプレートへ段階移行する。

## 16. JRA-VAN / システム設計変更対象

### 16.1 `docs/jravan/04_prediction_engine.md`

- `user BET / SKIP` を中核フローから削除
- 根拠構造をPrediction Engine出力へ追加
- 新規featureはShadow比較可能な構造にする

### 16.2 `docs/jravan/05_odds_design.md`

- オッズを市場分析・価格予測へ限定
- Production能力順位への非逆流を維持
- 実購入判断を削除
- 任意仮想検証との接続を分離

### 16.3 `docs/jravan/06_webui.md`

削除候補:

- ユーザー予算入力
- BET操作
- 実購入記録
- 実損益

表示候補:

- Production順位
- 印
- 勝率 / 連対率 / 3着内率
- 予想確信度
- 根拠
- 初回→最終変更
- Shadow差分
- 結果 / 回顧

### 16.4 DB

既存DB設計と照合し、必要に応じて次を追加する。

- evidence
- horse_race_feature
- opponent_strength_snapshot
- meeting_trend_snapshot
- sire_condition_stats
- trainer_condition_stats
- course_condition_stats
- prediction_factor_evaluation

名称は既存schemaとの重複確認後に確定する。

## 17. 本計画の作業段階と既存JRA-VAN Phaseの対応

本節の「作業段階」は変更管理上の順序であり、`docs/jravan/phases/README.md` の正式な実装Phaseを置き換えない。コード実装は既存Phase 3→4→5→6→7→8の依存順と「各Phaseを独立PRにする」契約を維持する。

### 17.1 対応表

| 本計画の作業段階 | 内容 | 既存JRA-VAN Phase | 実装上の扱い |
|---|---|---|---|
| Stage 0 | 第3サイクル中の計画・設計準備 | Phase外 | proposalのみ。Productionを変更しない |
| Stage 1 | 第3サイクル終了審査 | Phase外 | validation / review上の変更管理。実装変更と別PR |
| Stage 2 | 次期仕様・契約の原子切替 | Phase 3〜8の前提 | manual、AGENTS、ADR、validation、gate/checker、phase文書を整合。新release有効化条件 |
| Stage 3 | Prediction / feature / Shadow engine | **Phase 3** | 根拠構造、☆廃止、共通Production、新規feature受け皿 |
| Stage 4 | Prediction Web UI | **Phase 4** | 次期Production表示、根拠、Shadow差分。購入UIを要求しない |
| Stage 5 | Odds / Market validation | **Phase 5** | 「Betting decision」から市場評価・任意仮想検証へphase文書を先に改訂してから実装 |
| Stage 6 | Result / Review preparation / Automation | **Phase 6** | 実購入settlement必須を外し、全Productionの結果結合を中心化 |
| Stage 7 | AI review | **Phase 7** | 次期根拠・誤差分類を用いた回顧支援。自動昇格は禁止 |
| Stage 8 | Backtest / Rule lifecycle | **Phase 8** | data cutoff、旧新release比較、Shadow昇格判定 |
| Stage 9 | 新規予想featureの前向き検証 | 主にPhase 3 + Phase 8 | feature生成はPhase 3、効果判定と昇格はPhase 8。1機能ずつ独立PR |

### 17.2 Stage 0: 第3サイクル中の準備

対象:

- 本計画書
- ☆廃止proposal更新
- 第3サイクル終了審査項目登録
- 次期feature / DB設計案

完了条件:

- Production v1.6.1へ影響する変更がない。
- 未マージproposalをProduction根拠として参照しない。
- 第3サイクルの既存KPI・対象集合・固定成果物を変更しない。

### 17.3 Stage 1: 第3サイクル終了審査

2026-10-12開催分までを現行契約で閉じた後に実施する。

評価項目:

- Betting工程に要した処理量と予想工程への影響
- 最終予想未完了との関係
- ☆印の実用価値
- 重賞過去傾向Shadowの追加価値
- 根拠不足による順位変更例
- 相手レベル不足による誤評価例
- 新規案の次サイクル採否

完了条件:

- 終了審査と正式変更を同じPRで混在させない。
- 未検証項目を効果ありとして昇格させない。

### 17.4 Stage 2: 次期仕様・監査契約の原子切替

コードPhaseへ進む前に、次期仕様の正本と監査経路を揃える。

同じ切替単位で最低限整合するもの:

- `docs/manual/`
- `AGENTS.md`
- `DECISIONS.md` のsuperseding ADR
- `docs/validation/` の次期テンプレート
- execution gate次期schema
- `scripts/check_prediction_compliance.py`
- checker関連テスト
- `docs/jravan/phases/phase_3_rule_engine.md`
- `phase_4_prediction_ui.md`
- `phase_5_odds_betting.md`
- `phase_6_settlement_automation.md`

完了条件:

- 新releaseの保存・監査がBetting情報なしで成立する。
- v1.6.1記録を旧契約で引き続き検証できる。
- 新旧schemaのdispatchがテストされる。
- Phase 3〜6の目的・受入条件が次期仕様と矛盾しない。
- manualだけ、checkerだけ、phase文書だけの片側切替を行わない。

### 17.5 Stage 3以降: 既存Phase順でコード実装

仕様切替後のコード変更は `docs/jravan/phases/README.md` を正とし、Phase 3から順に独立PRで進める。

依存順序:

```text
Stage 2 契約切替
  ↓
Phase 3 Feature / Production / Shadow engine
  ↓
Phase 4 Prediction Web UI
  ↓
Phase 5 Odds / Market validation
  ↓
Phase 6 Result / Review preparation / Automation
  ↓
Phase 7 AI review
  ↓
Phase 8 Backtest / Rule lifecycle
```

Phase 5・6は現行文書が購入判断・実購入settlementを前提としているため、Stage 2でphase文書の目的と受入条件を改訂した後にコード実装へ進む。Phase 3・4も印体系・根拠出力・新release整合を受入条件へ反映する。

### 17.6 新規Shadow検証

次の順序を基本とし、一度に複数をProductionへ昇格させない。

1. 近5走相手レベル
2. 開催期間傾向
3. 新馬専用評価
4. 条件別統計feature拡張

各featureについて、

- Phase 3で取得・feature生成・Shadow出力を実装
- Phase 8でdata cutoff、前向き比較、非劣化、追加価値を検証
- 正式昇格は別のmanual変更PR

とする。

完了条件:

- 各featureの単独追加価値を比較可能。
- data cutoffが検証可能。
- 取得不能時に既存Productionが継続可能。
- 結果後に条件を追加して適格化しない。

## 18. テスト計画

### 18.1 ドキュメント整合

- manual release一致
- Owner / depends_on / produces整合
- `AGENTS.md` / `DECISIONS.md` / manual / validation / JRA-VAN phase文書の責任範囲一致
- 廃止用語の参照残り検索
- 実購入前提のリンク切れ確認
- ☆参照残り確認
- 重賞Production前に過去傾向が適用されていないことを確認

### 18.2 Prediction単体

代表ケースを用意する。

- 通常条件戦
- 重賞
- 新馬
- 未勝利
- 昇級馬
- 牝馬限定
- OPEN / 特別
- 強い直前情報あり
- 弱い直前情報のみ
- データ欠測あり

確認:
- 根拠のない印変更0
- 市場価格だけによる順位変更0
- 弱い単発情報による大幅変更0
- 強い新情報では正規手順で更新可能
- 印と順位の整合

### 18.3 Shadow

- Production固定後にのみ実行
- Productionへ逆流しない
- 共通input cutoffを使用
- featureごとに結果を分離
- 欠測時に未完了/不適格を明示

### 18.4 履歴互換

- 旧☆snapshotを読める
- 旧Betting recordを消さない
- 新版KPIへ旧実購入記録を自動混入しない
- 旧サイクルを新ルールで再採点しない
- `v1.6.1 + prediction-compliance-v1` の既存fixtureが旧validatorでPASSする
- 次期releaseへ切り替えたmain上でも旧gateを旧契約で検証できる

### 18.5 機械監査

最低限以下のcheckerテストを追加する。

- 現行v1.6.1正常gate → PASS
- 現行v1.6.1でBetting必須項目欠落 → 旧契約どおりFAIL
- 次期release正常gate（実購入・Bettingなし） → PASS
- 次期releaseでProduction必須根拠欠落 → FAIL
- 次期releaseで任意市場sidecarなし → Prediction適格性へ影響しない
- schema / manual_releaseの不正な組み合わせ → FAIL
- 未知schema / 未知release → FAIL
- 発走後保存を前向き証跡として宣言 → FAIL
- REPLAYを前向きKPIへ昇格 → FAIL
- 旧gateを新validatorへ暗黙変換しない
- current manual releaseが次期版でも、履歴監査モードではv1.6.1 gateを検証可能

checkerテストだけでなく、validation templateのsampleを用いたend-to-end検証を1件以上行う。

## 19. 受入条件

本変更全体は以下を満たした場合のみ完了とする。

1. horse-manが実購入情報なしで予想・固定・結果・回顧を完結できる。
2. Production順位と印が一貫する。
3. 主要な印・順位に説明可能な根拠がある。
4. 根拠が弱い場合は不確実性として扱い、印操作で補わない。
5. 強い新情報への柔軟な変更経路が残っている。
6. 通常レースと重賞の基本Productionロジックが共通である。
7. 重賞固有過去傾向はProductionを直接変更しない。
8. 新規予想メソッドはShadowを経ずにProductionへ昇格しない。
9. data cutoffより未来の相手成績を利用しない。
10. 過去snapshot、回顧、旧☆、旧Betting recordを遡及変更しない。
11. manual、validation、JRA-VAN設計、WebUIで責任範囲が一致する。
12. 変更理由・受入条件・検証結果を日本語PRで追跡できる。
13. 次期manual releaseへ切り替えた時点で、対応するexecution gate / checker / validation templateが同時に利用可能である。
14. 新release切替後もv1.6.1の過去記録を旧契約のまま機械検証できる。
15. 次期Predictionの正式性判定は実購入・Betting情報がなくても完了できる。
16. `AGENTS.md` と `DECISIONS.md` が次期責任範囲と矛盾しない。
17. JRA-VANのコード実装は既存Phase 3→8の順序と独立PR契約を維持する。

## 20. ロールバック

次期manual release適用後に重大な問題が見つかった場合は、

- 過去成果物を変更せず
- 新releaseの適用を停止し
- 直前のmanual releaseを再度参照可能な状態に戻し
- 新規Shadowデータは比較記録として保持
- DB migrationがある場合は旧schema読取互換を維持

する。

結果に合わせて新releaseのProductionを旧releaseへ書き換えない。

## 21. 実装PRの分割方針

コード実装は1つの巨大PRにせず、既存JRA-VAN Phase単位の独立PRを維持する。ただし、**次期releaseを有効化する契約切替だけは、manualと監査が一時的に不整合にならないよう原子的な1 PRにまとめる。**

推奨順:

1. 第3サイクル終了審査PR
2. **次期契約切替PR**  
   manual / AGENTS / superseding ADR / validation template / execution gate schema / checker / checker tests / Phase 3〜6文書を同時整合し、次期manual releaseを有効化
3. Phase 3: Feature / Production / Shadow engine PR
4. Phase 4: Prediction Web UI PR
5. Phase 5: Odds / Market validation PR
6. Phase 6: Result / Review preparation / Automation PR
7. Phase 7: AI review PR
8. Phase 8: Backtest / Rule lifecycle PR
9. 近5走相手レベルShadow PR
10. 開催傾向Shadow PR
11. 新馬Shadow PR
12. 条件別統計基盤PR

次期契約切替PRは「複数機能をまとめて実装するPR」ではなく、**同一releaseの仕様・保存形式・監査器を一致させるための不可分な契約変更**とする。Phase 3以降の実装コードはそこへ混在させず、各Phaseの受入条件を満たしてから次へ進む。

## 22. 未決事項

正式実装前に以下を決める。

- `30_betting.md` を改名するか、互換性のため名称を維持するか
- △を最大3頭固定とするか、レース構造に応じた可変数とするか
- 相手レベルの初期算定方法をルールベースにするか、feature値のみ保持するか
- 開催傾向の最低サンプル条件
- 新馬専用評価で調教データをどの段階から必須にするか
- 条件別統計の集計期間・縮約単位
- 既存DB schemaに追加するか、新規feature schemaを分離するか

未決事項はコードで暗黙決定しない。

## 23. 推奨実施順

現時点では以下を推奨する。

1. 第3サイクルは `v1.6.1` のまま2026-10-12まで完走する。
2. 並行して本計画と次期仕様候補だけを整備する。
3. 第3サイクル終了審査で変更理由を実測と対応付ける。
4. Stage 2の次期契約切替PRでmanual・上位契約・validation・gate/checker・Phase文書を原子的に整合し、新releaseを有効化する。
5. その後は既存JRA-VAN Phase 3→8の順にコード実装を独立PRで進める。
6. 新規featureは1つずつShadow検証する。
7. 精度・再現性・説明可能性の改善を確認してからProductionへ昇格する。
