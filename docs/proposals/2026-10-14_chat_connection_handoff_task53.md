# 53番：チャット方式の接続不足と後続実装タスク

## 適用範囲

2026-10-14の利用者指示「53を実施しろ」に対する棚卸し・引継ぎ。最新の番号付き計画のチャット方式への変更を優先する。正式予想はmainのv1.7.0、未マージPR69の差分を正式Productionへ代用しない。

今回の完成範囲は53-01〜05の棚卸し、入力・依存・Owner・受入条件・小タスクの登録。以下14項目の実装を完了したものではない。実装の着手前に対象タスクと依存を確認し、既存Phaseごとの独立PR契約を維持する。新規PR・アプリ・サーバーを今回作らない。

Windows/JRA-VAN/DB唯一Writer・常駐Scheduler・WebUI/hosting・外部AI Adapterは現構成の適用外。旧Phase設計はGit履歴・既存文書として保持し、チャット予想の必須依存へしない。Git JSON writer、日次branch、原子的台帳writerと独立receiptを再利用する。

## 5領域の確認結果

| 子タスク | 現在の再利用範囲 | 不足と引継ぎ |
|---|---|---|
| 53-01 取得/保存 | Registry/本文保存、構造化全頭入力validator、Git保存/読戻し | 非価格本文の共通記録・入力変換・出所対応をI01〜03へ。DB移行は対象外 |
| 53-02 予想/推奨 | 非価格Prediction、独立FIX/receipt、7券種推奨、個別gate、日別writer | 既存参照の組立て・読取再開表示をI04〜05へ。独立engineの新設や確率生成モデルは対象外 |
| 53-03 結果/回顧 | 公式全頭結果validator、推奨的中再計算、初回全scope回顧・履歴保全 | 公開本文変換・出所再照合・明示訂正sidecarをI06〜08へ |
| 53-04 前向き検証 | 37番の同時点ペア/Brier/捕捉/差、層別集計、指定4日計画 | 全該当対象との集合照合・Owner審査資料をI09〜10へ。実測/校正/非劣化はOPEN |
| 53-05 任意市場/AI支援 | 29番の取得/正規化/保存接続、Phase5/7の独立境界 | 既存29実測と新補助の独立性回帰をI11〜12、非UI回顧資料/改善候補をI13〜14へ |

## 小タスク一覧

各項目の実装状態は「未着手」。I11だけは既存29番の実測待ちを同一の残件として参照し、二重の取得・試験を要求しない。新規補助のschemaやコマンド名は設計案であり、正式契約へ追加済みと扱わない。

### 53-I01：非価格情報の取得要求・取得本文の記録

- 所属：Phase 2。Owner：00_core / 10_prediction / 入力取得。
- 依存：独立。
- 入力：依頼の公式scope・馬番集合・cutoff・必要項目、実閲覧URL/本文/時刻/取得状態。
- 不足の根拠：market専用本文記録は存在するが、非価格情報の共通取得記録入口は確認したscriptsにない。
- 再利用：`scripts/chat_market_acquisition.py`、`docs/validation/contracts/cycle04_operations.md`。
- 受入：閲覧本文とHTTP原bytesを区別し、本文hash/実閲覧時刻/掲載時刻/出所/試行理由を保持。失敗・未試行・時刻不明を成功へ変換しない。上流転載を独立証拠へ数えない。
- 待ち条件・保護：提供元ごとの実ページ構造は実取得時に確認。未知の成功本文を合成して公式取得成功としない。

### 53-I02：確認済み非価格本文から全頭入力への変換

- 所属：Phase 2。Owner：10_prediction / 入力取得。
- 依存：53-I01（すべて成立後）。
- 入力：取得記録・確認済み馬体重/近走/相手レベル・馬番集合。
- 不足の根拠：validate_inputsは構造化JSONを検査するが、非価格の公開本文をrace-input-coverage-v1へ変換する共通入口はない。
- 再利用：`scripts/cycle04_operations.py`。
- 受入：既存race-input-coverage-v1へ全馬行を生成。馬体重/近5走/相手レベル、初出走、取消、公式失敗後fallbackを区別。本文にない値を0/取得済みへ補完せず、未来/重複/別race/時点逆順を拒否。既存validatorを通す。
- 待ち条件・保護：クラス序列・相手強度の独自基準を作らず、Ownerと出所付きの既存事実のみ使用。

