# ChatGPT 次期予想タスクテンプレート（v1.7.0予定）

> 状態: 次期契約用。main の現行releaseが `v1.7.0` へ切り替わるまではProductionへ使用しない。

## 目的

実購入・Bettingを必須工程にせず、発走前のProduction予想を順位・確率・印・根拠とともに固定し、結果後に予想精度を回顧できる状態へする。

公式発走時刻の変更時は `docs/validation/contracts/cycle04_post_changes.md` に従い、独立した公式原文・変更履歴のGit読戻しを確認する。初回登録時刻、旧FIX・事前宣言・receiptは変更しない。変更後の新規固定だけを新予定で実施する。

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
- 推奨生成にオッズ・人気・期待値・実購入・予算入力は不要。◎○と同時好走・着順適性を先に確認し、原則1券種（多くても2種類程度）の自然な本線を選ぶ。複勝は○など根拠ある非◎も対象。三連単は◎1着を原則とし、○/▲1着・◎2着の根拠ある逆転も認める。旧☆価格目的追加・馬連/ワイド等の非◎縦目は移植しない。

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
7. 推奨が要求される場合、Prediction作成前の事前宣言に `recommendation_scope`（race_id/推奨ID/保存予定path）を含める。固定後に独立推薦intentと推奨snapshotを作成し、推薦JSON全体の `content_sha256` を記録したreceiptで固定時刻→保存確認→receipt読戻し→発走時刻の順を保証する。Prediction gateも各推奨revisionごとにSHA-256付きの固定証跡を残す。
8. 推奨の前向き適格は元Predictionの `FORWARD + Production ELIGIBLE` が前提。結果照合では同じ開催日・レースIDを必須検証する。旧版は当時のPredictionを参照して失効状態を保つ。
9. 保存・監査が未完了でも予想内容を結果後に捏造・補完しない。

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


## 保存拒否と発走時計の是正（2026-10-17、実装後の新規試行に適用）

正式レースでの発走前保存は次の順序を必須とする。未マージのPR・計画を既存本番で有効と自己申告しない。

1. 対象開催日とrace ID、公式scope、公式発走変更chain、日次branchと作業対象pathを確認する。実際のChatGPT/GitHub連携の権限と利用経路を確認する。未確認なら成功と表現しない。
2. 書込み直前・本体読戻し直後・receipt読戻し直後に、現在UTCを取得して `prediction_clock.py` / `verify_prediction_persistence.py --clock-status --date YYYY-MM-DD --clock-race-id RACE_ID` で判定する。第4運用入口は `cycle04_workflow.py --clock-status --date YYYY-MM-DD --clock-race-id RACE_ID`。JST表示、残秒、根拠、状態を返す。実時計が取れない環境では読取専用の計算値を用意できても、実測と混同せず時刻未判定とする。公式scopeと発走変更chainの読取りが終わった**後**に判定時計を新規取得する。取得前の時計を読取り後まで流用しない。時計が5秒超古い、オフセット/秒精度がない、monotonicとの乖離が2秒超、境界不明なら未判定。予定到達は実発走確認済みではない。
3. 正式intentは分析前にGit保存・固定commitから同一bytes読戻しする。FIX独立manifest→本体→receipt→個別検査の順序を守る。自己申告のreadback、ローカル保存、Actions成功だけで正式完了にしない。
4. 固定bytesとSHA-256を保持し、障害を `prediction_persistence_io.py` の拒否分類・操作記録に残す。権限/branch制約、SHA競合、通信/timeout、CI失敗、安全性拒否、理由不明を分ける。拒否された操作を別経路や高権限で迂回しない。通信系のみ、同一原本の遠隔読取り後に最大2回まで許可済みの保存を再試行する。独立した許可済み経路がなければ切替不可と明記する。
5. 実行環境にPythonと承認済みGitHub Contents API認証情報がある場合は、`python3 scripts/prediction_persistence_io.py --date YYYY-MM-DD --race-id RACE_ID --path RELATIVE_PATH --payload-file FIXED_FILE --operation-id UNIQUE_ID --write` を使用できる。同一bytesの既存原本はcommit固定で読戻し、再書込みせず存在確認済みとして扱う。固定原本と異なる内容は `--allow-update` を指定しても上書きせず、新しいrevision/pathで独立保存する。トークンや権限の自動取得・branch自動作成はしない。ChatGPTのGitHub連携利用時は同等の書込→返却commit固定読戻しを連携ツールで実行し、Pythonアダプター成功と取り違えない。
6. 失敗時は固定原本と秘匿済み障害記録を実行環境に保全し、GitHub正式保存は未完了と表示する。branch初期確認段階の拒否（HTTP 403等）でも `--local-incident` へ要求ID・応答分類・API到達状態を保存する。ローカルログ保存失敗も別途表示する。機密文字列を公開リポジトリに記録しない。事故記録の正式保存先は `docs/validation/persistence-incidents/YYYY-MM-DD/` だが、これは当時のreceiptを代替しない。旧データ・過去の証跡を遡及補完しない。

固定原本の保存前には `--race-id`、`--date`、日次branch、対象path、JSON本文のrace ID／開催日／発走予定を照合し、公式scope／発走変更chainから**当該レース**について取得した時刻判定のID・日付・予定時刻とも一致させる。11Rの原本に12Rの時計を使うこと、異なる日付・snapshot IDのパスへ固定することは不可。複数レースの一括intentは最早発走時刻と等しい公式時計を指定する。推奨の独立宣言は `docs/validation/recommendation-intents/YYYY-MM-DD/`、推奨認証は `docs/validation/recommendation-gates/YYYY-MM-DD/`、Prediction固定gateは `docs/validation/recommendation-prediction-gates/YYYY-MM-DD/` に限って新規原本保存を許可する。古い原本や同名gateを異内容上書きせず、新revision・historyによる別pathを使用する。

**ID互換・共有receiptの例外・障害記録復旧**：レースIDは `20261018-TOK-11`（TOK/KYO/NII短縮形式）と `2026-10-18-TOKYO-11`（TOKYO/KYOTO/NIIGATA長形式）を同じ開催日・場・レース番号へ正規化して照合する。異なるレースを混用してはならない。正式推奨は共有 `docs/validation/persistence-receipts/YYYY-MM-DD.md` へ、先行するR01および他レースのreceiptを**1 byteも変更せず**R02を新規追記する。CLIは共有ファイルの既存bytesに追加レコードを末尾連結した完成版を `--payload-file` に渡し、`--append-receipt --write` を明示する。既存blob SHAと原本bytesの両方を再照合し、整合する場合だけ条件付き更新し、返却commitの読戻しを実施する。R02の `previous_receipt_ref`、artifact、内容SHA、保存/読戻し時刻を一致確認する。R01など過去の固定証跡や推奨本体JSONへの変更は引き続き禁止。 `incident_record()` で生成した障害JSONはrace ID・開催日・branchを保持し、`persistence-incidents/YYYY-MM-DD/` へ復旧後（発走後を含む）に新規保存・読戻し可能。ただし事故記録の保全は発走前保存、receipt認証、KPI適格を代替しない。

時計判定・保存成功・読戻し一致・宣言/FIX順序・個別完了・正式KPIは独立した項目として表示する。現在の時計が発走後というだけで、過去の固定commitによる発走前保存を遅延へ書換えない。実チャット/予約/再開の経路試験は合成CIと別に記録する。安全性拒否の内部理由はログ未取得につき未確定のまま扱う。
