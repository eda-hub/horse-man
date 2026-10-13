# チャット取得本文の補助入口

## 非価格取得本文の保存

`chat_fact_capture.py`はチャットで実際に閲覧した本文を受け取る補助で、Webサイトを自動取得しない。新規sidecarでありPrediction/Recommendationの正式schemaを変更しない。

```bash
python3 scripts/chat_fact_capture.py --root . --request request.json --captures captures.json \
  --output docs/validation/fact-captures/YYYY-MM-DD/capture-id.json
```

requestは`schema_version=chat-fact-request-v1`、`request_id`、`race_id`、`race_date_jst`、JSTの`scheduled_post_time_jst`、`data_cutoff`、`purpose=INPUT/RESULT`、全馬の`horse_numbers`、`required_items`を持つ。INPUTのcutoffは発走前、RESULTは発走以後。

capturesは配列。各行は一意の`capture_id`、HTTPS `source_url`、`provider=OFFICIAL/FALLBACK`、上流を識別する`origin_group`、`mode=FORWARD/REPLAY/SYNTHETIC`、`retrieval_kind=PAGE_TEXT/SEARCH_SNIPPET/ERROR/NOT_ATTEMPTED/SYNTHETIC_PAGE_TEXT`、実閲覧の`read_started_at_jst/read_finished_at_jst`、掲載の`source_updated_at_jst`（不明ならnull）、`text`、`reason`を持つ。OFFICIALはJRAドメインを要求するが、URLの構造検査だけで取得元の真正性を認証しない。

NOT_ATTEMPTEDは本文と閲覧時刻なし、ERRORは本文なし。成功本文は128KiBまで。実際に取得していないHTTP原bytes hash/statusはnull。出所時刻不明・検索抜粋・Replay・合成は利用可能な前向き事実へ変換しない。転載元が同一ならorigin_groupを共有し、URL数で独立証拠数を増やさない。

`usable_as_observed_fact`は提出本文の形式・時点・状態の検査結果で、公式取得の真正性、個別保存、前向きKPIの認証ではない。本文値の変換/根拠照合も別工程。`formal_kpi_certified/git_persistence_verified`はfalseを保持する。

書込みは対象日のprediction branchだけ。writerロック、一時本文のfsync/読戻し、原子的な非上書き保存を使う。既存artifactへの再試行は全bytes一致だけを許し、内容・記録時刻が変わるときは新revisionへ保存する。CLIのローカル読戻し後、従来どおりGitHubへ保存・読戻しし、同一artifactのreceiptを別に確認する。過去・将来の宣言/receiptを生成しない。

合成テストは実レースの取得実績へ算入しない。未知の提供元本文を自動解釈せず、本文と値の出所は後続の明示変換で照合する。

## 確認済み注釈から全頭入力への変換

`chat_fact_input.py --capture 本文sidecar.json --annotations 注釈.json --readback-at 実読戻し時刻`で既存`race-input-coverage-v1`へ変換する。注釈JSONはbody_weight/recent_five_runsの全馬行を持つ。取得済み行は既存value/status/reason等に`quotations`の配列を付ける。各引用はcapture_id/start/end/quote（文字単位、endは排他）を持ち、保存本文との完全一致が必要。未取得は理由付きMISSING/null、初出走は既存の出所と0過去走の条件を満たすNOT_APPLICABLEとする。

provider/URL/観測・取得時刻は保存本文から導出し、読戻し時刻は実際の値を渡す。近5走・相手格の構造と未来値、全馬集合、fallback時の公式失敗理由は既存validatorで検査する。出力はinput、bindings、coverageを持つ独立変換sidecarで、値の意味と引用の対応を認証したものではない。semantic_extraction_verified/formal_kpi_certifiedはfalse。後続の根拠照合・独立artifact/receiptと個別gateを省略しない。

## 本文値と独立保存の照合

`chat_fact_provenance.py --capture-ref 本文参照.json --conversion-ref 変換参照.json --post 発走予定`は、同一artifactのhash・発走前receipt・保存順序/cutoffと、引用・入力値・馬番号・coverageを読取照合する。参照JSONは既存verified_artifact形式。

引用は1馬の1行を対象にし、馬番号と数値/文字列の一致を必要とする。他馬の行を連結して値を取得できない。馬体重は整数の境界を照合する。近走はquoteにvalue_pointer（value内のJSON Pointer、例`/0/class`）を付け、各走の日付/クラス/取得済み相手格を網羅する。日付や値が引用本文にそのまま存在しない表示形式は本補助では未対応として保持し、暗黙の変換や相手強度の創作をしない。初出走は馬番号と「初出走」の明示引用を必要とする。