### 53-I03：取得記録と入力artifactの出所対応を検査

- 所属：Phase 2。Owner：00_core / 入力保存。
- 依存：53-I01・53-I02（すべて成立後）。
- 入力：本文原本/変換入力/hash/同一artifact receipt・項目別参照。
- 不足の根拠：入力JSONのhash・receiptは検査されるが、各取得値が保存本文のどの箇所から来たかを一般的に再照合する接続は未受入。
- 再利用：`scripts/cycle04_operations.py`、`scripts/verify_prediction_persistence.py`。
- 受入：項目ごとの本文参照・確認済み抽出を対応付け、原本改変/出所差替え/入力混入を拒否。静的資料を再利用し動的情報のみ更新。JSON保存成功とGit読戻し成功を区別。
- 待ち条件・保護：新しい支持資料は独立sidecarに限定し、正式Predictionのschema/必須入力を無言で拡張しない。

### 53-I04：固定予想・推奨の既存入口へ渡す参照の組立て

- 所属：Phase 3。Owner：00_core / 30_betting / 保存CLI。
- 依存：53-I03（すべて成立後）。
- 入力：既存基準・全頭評価・入力参照・宣言/FIX/本体/receipt/gate・選定履歴。
- 不足の根拠：保存・推奨・record_predictionは接続済み。利用者確認済み参照からentryを組み立てる補助入口の不足を局所化。
- 再利用：`scripts/seal_prediction.py`、`scripts/recommendation.py`、`scripts/cycle04_workflow.py`、`scripts/task_completion.py`。
- 受入：既存entry/operations形式へ参照を組み立て、既存validatorで同一race/cutoff/基準/hashを確認。価格/実購入なしで推奨まで接続。基準を再生成せず順位/確率を独自算定しない。declared scopeと旧履歴を保持。
- 待ち条件・保護：Git書込み/読戻しは従来API工程。将来engine/DBは現構成の前提にしない。

### 53-I05：保存途中からの再開点を読取表示

- 所属：Phase 3。Owner：00_core / 個別完了。
- 依存：53-I04（すべて成立後）。
- 入力：既存artifact/receipt/gate/FIX/選定revisionと実保存結果。
- 不足の根拠：個別不足表示は存在。再開に必要な固定参照と次の未完了工程を一括提示する補助を具体化。
- 再利用：`scripts/task_completion.py`、`scripts/persistence_status.py`、`scripts/verify_prediction_persistence.py`。
- 受入：完了工程を再実行せず、同一bytes/hashの再試行・不一致・期限超過・別branchを区別。現在の未確認状態だけを表示し、当時の保存/receipt時刻を生成しない。取得済みmainと未マージbranchを混同しない。
- 待ち条件・保護：独立した常駐タスク/自動予想/予約を新設しない。

### 53-I06：公式結果本文を既存結果JSONへ変換

- 所属：Phase 6。Owner：50_review / 結果取得。
- 依存：53-I01（すべて成立後）。
- 入力：同一race/dateの公式全出走結果本文・取得時刻・URL・固定馬番集合。
- 不足の根拠：validate_official_result/settle/reviewは構造化結果を処理するが、現在の公開本文からfinish_groupsへ変換する共通入口は未受入。
- 再利用：`scripts/cycle04_operations.py`、`scripts/recommendation.py`、`scripts/cycle04_workflow.py`。
- 受入：全着順・同着group・取消/除外・非完走を正規化し、本文/構造化結果hashを分離。馬名への装具文字混入・部分結果・別race/date・結果前取得を拒否し、既存全頭validatorを通す。
- 待ち条件・保護：公式原HTMLが取れないときは既存の公式取得本文保存契約を使い、HTTP原bytes hashを捏造しない。

### 53-I07：公式結果の本文・構造化値・固定原本を再照合

- 所属：Phase 6。Owner：50_review / 結果監査。
- 依存：53-I06・53-I04（すべて成立後）。
- 入力：結果本文/抽出記録/結果JSON・Prediction/推奨固定参照。
- 不足の根拠：現在の結果validatorは出所URL・race/date・全頭集合を照合するが、保存本文からの着順再構成と一致検査の汎用入口は未受入。
- 再利用：`scripts/cycle04_operations.py`、`scripts/recommendation.py`、`scripts/cycle04_workflow.py`。
- 受入：race/date/全頭着順/取消/同着を本文と再照合し、改変・未確定・訂正待ちを理由付き保留。払戻なしで推奨的中を再計算。初回scope全件・推奨なし・未最終を回顧対象に保持。
- 待ち条件・保護：過去の結果や固定予想を再作成しない。原票真正性は取得形式の限界を明示。

