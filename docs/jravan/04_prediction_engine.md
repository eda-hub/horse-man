# Prediction engine design

## 正本
Prediction Engineは独自ルールを発明しない。競馬判断の正本は `docs/manual/` とし、現行release・Owner・決定権を実装へ写像する。

## Productionパイプライン
```text
JRA data
 -> normalized core/market
 -> feature generation
 -> docs/manual release verification
 -> 00_core execution contract
 -> 10_prediction Production baseline
 -> 20_conditional formal adjustments (該当時)
 -> live body-weight/event ingest
 -> FINAL readiness check (T-20以降)
 -> Production baseline freeze / baseline_forecast_id
 -> odds observation / final-odds forecast
 -> 30_betting market evaluation / ticket candidates
 -> user BET / SKIP
```

価格情報は市場評価・購入判断には使うが、`10_prediction` の能力順位・基準確率を価格だけで変更しない。

## Shadowパイプライン
```text
fixed Production
 -> copy baseline context
 -> 40_shadow / 51B / Experimental delta
 -> shadow forecast
 -> optional shadow ticket comparison
 -> result comparison
```
Shadowから同一レースのProductionへ書き戻さない。

## Result / Review
結果確定後はProduction、Shadow、実購入を `50_review` の観点で比較し、同じ `baseline_forecast_id` で追跡する。

## Rule実装方式
`docs/manual/` を別YAMLへコピーして新しい正本を作らない。実行可能ロジックはPythonコード/設定として実装してよいが、各実装単位を `module + rule_id` に紐付ける。

各Predictionには次を保存する。
- `manual_release`
- `manual_manifest_hash`
- 使用module hashes
- rule IDs
- engine version
- feature version
- data cutoff
- `data_readiness`
- 必須当日データごとの observed/captured timestamp、source、acquisition method、freshness、coverage、missing reason

manifestと必須moduleの `manual_release` が一致しない場合はfail closedする。

## スコアと確率
内部特徴量や説明用scoreは保持してよいが、最終的な意味・優先順位は `10_prediction.md` を正とする。最低限、基礎能力/今回発揮能力、適性、展開、確率、予想確信度の説明を再現できること。

## データ時点
- PRE: 事前取得可能な非価格情報中心
- DAY: 当日馬場・天候・関連レース実測等を追加
- FINAL: T-20以降にreadinessを再検証し、発表後に保存済みの当日公式馬体重、直前非価格情報、市場情報を揃えた運用snapshot

FINALの必須非価格情報は、当日馬体重と増減、最新馬場・天候、取消/競走除外、騎手・斤量・発走時刻等の変更eventとする。馬体重は通常T-20より前に発表・取得されるため、**T-20以降の新規取得を必須条件にしない**。現在の出走対象馬すべてについて同一レースの当日公式WHが揃っていれば、T-20より前の取得snapshotでもFINALに利用できる。

馬体重readinessは `PENDING / READY / PARTIAL / MISSING / STALE / SOURCE_ERROR` を区別し、`READY` 以外でFINALへ進む場合は原則 `data_readiness=DEGRADED` とする。`STALE` は前日・別レース・旧出走構成など現在レースへ適用できない場合に限り、単なる取得時刻の古さでは判定しない。

`DEGRADED` の場合でも予想継続は可能だが、欠損が馬体重・馬場等の今回発揮能力に影響しうる情報なら予想確信度の上限を下げ、購入確信度も別途下げる。後からデータが取得できても固定済みFINALを結果に合わせて上書きせず、取得遅延eventとして回顧に残す。

PRE/DAY/FINALは同一ルール体系の時点snapshotであり、チャットが変わっただけ、またはオッズだけが変わっただけでは `baseline_forecast_id` を再発行しない。

## 購入判断との分離
予想側は推奨候補・買い条件・見送り条件を提示する。ユーザーの購入馬、券種、予算は `30_betting` の二段階購入設計に従い、能力評価を変更せず指定条件内で購入設計を最適化する。

