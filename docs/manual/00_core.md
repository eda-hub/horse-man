---
module: core
manual_release: v1.7.0
manifest: docs/manual/README.md
depends_on:
  []
produces:
  - execution_mode
  - production_shadow_boundary
  - baseline_forecast_id_contract
  - standard_flow
must_not_modify:
  - market_based_reranking
  - shadow_to_production_backflow
---

# 00_core — v1.7.0共通実行契約

## 0.0 正式入口・有効化

正式予想は `main` のREADMEから開始し、全Ownerを同じmanual参照commitで読む。v1.7.0はPR79のmainマージ後に有効となる。未マージbranch・候補文書を正式運用に使わない。第4サイクルは10/17・18・24・25（東京・京都・新潟）と10/31・11/1（東京・京都）のJRA。実行日でなく対象レースの開催日で所属を決める。

### 0.0.0 ProductionとShadowの決定権

正式ルールの事実→評価→確率→順位を守る。Shadow・過去集団傾向・価格・人気は同一レースのProductionへ逆流させない。基礎能力、近走内容、相手レベル、成長、適性、複数シナリオの骨格は維持する。

標準順は `事実収集→10_predictionの評価/確率/順位/印→20_conditionalの該当直接情報→Production固定→30_bettingの価格不要推奨固定→該当Shadow固定→結果照合→50_review`。各推奨は固定Predictionを親とし、予想と独立保存する。

### 0.0.1 依頼の実行モード

単一事前予想、開催全体選別、選定候補の最終予想、重賞、WIN5、回顧を依頼から解決する。通常の初回・最終・回顧依頼で所属サイクルの該当検証まで実行する。内部IDを利用者へ覚えさせない。明示的な印のみ依頼は推奨のEXPLICIT_MARKS_ONLYとして区分する。

### 0.0.2〜0.0.5 責任範囲と基本用語

Productionは順位、印、全頭勝率/連対率/3着内率、予想確信度、根拠、主要シナリオを作る。Recommendationは券種・具体的組合せ・ユニーク点数・優先順位・理由・失敗条件を作る。実購入意思・金額・購入確認・実購入ROIは新規中核責任から外す。任意市場sidecarを実行しなくても予想・推奨・回顧は完結する。

予想確信度は価格非依存のA/B/C/D。選定優先度は作業順であって能力評価ではない。推奨なしは正常な状態で、予想回顧から除外しない。旧Betting/☆/実購入は当時のreleaseとschemaで読取検査する。新方式へ自動変換せず、発走前証跡を後から作らない。

### 0.0.6〜0.0.8 同一予想と変更統制

同一release・レースの既存 `baseline_forecast_id` と静的入力を再利用する。別チャット・価格更新・単なる再考で作り直さない。取消・重大な状態/馬場変更、強い新事実や複数の独立根拠がある場合だけ、37.1/37.2に従い前後順位/確率/確信度・要素・時刻・強度・理由を新revisionへ固定する。

根拠はfactor/fact/source_ref/observed_at_jst/direction/strengthを持ち、cutoffより未来の情報を使わない。同じ事実・祖先を重複加点しない。取得済みの静的証拠をProduction/Shadowで再利用し、動的情報だけ更新する。

### 0.0.9 日次branchと履歴不変

初回作業時に対象レース開催日の `prediction/YYYY-MM-DD` を使う。同じ開催日の別チャット・翌日回顧も同branchを継続し、mainへ直接書かない。FIX済み本体は独立JSON、同一ID/同bytesの再試行だけ許し異内容は新revisionにする。旧Markdownを改変してhashを一致させない。


## 保存拒否と発走時計の是正（2026-10-17、実装後の新規試行に適用）

正式レースでの発走前保存は次の順序を必須とする。未マージのPR・計画を既存本番で有効と自己申告しない。