### 53-I08：公式結果訂正を別履歴として記録・比較

- 所属：Phase 6。Owner：50_review / 訂正履歴。
- 依存：53-I07（すべて成立後）。
- 入力：元result_ref/回顧・公式訂正の出所/取得時刻・新結果hash・訂正理由。
- 不足の根拠：reviewは回顧済み改変を拒否しexplicit correction historyを要求するが、その追加履歴の専用入口は未受入。
- 再利用：`scripts/cycle04_workflow.py`。
- 受入：旧結果・旧回顧・旧集計を保持して訂正sidecarを追記し、旧新の差分を表示。単純な台帳上書きを拒否。訂正のKPI採用はOwner審査前に自動変更しない。
- 待ち条件・保護：正式訂正がない実レースへ訂正履歴を作らない。新契約変更が必要ならOwner審査と独立PRへ分離。

### 53-I09：前向き比較の対象網羅を照合

- 所属：Phase 8。Owner：40_shadow / 50_review。
- 依存：53-I07（すべて成立後）。
- 入力：実依頼初回scope・事前assessment・該当/非該当/未確認・提出pair一覧・公式結果。
- 不足の根拠：class_transition_shadow.collectionは提出ペアを照合するがsample_coverage_verified=false/trial_complete=falseを保持。全該当対象との集合照合は未受入。
- 再利用：`scripts/class_transition_shadow.py`、`docs/validation/class-transition/forward-plan.json`、`scripts/cycle04_workflow.py`。
- 受入：指定10/17・18・24・25の実依頼全該当例で対象/提出/欠測/非該当を集合照合。重複・選択的除外・未確認を非該当化する入力を拒否。合成/REPLAYは実測母数外。網羅成功でも非劣化/性能昇格を認証しない。
- 待ち条件・保護：開催日前にダミーscope・実測0・事前証跡を生成しない。37-05を重複した別試験へ作り直さない。

### 53-I10：校正・非劣化審査用の入力を読取出力

- 所属：Phase 8。Owner：10_prediction / 40_shadow / 50_review。
- 依存：53-I09（すべて成立後）。
- 入力：網羅確認済み前向きペア・固定確率・公式結果・層別条件・不足。
- 不足の根拠：Brier/捕捉/改善・中立・悪化は算定済みだが、実確率/条件別校正・非劣化受入は未実測。審査資料の接続を分離。
- 再利用：`scripts/class_transition_shadow.py`、`scripts/cycle04_workflow.py`、`scripts/probability_presentation.py`、`scripts/dependency_risk.py`。
- 受入：同一cutoff/基準/条件/対象集合でBrier・捕捉・点数/依存の入力を出力。旧KPI/任意市場ROIを混入せず、0母数はnull。新共通閾値・校正済み下限を創作せず、採否は既存50_reviewの別審査。
- 待ち条件・保護：30〜37の実確率/校正/性能と37-05は実データ待ち。独自モデル・数値補正の実装は本タスクの対象外。

### 53-I11：既存29番の発走前取得・2開催受入を実行

- 所属：Phase 5。Owner：60_market / 取得。
- 依存：独立。
- 入力：実開催の公式scope・固定予想/推奨・対象券・締切・実本文/receipt。
- 不足の根拠：チャット取得/8券種正規化/保存接続/checkerは実装済み。発走前8券種・独立提供元・2開催の真正な実測が未受入。
- 再利用：`scripts/chat_market_acquisition.py`、`scripts/check_chat_market_live_validation.py`、`docs/validation/market-chat-acquisition.md`。
- 受入：既存29-C03/C06/C07/C08を同一証跡で受入。実前向き8券種・2提供元・2開催、当時Git/独立receiptを照合。市場未完了でも価格不要Prediction/推奨を完結。
- 待ち条件・保護：開催・公開本文取得可否待ち。JRA本文正規化は実本文確認前は未対応。新しい実測日/対象数を勝手に確定しない。

### 53-I12：入力取得補助と任意市場の独立性を接続検査