## AI非依存
AIが停止していてもProduction予想、Shadow比較、買い目候補、結果精算は動作すること。

## 評価指標
Prediction Performance、Market/Odds Forecast Performance、Bet Performance、Decision Performance、Shadow Validation Performanceを分離する。加えてFINAL data readinessを記録し、`READY` と `DEGRADED` の予想精度・購入成績を分離して比較できるようにする。

## 今後の検討事項 — コース要求 × 馬個体適性の構造化

現行manualの `10_prediction.md` と `40_shadow.md` にある E-09「馬個体適性プロファイル」および E-04「位置取り主導権」を前提に、重複ルールを増やさず、コース物理特性・ペース形状と馬個体の再現性を構造化featureとして扱うことを検討する。

基本形は次とする。

```text
Race Course Demand Profile
        ×
Horse Aptitude Profile
        ↓
Course-Demand Fit
```

### コース側で追加・明示を検討するfeature

既存E-09で定義済みの直線長、急坂/平坦、コーナー半径・角度、3〜4角の上下り、小回り、スタートから最初のコーナーまでの距離、直線入口の加速要求、トップスピード持続要求は再定義しない。そのうえで、次を追加候補とする。

- スタート位置の環境差（客席前 / 向正面など）
- スタート地点の路面と本走路面の組み合わせ（芝スタート→ダート等）
- ワンターン / 4コーナー / それ以上のコーナー構成
- 道中の坂回数・位置・勾配と、最終直線坂の有無・強度
- コーナーの連続性、きつさ、大小
- 区間ごとの要求加速・巡航・減速耐性

### ペース形状feature

平均ペースだけでなく、「どの区間で速くなるか」を別featureとして扱うことを検討する。

- 澱みない一定巡航型
- 前半高速→後半減速型
- 前半緩み→残1000〜800m付近からロングスパート型
- 前半緩み→直線入口以降の瞬発力型

同じ平均ペースでも要求能力が異なるため、過去走のレースラップ、コーナー順位、上がり3F等から、その馬が各pace shapeで能力を維持・発揮できたかを推定する。

### 馬側で検討する適性feature

- `early_position_gain`: 発馬後から最初のコーナーまでに希望位置を取れる能力
- `high_cruise_fit`: 高速巡航への適性
- `front_loaded_pace_fit`: 前半高負荷型への適性
- `midrace_acceleration_fit`: 道中からのペースアップへの適性
- `late_sprint_fit`: 終盤だけの瞬発力勝負への適性
- `uphill_fit`: 坂での能力維持
- `multi_slope_fit`: 複数回の坂越えへの適性
- `tight_turn_fit`: 小さくきついコーナーへの適性
- `one_turn_fit`: ワンターン適性
- `multi_turn_fit`: コーナー4つ以上の適性
- `long_straight_sustain_fit`: 長い直線で脚を持続する適性
- `short_straight_acceleration_fit`: 短い直線で素早く加速する適性

### 血統の扱い

血統は `10_prediction.md` の既存方針どおり、適性を断定するfeatureではなく事前仮説として使用する。坂、持続力、瞬発力、距離等の適性仮説を作る補助情報には使えるが、当該馬自身の実走と矛盾する場合は実走を優先する。

### 実装・検証方針

- 既存E-09 / E-04をOwnerとして扱い、新しい競馬判断ルールを別系統で増殖させない。
- 初期段階ではProductionへ直接昇格させず、Shadow / 比較featureとして前向き検証する。
- 加点表の単純合算ではなく、レース側の要求と馬側の適性のinteractionとして扱う。
- 未経験条件は弱点と断定せず、不確実性として保持する。
- 同じ根拠をコース適性・位置取り・持続力等で二重計上しない。
- 実装時は `feature.runner_feature` / `features_json` に保持し、feature versionと元データprovenanceを追跡可能にする。
- 十分なデータが揃った後は、表形式featureとの相性を踏まえ、CatBoost / LightGBM等のLearning-to-Rankを比較候補とする。ただしProductionの最終的な意味・優先順位は引き続き `docs/manual/` を正とする。