1. 対象開催日とrace ID、公式scope、公式発走変更chain、日次branchと作業対象pathを確認する。実際のChatGPT/GitHub連携の権限と利用経路を確認する。未確認なら成功と表現しない。
2. 書込み直前・本体読戻し直後・receipt読戻し直後に、現在UTCを取得して `prediction_clock.py` / `verify_prediction_persistence.py --clock-status --date YYYY-MM-DD --clock-race-id RACE_ID` で判定する。第4運用入口は `cycle04_workflow.py --clock-status --date YYYY-MM-DD --clock-race-id RACE_ID`。JST表示、残秒、根拠、状態を返す。実時計が取れない環境では読取専用の計算値を用意できても、実測と混同せず時刻未判定とする。公式scopeと発走変更chainの読取りが終わった**後**に判定時計を新規取得する。取得前の時計を読取り後まで流用しない。時計が5秒超古い、オフセット/秒精度がない、monotonicとの乖離が2秒超、境界不明なら未判定。予定到達は実発走確認済みではない。
3. 正式intentは分析前にGit保存・固定commitから同一bytes読戻しする。FIX独立manifest→本体→receipt→個別検査の順序を守る。自己申告のreadback、ローカル保存、Actions成功だけで正式完了にしない。
4. 固定bytesとSHA-256を保持し、障害を `prediction_persistence_io.py` の拒否分類・操作記録に残す。権限/branch制約、SHA競合、通信/timeout、CI失敗、安全性拒否、理由不明を分ける。拒否された操作を別経路や高権限で迂回しない。通信系のみ、同一原本の遠隔読取り後に最大2回まで許可済みの保存を再試行する。独立した許可済み経路がなければ切替不可と明記する。
5. 実行環境にPythonと承認済みGitHub Contents API認証情報がある場合は、`python3 scripts/prediction_persistence_io.py --date YYYY-MM-DD --race-id RACE_ID --path RELATIVE_PATH --payload-file FIXED_FILE --operation-id UNIQUE_ID --write` を使用できる。同一bytesの既存原本はcommit固定で読戻し、再書込みせず存在確認済みとして扱う。固定原本と異なる内容は `--allow-update` を指定しても上書きせず、新しいrevision/pathで独立保存する。トークンや権限の自動取得・branch自動作成はしない。ChatGPTのGitHub連携利用時は同等の書込→返却commit固定読戻しを連携ツールで実行し、Pythonアダプター成功と取り違えない。
6. 失敗時は固定原本と秘匿済み障害記録を実行環境に保全し、GitHub正式保存は未完了と表示する。branch初期確認段階の拒否（HTTP 403等）でも `--local-incident` へ要求ID・応答分類・API到達状態を保存する。ローカルログ保存失敗も別途表示する。機密文字列を公開リポジトリに記録しない。事故記録の正式保存先は `docs/validation/persistence-incidents/YYYY-MM-DD/` だが、これは当時のreceiptを代替しない。旧データ・過去の証跡を遡及補完しない。

時計判定・保存成功・読戻し一致・宣言/FIX順序・個別完了・正式KPIは独立した項目として表示する。現在の時計が発走後というだけで、過去の固定commitによる発走前保存を遅延へ書換えない。実チャット/予約/再開の経路試験は合成CIと別に記録する。安全性拒否の内部理由はログ未取得につき未確定のまま扱う。

### 0.0.10 保存・締切・失敗時の継続

予想開始前にrace scope、保存ID/path、実発走予定、推奨scopeを事前宣言し、Git保存・読戻しする。FIX前hashを独立manifestとしてGit保存・読戻しした後、同じbytesの本体とreceiptを保存・読戻す。宣言→FIX証跡→本体→receiptは同一artifactと時刻を照合する。

本体保存、receipt、FIX hash、個別完了、gate、該当Shadowを独立検査する。全体audit成功を個別完了へ代用しない。保存未試行・失敗・読戻し不一致・個別未実施・完了を日本語で示す。Shadow未完了はその比較KPIを保留し、Production本体の保存成功を失敗へ置換しない。

発走時刻を確認し、公式優先、締切内の代替取得、最大2回の同bytes再保存を行う。取得障害やchecker不合格でも依頼された予想の提示を発走まで無限に待たせない。失敗を完了としない。発走後保全はLATE_PERSIST/REPLAYとして保存し、前向き適格にしない。

### 0.0.11 全頭の必要入力

当日最終では馬体重/増減、馬場、取消・騎手・斤量等を取得試行する。馬体重はJRA公式→スポーツナビ→信頼できる代替の順を継承し、静的HTML空欄だけで未発表と断定しない。出所/観測/取得/読戻し時刻、対象頭数/取得頭数、未取得と理由を保持する。前走・調教後の馬体重を当日値へ代用しない。

近5走・古馬対戦経験・クラス・相手格は直接実走と時点を確認する。未取得を0へ変換せず、入力不足の影響を予想確信度・不確実性へ反映する。新しい一律年齢減点や未知値の補完は行わない。

### 0.0.12 第4サイクルの3段階契約

初回scope、選定scope、最終scope、回顧scopeを別集合で固定する。初回全件の基準と候補/未取得を保存する。最終は選定候補のみを対象とし、候補追加・用途変更・取消は発走前revisionと理由を残す。回顧は初回全件を対象とし未最終/推奨なしも除外しない。

用途はPREDICTION/VALIDATION_ONLY/RECOMMENDATION/MARKET_SIDECARを分離する。Recommendationの採否と利用者の実購入を混ぜない。運用の唯一の保存手順は `docs/validation/contracts/cycle04_operations.md`、標準実行入口は `scripts/cycle04_workflow.py`。

## 0.18 共通出力

レース/開催日/実発走予定、manual_releaseと参照commit、baseline ID、cutoff、全頭順位/確率/根拠、印、予想確信度、入力充足と不足理由、最終候補、推奨状態/組合せ/点数/理由、各対象の保存状態を提示・固定する。短い出力指定でも内部の全頭取得・scope照合を省略しない。

## 1〜2 分析原則

事実・解釈・予測を分け、結果に都合のよい説明へ遡及変更しない。個別の予想判断は10_prediction、補正は20_conditional、推奨は30_betting、比較は40_shadow、採否は50_reviewが唯一のOwner。
