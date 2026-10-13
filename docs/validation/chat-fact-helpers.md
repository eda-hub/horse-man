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