- 所属：Phase 5。Owner：60_market / 00_core。
- 依存：53-I03・53-I04（すべて成立後）。
- 入力：同一固定Prediction/推奨・任意市場の各取得状態。
- 不足の根拠：既存市場の独立性は受入済み。新規の非価格取得/参照組立て補助を追加した後の接続回帰だけを登録。
- 再利用：`scripts/market_sidecar.py`、`scripts/cycle04_workflow.py`、`scripts/chat_market_acquisition.py`。
- 受入：未依頼/未試行/失敗/締切/取得済みの全状態で固定Prediction/推奨bytes・KPIを保全。市場cutoffを独立保持し、取得本文保存と正式登録を分離。
- 待ち条件・保護：市場取得・校正を取得/予想補助の必須条件へしない。

### 53-I13：非UIの回顧資料を固定参照から生成

- 所属：Phase 7。Owner：50_review / 回顧支援。
- 依存：53-I07（すべて成立後）。
- 入力：固定原本・公式結果・独立KPI・不足・誤差分類・正常部分/次検証。
- 不足の根拠：Phase7は非UIへ整合済み。最小Review Packageの専用生成入口は確認したscriptsにない。
- 再利用：`scripts/cycle04_workflow.py`、`docs/jravan/phases/phase_7_ai_review.md`。
- 受入：初回scope全件・未最終/推奨なしを保持し、hash/race/date/cutoff/baselineを対応付けた読取資料を生成。旧実購入は歴史診断に分離。AI API・UI・DB接続を要求しない。
- 待ち条件・保護：ChatGPTによる現行回顧を外部AI Adapterの稼働証明としない。

### 53-I14：改善候補の不足・Owner・次試験を引継ぐ

- 所属：Phase 7。Owner：50_review / 改善候補。
- 依存：53-I13・53-I10（すべて成立後）。
- 入力：回顧資料・改善候補・根拠/不足/保護対象・既存採否。
- 不足の根拠：既存47番採否は保存済み。今後のチャット候補を一意な固定参照から構造化して引き継ぐ補助入口を具体化。
- 再利用：`docs/jravan/phases/phase_7_ai_review.md`、`docs/manual/50_review.md`。
- 受入：採用候補/継続検証/棄却/判断保留、Owner・根拠・次試験を保持。AIがmanual/固定原本/DBへ直接反映せず、人間承認/非劣化/別PRを迂回しない。
- 待ち条件・保護：53は候補仕様/棚卸しのみ。未知のrule/model/閾値を自動採用しない。

## 実施順と待ち条件

最初の独立入口は53-I01。I01→I02→I03→I04→I05を保存・入力接続として進める。結果接続はI01→I06、I04/I06→I07→I08。前向き検証はI07→I09→I10。I11は既存29の開催待ちとして独立に継続し、I03/I04→I12の接続回帰を価格不要フローの条件にしない。回顧資料はI07→I13、I10/I13→I14。

実ページの未知の本文構造、公式訂正、校正方法や数値基準は推測しない。取得不能なら理由付き不足。校正モデル/閾値/正式schema変更など未確定判断が実装の条件となった時点で利用者へ内容・影響を提示して確認する。未確定事項をコードで暗黙決定しない。

## 継続残件と受入境界

- 12日研究は公式結果1/24R・本人/5代2頭・未確認13頭・5/43条件のPARTIAL。I01〜14をこれらの研究補完完了へ代用しない。
- 歴史的保存不足40件・未確認解釈・旧KPI保留57件・正式ROI nullを保持。過去宣言/FIX/receiptを後付けしない。
- 29番の発走前8券種/独立提供元/2開催、37-05の10/17・18・24・25の実依頼全該当例は実測待ち。既存期間・対象を変更せず、実測0/ダミーscopeを作らない。
- 実確率・校正・枠連推奨生成・集中/二頭軸/各比較の性能は未受入。構造検査・コード存在・合成CIで昇格しない。
- mainの66入力は正式開始可能、PR69の134入力は原子整合と未マージ拒否を区別する。PR69のマージ/正式切替/rollbackは今回実行しない。

判定の証拠はPR69の`docs/validation/implementation/2026-10-14-task53.json`。計画正本は本ファイルを含むPR68。取得本文/HTTP原bytesと構造化入力、実取得/合成、保存/読戻し、引継ぎ/実装完了を常に分離する。