出力のextraction_consistency_verifiedは提出引用・値・保存証跡の整合だけ。origin_authenticity_certified/formal_kpi_certifiedはfalse。取得元が実際にその内容を公開したこと、提供元独立性、正式Prediction/推奨の適格性はこの照合だけでは認証しない。入力完備/不足は既存coverageをそのまま表示する。

## 固定参照の組立て・台帳プレビュー

`chat_entry_assembly.py --entry entry.json --capture-ref 本文参照.json --conversion-ref 変換参照.json`で、既存の固定gateとoperationsの参照を検査する。operationsの全頭入力参照は現契約の`inputs_ref`。独立保存した通常のrace-input-coverage-v1本体が、根拠照合済み変換のinputと一致することを要求する。引用変換sidecarそのものを通常入力本体へ代用しない。

既存の公式scope・選定履歴・固定Prediction/推奨・宣言/FIX/receiptを再利用し、実台帳writerと同じ全日validatorでINITIAL/FINALの順序・revision・hash・入力不足・任意市場境界までプレビューする。candidate_dayは検査用の候補で、既存台帳・固定予想・推奨を上書きしない。プレビュー成功はGit保存や正式KPI認証ではない。確認したentryを既存cycle04_workflowの対象日branchで保存し、従来のGit読戻しを別に実施する。

## 保存途中からの読取再開表示

`chat_resume.py --request 再開参照.json`は既存個別完了checkerの不足から次の確認だけを日本語表示する。`--json`は監査用。requestはschema_version=chat-resume-request-v1、date、snapshot_id、phase=INITIAL/FINAL、scheduled_post_time_jst、prediction_gate_path、任意のintent_id/artifact_pathを持つ。FIX hashは当時記録したfixed_content_sha256か、発走前独立receipt付きfix_refを渡す。現在の本体から期待hashを新しく算出しない。

FINALの推奨はrecommendation_artifact_path/recommendation_gate_path/recommendation_fix_hashで別確認する。予想側Shadowの不足を推奨へ転用せず、未確認推奨を対象外にしない。既存日別台帳への同一参照も確認する。保存済み本体・構造上の個別完了と、現時点で確認可能な保存時刻を分け、未来/時刻不明receiptを現在の完了へ使わない。

発走後は発走前の再保存を提案せず、読取による不足確認を継続する。本入口は書込み・自動再試行・開始認証・Git読戻しを行わない。保存・読戻し・個別完了・main開始は独立工程のまま保持する。

## 公式結果本文の正規化

`chat_result_conversion.py --capture 本文sidecar.json --annotations 結果注釈.json`は既存結果JSONへ全馬を正規化する。RESULT要求の発走後閲覧本文から、確認引用、各馬のfinish_position/statusと引用、place_basisを渡す。各引用はcapture_id/start/end/quote。着順は「N着」、馬番号は「N番」の字面を照合する限定入口で、未知の表示形式を推測しない。

同着の次の着順、取消/除外、競走中止/失格を区別し、全頭不足・重複・未確定・馬名/装具アイコンの注釈混入を拒否する。馬名は結果schemaへ転記しない。結果の掲載更新時刻が不明でも、公式確認引用と実際の発走後閲覧時刻は照合し、publication_time_unknownを保持する。発走前入力の時刻不明を取得済みへ変換するものではない。

place_basisはOFFICIAL_PLACE_PLACES（公式本文の複勝対象着数）かOFFICIAL_SALES_START_COUNT（公式の発売開始時頭数）。kind/value/quotationを持つ。JRAの[馬券の種類](https://www.jra.go.jp/kouza/beginner/baken/)で発売開始時5頭以上・7頭以下では2着までの規則を確認した。取消後の実出走頭数を発売開始時頭数へ代用しない。根拠不明・不発売など現契約で扱えない状態は推測補完せず照合不合格とする。

FORWARD/REPLAY/SYNTHETICの区分を結果sidecarへ引き継ぎ、合成/Replayを前向き結果へ認証しない。HTTP原bytesや取得元真正性、正式KPIは本補助で認証しない。result本体の保存・Git読戻しと、固定Prediction/推奨との対応は次工程。

保存済みJRA本文のパイプ表は着順・枠・馬番の列を分離し、画像リンク番号やブリンカー表示を馬番へ流用しない。10/12保存原票の15行をREPLAY形式回帰で照合する。保存断片に確定/複勝根拠がなければ単独では全結果へ昇格しない。
