# ChatGPT 次期予想タスクテンプレート（v1.7.0予定）

> 状態: 次期契約用。main の現行releaseが `v1.7.0` へ切り替わるまではProductionへ使用しない。

## 目的

実購入・Bettingを必須工程にせず、発走前のProduction予想を順位・確率・印・根拠とともに固定し、結果後に予想精度を回顧できる状態へする。

## 発走前に必須の出力

- race_id / race_date / scheduled_post_time / data_cutoff
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
- **次期推奨構成**: Production固定後、独立したオッズ非依存の推奨買い目（券種・馬番の組み合わせ・ユニーク点数・優先順位・短い理由）、または根拠付き「推奨なし」を提示する。明示的な印のみ依頼・未完了も別状態として保存する。
- 推奨生成にオッズ・人気・期待値・実購入・予算入力は不要。◎○と同時好走・着順適性を先に確認し、原則1券種（多くても2種類程度）の自然な本線を選ぶ。旧☆価格目的追加・非◎縦目は移植しない。

## 根拠契約

各根拠は最低限次を持つ。

- factor
- fact
- source_ref
- observed_at_jst（data_cutoff以下）
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

1. 予想作成前に `prediction-persistence-intent-v1` を作り、race_id、snapshot_id、deadline、v2 JSONの `artifact_path` を固定する。
2. Production snapshotは原則 `docs/validation/snapshots/YYYY-MM-DD/SNAPSHOT_ID.json` へ保存する。
3. JSONには少なくとも `schema_version=prediction-snapshot-v2`、snapshot_id、race_id、working_branch、scheduled_post_time_jst、manual release/commit、baseline ID、data_cutoff、順位、印、確率、確信度、根拠、fixed_atを持たせる。
4. FIX内容のJSONファイルbytesからSHA-256を保持し、snapshot保存・読戻し、同一artifactのreceipt保存・読戻し後に `--task-complete --fixed-content-sha256` で一致確認する。
5. `prediction-compliance-v2` gateを作成し、snapshot内容とgate内容を完全照合する。
6. persistence auditとcompliance auditの両方で未宣言snapshot・未登録gateがないことを確認する。
7. 保存・監査が未完了でも予想内容を結果後に捏造・補完しない。

旧Markdown snapshotはv1.6.1履歴互換のため継続して読めるが、新規v1.7.0 Productionの標準形式にはしない。

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
