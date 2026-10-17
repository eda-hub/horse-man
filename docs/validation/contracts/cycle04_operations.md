# 第4サイクル v1.7.0 実運用契約

## クラス移行Shadowの固定3条件と前向き試験

比較原本の`comparison_method_id`は試験計画の`class-transition-evidence-v1`と一致させ、`change_reason`に変更/据置の根拠を保存する。試験途中で異なる比較方法を混ぜない。共通入力と基準の読戻し→入力binding保存/読戻し→比較保存の順を照合し、基準読戻し前のbindingを拒否する。その他の共通事実は`other_facts`の根拠行（horse_no/factor/fact/source_ref/observed_at_jst/direction/strength）で保持し、cutoff後の情報を拒否する。

第37項の準備用読取入口は`scripts/class_transition_shadow.py`。`python3 scripts/class_transition_shadow.py docs/validation/class-transition/fixed-cases.json`で、年齢限定重賞→古馬OP、混合クラス移行、既対戦/入力不足の最大3固定例を照合する。保存した3例は明示的なSYNTHETICで、実馬・過去予想の復元・前向き性能ではない。REPLAYも前向きKPI外。10/12の旧回顧/snapshotにある部分比較と不適格を、真正な新比較ペアへ代用しない。37-01〜03の固定条件のコード検査と、実例での効果検証は分離する。

利用者は2026-10-14に前向き試験を10/17・18・24・25・31・11/1の該当全例へ延長した。10/17・18・24・25は東京/京都/新潟、10/31・11/1は東京/京都の実際に依頼・保存された対象から収集し、件数は実該当数を記録する。件数上限や新たな一律受入閾値を作らない。`docs/validation/class-transition/forward-plan.json`は試験方針で、未来の予想/台帳/実測0ではない。37-04の期間/対象・Owner・必要入力・判定方法は固定、37-05の将来実測は開催前につきOPEN。

前向きの読取manifestは`{"plan": <forward-plan.jsonの内容>, "items": [{"gate_path": "保存済みPrediction gateの相対path", "shadow_item_id": "該当ShadowのID", "result_path": "公式結果JSONの相対path"}]}`。`python3 scripts/class_transition_shadow.py MANIFEST.json --root REPO`で検査する。対象日のFORWARD、Production/Shadow双方のELIGIBLE、独立した発走前原本・hash・receiptを既存gate/verified_artifactで確認する。

Shadow原本は`class-transition-shadow-pair-v1`で、race_id/race_date_jst/data_cutoff/scheduled_post_time_jst/mode、baseline_forecast_id、baseline_prediction_sha256、baseline/shadow、assessment、common_input_ref/common_input_sha256、baseline_input_binding_refを持つ。baseline/shadowは同一cutoff・共通入力hash・全頭ranking/probabilitiesを持つ。基準値は検証済みProductionと完全一致させ、全頭集合と確率総和1/2/3を照合する。assessmentは36番の同一レース・馬・cutoffの入力。

共通入力原本は`class-transition-common-input-v1`のrace_id/data_cutoff/assessmentsと、両予想が使ったその他の共通事実を持つ。基準入力bindingは`class-transition-input-binding-v1`のrace_id/data_cutoff/baseline_prediction_sha256/common_input_sha256。共通入力・binding・Shadow原本のすべてを既存独立receiptで発走前に保存/読戻しする。基準の同一入力利用を事後の自己申告だけで適格にしない。標準Prediction schemaや値を書換えず、この比較用bindingを別原本として保持する。

公式全頭結果と対応し、勝率/連対率/3着内率のBrier、◎勝利、上位1/3/6頭の勝馬捕捉、順位変更、基準→比較差を同一ペアで計算する。いずれかのBrier上昇または捕捉悪化があるペアは悪化、悪化なしの改善は改善、差なしは中立。改善した指標だけを選んで採用しない。未知の結果・全頭欠落・未来結果・入力/根拠不足・取消未再固定・同着の未検証境界・重複は理由付き分離。前向き適格ペアは直接/強い代替の構造充足と入力completeを要求する。

平均差は記述診断で、統計的非劣化/校正や性能昇格を自動認証しない。条件別・全該当scopeと未提出/不適格を実day原本へ対応付けてOwnerが終了審査する。期間経過だけでtrial_completeにはならず、sample_coverage_verifiedは終了審査までfalse。データなしは値null/未実測、0適格でも0%の性能にしない。既存50_reviewの複数条件・5例/20例等の目安と良好部分保全を別PRで審査する。37-05、代替手法の効果・校正・前向き非劣化は実測待ちを保持。標準予想/推奨や29番の価格取得をこの試験待ちで止めない。

## 初古馬対戦・昇級の準備用読取監査

`python3 scripts/class_transition.py INPUT.json`で`class-transition-assessment-v1`を照合する。任意の準備用入力で、既存Production/推奨の必須入力や正式schemaを変更しない。出力は比較材料の不足・時点・整合の確認であり、能力点/確率/年齢減点を生成しない。第37項の比較へ引き継ぐ準備機能で、前向き性能は未受入。

入力は`race_id`、`horse_no`、`horse_age`、`data_cutoff`、`target`、`prior_start_count`、`older_encounters`、`previous_class`、`class_promotion`、`recent_five_runs`、`comparison_evidence`を持つ。各事実は`status=ACQUIRED/MISSING`、`value`、`reason`を持ち、ACQUIREDは`source_ref`と`observed_at_jst <= acquired_at_jst <= cutoff`を要求する。MISSINGはnullを保持する。

`target`は年齢条件`age_condition=AGE_RESTRICTED/MIXED`、実際の古馬出走`older_horses_present`、クラス`class`、斤量`carried_weight_kg`を別々の事実で持つ。混合戦という出走資格だけで実際の古馬対戦を断定しない。古馬既対戦数を確定するには`coverage=ALL_PRIOR_STARTS`と全過去走数の整合が必要。近5走に古馬がいないことだけから全過去の0を推測しない。3歳初古馬対戦は対象の実古馬出走と0/正数/不明から判定し、昇級true/false/不明は前走/対象クラスと別に保持する。クラス名の文字列から序列や昇級を推測しない。

近5走は利用可能な`min(5, prior_start_count)`走を新しい順に保持し、各走の`run_id`、`race_at_jst`、`source_ref`、当時の`horse_age`、年齢条件、古馬対戦の有無、クラス、斤量、相手レベルを照合する。実走時刻・情報観測/取得時刻はcutoff以下で、古いレースの相手の後日成績でもcutoff後の情報を逆輸入しない。確認済み近5走の古馬対戦数が全過去件数より多い矛盾を拒否する。

比較根拠は`evidence_id`、提出区分`kind=DIRECT/STRONG_SUBSTITUTE/REFERENCE`、`source_ref`、`claim`、`limitations`、`evidence_at_jst <= observed_at_jst <= acquired_at_jst <= cutoff`を持つ。対象クラスが一致し、年齢構成・斤量が取得済みで、`comparison_dimensions`がCLASS/AGE_CONTEXT/WEIGHTを網羅する場合に構造上の充足を検査する。直接比較は確認済み実走`run_id`と、その実走のクラス/相手レベル/斤量/年齢構成/古馬対戦を必要とする。対象と同クラス、または出所・時点付き`class_relation=HIGHER`の実走が必要で、古馬相手の対象には実古馬対戦も必要。強い代替は`comparison_method`と比較条件/限界を明記する。3歳・軽斤量・連勝というラベルだけを直接証拠にしない。

出力は直接比較→強い代替→参考→比較不能の順で提出根拠の充足を表示する。前2区分の条件を満たさない提出根拠は参考として残し、根拠なしは比較不能。不足項目と`input_complete`は別表示し、直接比較が1件あることだけで他の欠測を消さない。これは提出根拠の構造・情報時点の照合で、出所の真正性・代替方法の実効性・校正・性能の認証ではない。一律3歳減点やProduction値/順位/印・正式推奨への逆流を行わない。

## 2頭軸の比較候補と取消・欠測

`two_axis_candidates.compare`は固定Productionの3着内率70%以上が2頭以上の場合だけ上位2頭を軸候補にする。70%/30%は試験トリガーで、標準採用条件や校正済み同時率ではない。三連複は取消後の固定順位上位6頭から軸以外のm頭でm点、三連単は取消後の3着内率30%以上の軸以外n頭で6n点。順位・確率・旧原本を変更しない。

FINALの比較には検証済み推奨原本の`cancelled_horses`を渡す。取消馬を除いて固定順位を保ち、次順位を候補として再計算する。実出走馬の確率欠落/null/不正、順位重複、取消対応不正は理由付き`MISSING`とし、欠測を0や非該当へ置換しない。取消馬の確率は候補生成に使用しない。軸条件を満たす馬が2頭未満なら理由付き`NOT_APPLICABLE`。

出力は全候補点で、標準推奨の◎・着順役割の制約を満たす採用点とは別。`selected_points`と`joint_probability`はnull、同時率は`NOT_CALCULATED`、標準採用・性能昇格は`NOT_APPROVED`。結果後の再演を前向きKPIへ昇格させない。

正式版はv1.7.0、有効化はPR79のmainマージ後。価格不要のPrediction→Recommendation→保存→結果/回顧を標準にする。開催日は10/17・18・24・25（東京・京都・新潟）と10/31・11/1（東京・京都）。開始前は実測・性能をnull/未測定とし、予定192Rを未依頼scopeへ補完しない。

## main確認と日別実行

最新mainを取得し、以下の開始確認を通す。`v170-release.json`の全対象hashがローカルと取得済みmainで同じ場合だけ開始できる。候補branchの受入成功だけでは開始しない。

```bash
python3 scripts/run_release_readiness.py --require-main
python3 scripts/check_cycle04.py --require-active
```

予想依頼時に日次branch `prediction/YYYY-MM-DD` を作り、公式出馬情報から依頼範囲を明示する。scope入力は `cycle04-official-scope-v1`、`race_date_jst`、`source_url`、`observed_at_jst`、`races`（`race_id`とJST発走予定）を持つ。登録は発走前に行い、既存日を上書きしない。同日追加依頼は`--extend-scope`で新規レースだけ追記し、既存の対象・発走時刻・予想・回顧を保持する。追加レース自身の締切で確認する。

```bash
python3 scripts/cycle04_workflow.py --register-scope official-scope.json
# 同日の追加依頼時のみ
python3 scripts/cycle04_workflow.py --extend-scope additional-official-scope.json
python3 scripts/cycle04_workflow.py --date YYYY-MM-DD --record-prediction initial-entry.json
python3 scripts/cycle04_workflow.py --date YYYY-MM-DD --select selection-entry.json
python3 scripts/cycle04_workflow.py --date YYYY-MM-DD --record-prediction final-entry.json
python3 scripts/cycle04_workflow.py --date YYYY-MM-DD --review review-entry.json
python3 scripts/cycle04_workflow.py --summary
```

予想entryは`race_id`、`phase=INITIAL/FINAL`、`prediction_gate_path`、`operations`（下記の独立証跡）、`input_complete`、不足理由/影響、`market`を持つ。FINALは`recommendation_gate_path`も必須。selection entryはrace_idとselection_ref。SELECTだけで候補を登録でき、買い目固定を先に要求しない。同じ入口でCANCEL→DESELECTまたは再SELECTの連続履歴を適用する。履歴の巻戻し・分岐は拒否し、最終は最新の選定履歴へ買い目固定イベントを追記した連続履歴も受け取り、独立証跡を照合して保存する。選定後に買い目を作る通常の順序で完了できる。review entryはrace_id、result_path、result_reconciliation_refとv2回顧の状態・Owner必須項目を持つ（末尾のPR88契約を参照）。公式結果はOFFICIAL、同一ID/開催日、source_url、発走後retrieved_at_jst、同着をまとめたfinish_groups、place_placesを持つ。着順・non_finishers・scratched_horsesの和は固定予想の全頭と一致させ、不完全な結果を完了へ算入しない。

日別JSONは`docs/validation/records/cycle_04/YYYY-MM-DD.json`。初回・最終の独立固定参照を履歴として保持する。書込みCLIは対象日の`prediction/YYYY-MM-DD`だけを許可し、main・別日・detachedでは拒否する。writerロックと一時ファイル読戻し→原子的置換で中途半端な台帳を残さない。異常終了後にロックが残る場合はwriterが終了したことを確認してから除去する。

ローカル保存・検査後、従来どおり日次branchへGit保存し、保存先を読戻して同一bytesを確認する。CLI成功だけをGit保存完了とは説明しない。

`run_cycle04_acceptance.py --write`は合成受入を保存する。`check_cycle04.py --require-active --require-complete`は6日の実測・全初回scope回顧が揃ってからのみ成功する。

## 新規予想の保存

1. 日次branchで、対象1R・保存path・期限・必要な推奨scopeを含む事前宣言を予想作成前にGit保存して読戻す。宣言自身の同一artifact/内容hash/保存・receipt読戻し時刻を記録する。
2. 新規予想は `docs/validation/snapshots/YYYY-MM-DD/ID.json` に保存する。本文と版/cutoff/全頭順位・確率・根拠を固定する。既存Markdownはそのまま読む。
3. `seal_prediction.py --root . --draft 草稿.json --artifact-path 本体path --fix-path docs/validation/fix-manifests/YYYY-MM-DD/ID.json --intent-ref 宣言参照.json` でFIX時のbytes hashを独立ファイルへ先に書込む。この段階で本体を書込まない。
4. 独立FIXファイルをGit保存・読戻しし、別artifactとしてhash付きreceiptを記録する。同じコマンドに `--fix-ref FIX参照.json` を加えて本体を書込む。締切後やhash不一致は拒否。異なる内容は新revisionへ保存する。
5. 本体をGit保存・読戻しし、`verify_prediction_persistence.py --date YYYY-MM-DD --snapshot-id ID --intent-id 宣言名 --task-complete --fixed-content-sha256 FIX前hash` と個別 `--completion-status` を実行する。本体/receipt/hash/個別確認/gate/適用Shadowの不足を独立表示する。
6. 保存が失敗しても本文を消さず、未試行・書込失敗・読戻し不一致・本体保存済みで個別未完了を伝える。監査成功を個別完了へ転用しない。

参照JSONは `artifact_id / artifact_path / sha256 / receipt_path / receipt_id` を持つ。receiptは同一ID・path・content_sha256、保存/receipt確認済み、発走前状態、実際の保存・読戻し・発走時刻を持つ。宣言読戻し≦FIX≦独立hash保存≦hash読戻し≦本体保存＜発走を照合する。時刻/receiptを自動生成して発走前保存を装わない。旧記録のFIX hashを事後作成して認証しない。

## v1.7.0の新規FORWARD Shadow原本・適格性

新規のShadowを **ELIGIBLE** とするのは、発走前に別ファイルで固定した独立原本（JSON）について、実際の原本bytes、当時固定したSHA-256、同一receiptの内容hashと保存・読戻し時刻が一致するときだけ。旧v1.6.1のShadow/第三台帳やProductionの共通`evidence`契約には遡及適用しない。

- `shadow_items[*].evidence_ref` に `artifact_id`、`artifact_path`、**当時固定した`sha256`**、`receipt_id`、`receipt_path`、`timing_eligibility: PRE_RACE_ELIGIBLE`、`persist_verified_at_jst` を指定する。ID/hash/時刻は原本の現在値から推測・補完しない。
- `receipt_path` の同一`receipt_id`が一意であり、`artifact_id`、`artifact_path`、`content_sha256` がrefと一致すること。receiptの`artifact_persist_status: PERSIST_VERIFIED`、`receipt_persist_status: RECEIPT_VERIFIED`、`timing_eligibility: PRE_RACE_ELIGIBLE` を確認する。
- `persist_verified_at_jst` がrefとreceiptで同一、かつ **保存確認時刻 ≤ `receipt_verified_at_jst` ＜ gateの`scheduled_post_time_jst`**。receiptの`scheduled_post_time_jst`もgateと一致し、検査実時刻より未来の確認は不適格。比較専用の入力原本・bindingでは既存の`data_cutoff`以前の時刻・保存順の条件も維持する。
- 原本改変、ハッシュ未固定、receipt不在・重複、読み戻し逆転、発走以後の読戻しは、該当Shadowの **ELIGIBLE** 宣言を拒否する。発走後Replay・合成診断を前向きKPIに転用しない。不足時はShadow項目を `PENDING` または `INELIGIBLE` として根拠を残し、Productionの順位・確率・推奨と独立に保存する。
- `scripts/check_prediction_compliance.py` の通常実行、`scripts/task_completion.py` の個別完了、日別記録の照合が同じ新規Shadow検査を利用する。個別完了のShadow不足は項目別エラーとして報告し、保存済みPredictionの本体・receipt・FIX hashを消さない。Shadow対象外のときだけ `NOT_APPLICABLE` とする。

## 用途・入力・市場

`selection-history-v1` の既存revision chainを使う。検証用、正式仮想、実購入に加え、価格不要推奨と任意市場を別用途にする。各イベントは原文JSON/hashと同一artifact receiptを持ち、締切前・連続revision・追加選定・変更/取消の根拠を検査する。履歴内の `BUY` は当該用途の案固定イベントであり、投票実行を意味しない。新規実購入はこの運用では扱わない。用途を移すには新用途のSELECTが必要で、旧案を変えず履歴を残す。

入力JSONは `race-input-coverage-v1`、race_id・cutoff・全出走馬番号を持つ。馬体重と近5走の全頭行を記録し、状態を取得済み/不足/初出走による近走対象外に分ける。取得済みは出所・公式/代替・観測/取得/読戻し時刻を必須とし、cutoff後の入力を拒否する。代替元は公式取得できなかった理由を残す。近5走は利用可能な過去実走数に応じて最大5走、クラス・相手レベルの根拠を記録する。初古馬混合・昇級の事実は元入力から判断し、一律年齢減点を作らない。

入力不足はnullと不足頭数を残す。予想を保全して不確実性・影響を明示できるが、入力完備や正常一巡成功とは表示しない。全頭順位・勝率/連対率/3着内率・根拠を照合し、確率合計1/2/3とscope一致を要求する。入力artifactの読戻しもcutoff以前であることを確認する。

価格は未試行/取得失敗/締切打切り/取得済みと、未評価/正の期待値/取得済み期待値不足を別属性にする。未取得ならodds/期待値はnull、判断は未評価。価格不要の予想・推奨を価格欠測で見送りへ置換しない。市場は任意sidecar、能力順位を変えない。次回の実測2開催以上で再発を確認する。

## 推奨と券種・確率の検査

PR69の価格不要推奨生成・独立保存・結果照合を再利用する。推奨本体の券種生成は既存7券種、枠連を含む8券種の事象比較・欠測検査は `cycle04_operations.py` で別検査する。枠連生成/性能を実装済みとは扱わず、未比較なら理由付きMISSINGにする。

8券種は全行を比較済み/不足/非該当へ分類する。枠連は枠内事象、同枠は異なる実出走2頭を要求。馬単/三連単の順序、取消・未知馬・重複を検査する。同時確率は不足/未校正中心値/裁量縮小/実測校正を分け、未校正値から校正済み下限を宣言できない。構造検査が通っても最適性・集中上限・全損率の性能を認証しない。二頭軸・集中・配分は個別採否に従って継続検証する。

## 日別契約

日別JSONは初回/選定/最終/回顧scope、未最終理由、全初回レース行と独立KPIを持つ。Production対象は全初回、推奨対象は全最終を記録する。各KPIの対象は適格∪不適格∪保留（相互排他）、理由を全件要求する。任意市場を推奨KPIから認証しない。互換用actual_purchase集合は空にする。

適格を宣言する行には `operations` 内の宣言・FIX・本体・入力・選定履歴の参照、全出走馬番号、枠対応、8券種比較を添付する。予想/推奨の機械gateは同じレース・本文・版・発走予定へ接続する。新規実購入の適格認証は拒否する。Replayは前向き適格にできない。未登録・欠測は保持し、過去21Rとの差を第4の有効例へ合算しない。

## 切替・切り戻し

利用者は次期版v1.7.0、有効化をmainマージ後と指定した。全Owner・README・AGENTS・DECISIONS・監査・テンプレート・Phase・機械契約は同一commitで切り替える。合成受入は性能昇格・実レース・Windows/JRA-VAN接続を認証しない。

切替commitのrevertで全入口/Owner/監査を同時に戻し、新規保存済みJSONと旧履歴は削除しない。新しいサイクルを未実施のまま完了と表示しない。

## 追加受入：FIX参照・発走予定・相手情報の同一性

FIX manifestには固定本体と一致する `fixed_at_jst` と、実際に先行保存・読戻しした `intent_ref` を保持する。日別operationsのintentと同一参照であることを検査し、宣言の保存先・deadline・日次branchも本体と照合する。単に同じsnapshot IDを記載した別宣言で代用しない。

各レース行の `scheduled_post_time_jst` は初回公式登録時刻として不変とする。公式変更がない場合は適格gate・receipt・結果との直接一致を維持する。公式変更がある場合のみ、同一race/dateの固定公式本文と連続した変更chainを照合し、各gate・receiptの当時の読戻し時点で有効だった予定時刻と一致する場合に限る。遅延で過去のLATEを適格化しない。別日変更は保留する。手順と独立artifact形式は `docs/validation/contracts/cycle04_post_changes.md`。

近5走の `opponent_level` は `{status, value, source_ref, observed_at_jst}` の構造化属性にする。ACQUIREDにはcutoff以前の情報時点・出所・値が必要。MISSINGは値nullとreasonを保持し、入力充足へ含めない。近走の開催日が過去でも、その対戦相手の未来結果を現在の評価に利用しない。

## 再レビューで追加した保全・集計

公式scope登録時刻と追加履歴、全対象・発走予定を検査し、初回/最終のgate bytesと固定本体参照を履歴ごとに照合する。回顧済みの予想・結果・回顧を上書きせず、正式訂正は元記録を保持した別の訂正履歴で扱う。通常CLIで事後変更しない。

日別JSONを直接編集した場合も、全頭の公式結果・誤差/非劣化/次回検証の回顧・推奨結果の再計算一致を要求する。的中数の自己申告を集計しない。新規actual_purchase集合は空を要求する。

確信度別、入力完備/不足別、午前/午後別の◎成績、初回→最終の順位変更と◎的中の改善/悪化、回顧ラベルの件数を集計する。初回比較がないレースは不足IDを残す。固定予想に取消馬が残る場合は精度の分母へ入れず比較不能の理由を記録し、推奨の取消券判定は独立して実施する。取消後に再固定済みの予想は実出走集合で照合する。

任意市場を依頼された場合だけ`--date YYYY-MM-DD --record-market market-entry.json`を使う。entryはrace_idとmarket_ref、独立artifactはmarket-analysis-v1・race_id/race_date_jst・data_cutoff・marketを持つ。価格はPrediction固定後の独立cutoffで取得可能だが、cutoff・保存/読戻しは発走前を要求する。Predictionの順位・確率・基準・推奨・cutoffを変更しない。

## 公式結果の正式適格性と回顧手順（PR #82）

従来の `validate_official_result` は単独結果の形式検査であり、正式算入を認証しない。新規回顧では本文・注釈変換・全頭結果・固定予想/推奨をまとめた独立manifestが必須。診断用Replay/Syntheticや旧履歴は読めるが、新規の前向き成績には算入しない。更新時刻不明は `source_updated_at_jst=null` として保持し、取得時刻を代用・捏造しない。

1. JRA確定本文を閲覧後、RESULT目的の `chat-fact-request-v1` と `chat-fact-capture-v1` （`provider=OFFICIAL, mode=FORWARD, retrieval_kind=PAGE_TEXT`）を保存する。予定発走、取得開始/終了、URL、実本文、race/date/発走予定引用、確定表示、全頭着順、同着・取消・中止、複勝対象着数の引用位置を明記する。本文保存は `python3 scripts/chat_fact_capture.py --request result-request.json --captures result-captures.json --output docs/validation/fact-captures/YYYY-MM-DD/result.json --root .` 。日次 `prediction/YYYY-MM-DD` ブランチで行う。
2. `python3 scripts/chat_result_conversion.py --capture SAVED_CAPTURE.json --annotations annotations.json > conversion.json` を実行し、変換JSONと `conversion.result` を別々のJSONファイルに保存・読戻す。各JSONの実bytesのSHA-256を `sha256sum` 等で記録する。元本文を上書きしない。
3. `refs.json` を次の6キーで作成する。capture/conversion/resultはそれぞれ `{ "artifact_path": "repo相対path", "sha256": "ファイルbytesのSHA256" }` とする。prediction_gateは日別台帳の最新 `prediction_history[-1].prediction_gate_path` と `prediction_gate_sha256` 、prediction_originalはその最新 `prediction_ref` 全体。最終推奨がある場合はrecommendation_gateに固定gateのpath/hashを指定する。予想なしでは後ろ3キーはnull、予想のみではrecommendation_gateがnull。推奨なしでも保存済み最終推奨gateは省略しない。

```json
{
  "capture": {"artifact_path": "capture.json", "sha256": "取得本文のsha256"},
  "conversion": {"artifact_path": "conversion.json", "sha256": "変換のsha256"},
  "result": {"artifact_path": "result.json", "sha256": "結果のsha256"},
  "prediction_gate": null,
  "prediction_original": null,
  "recommendation_gate": null
}
```

4. `python3 scripts/chat_result_reconciliation.py refs.json --root .` で独立参照を事前照合する。この読取専用診断の `formal_kpi_certified=false` は維持する。`{ "schema_version": "cycle04-result-reconciliation-manifest-v1", "refs": <上記refsのJSONオブジェクト> }` を独立したファイルに保存・読戻しする。`refs.result` は回顧入力の結果と同じbytesでなければならない。
5. `review-entry.json` に `{ "race_id": "...", "result_path": "result.json", "result_reconciliation_ref": {"artifact_path":"保存済みmanifest.json","sha256":"manifestのSHA256"}, "review":{"error_classification":"...","non_degradation":"...","next_validation":"..."} }` を指定し、`python3 scripts/cycle04_workflow.py --date YYYY-MM-DD --review review-entry.json` を実行する。writerは実時計で未来取得を拒否し、保存原票から変換を再構築し、FORWARD・公式URL・レース/日付/発走・全頭/複勝・FIX予想/推奨同一性を確認後にだけ日別台帳を更新する。
6. `python3 scripts/check_cycle04.py`、`python3 scripts/cycle04_workflow.py --summary` と回顧資料は同じ固定manifestを再照合する。照合不足、REPLAY、SYNTHETIC、結果だけのmode削除、参照/本文差替え、未来取得、未確定は当該レースの回顧未完了として残す。元結果、予想、receipt、他レースは消さない。既存第4記録の出所不足を後付け証跡で真正化しない。

同着・取消・中止と複勝対象着数は既存 `chat_result_conversion.py` の規約を使用する。未対応形式は理由付きで保留し、前向き公式データとして合成しない。

## 初回・最終Shadowの固定履歴と適用判定（phase-shadow-v1）

`record_prediction` のentryはINITIAL/FINALそれぞれに `shadow_applicability` を明示する。省略、空配列からの自動対象外化、理由なしは拒否する。`status` は `APPLICABLE`（gateのshadow_itemsとitem_idsが一致）、`NOT_APPLICABLE`（該当条件を調べて対象外、item_ids空）、`UNKNOWN`（判定材料不足、item_ids空）のいずれか。全状態で空でない `reason` が必要。適用判定は当時の既存Shadow仮説の条件から行い、gateを照合しただけでは該当条件の真偽を自動認証しない。未確認はUNKNOWN/保留とし、後から偽の判定・証跡を作らない。

```json
{
  "shadow_applicability": {
    "status": "NOT_APPLICABLE",
    "reason": "最終時点の当該仮説の条件が成立しないと確認",
    "item_ids": [],
    "previous_item_dispositions": {
      "既存比較項目ID": {
        "status": "NOT_APPLICABLE",
        "reason": "最終時点における個別の非該当条件"
      }
    }
  }
}
```

`previous_item_dispositions` は、**直前の固定gateに存在した項目IDに加えて、全固定 `shadow_history` 内で最後の個別判断が `UNKNOWN` のまま未解決となっている項目ID**のうち、今回のgateに現れないものを全件登録する。途中のFINALが空でも未解決集合を消してはならない。継続保留には各改訂で `UNKNOWN` と個別の非空 `reason` を再登録し、**明示的に `NOT_APPLICABLE` 等へ判断・理由を更新するまで最新Shadow KPIを保留にする**。別のShadow項目が適格でも未解決項目の保留を優先する。今回のgateに項目が再出現した場合はその固定項目の状態に従い再判定する。未解決を置いたまま `NOT_APPLICABLE` にして対象集合・理由を削除する登録はwriter・preview・checker・summaryの全経路で拒否する。取り消し理由を一括の空配列だけで代用しない。未確定は `UNKNOWN`、不足が確定した場合は `INELIGIBLE` と区別する。上記JSONは書式例であり、実レースの適用状態・時刻・原本を作成した事実ではない。

新規日別行は `shadow_tracking_version=phase-shadow-v1` を持ち、`shadow_history` を `prediction_history` と同じ順序・件数で追記する。各履歴はphase、固定Prediction gateのpath/SHA-256、baseline ID、data_cutoff、item_idと個別状態/evidence_ref、適用判定、レース単位のShadow状態を固定する。同一gate/phaseの再登録は冪等だが、過去の適用理由・履歴の差替えは禁止する。既存行に履歴がない場合、旧固定gateとPrediction履歴は保存するが、欠落した当時の適用判断・receiptを後から捏造せず、回顧の `shadow_history_gaps` に表示する。

日別 `kpis.shadow` は**最新**PredictionのShadow適用状態だけをレース単位で表す。`NOT_APPLICABLE` は対象集合から以前の適格・不適格・保留および理由を除去し、`UNKNOWN` は理由付き保留とする。複数項目に適格と保留/不適格が混在した場合、全項目適格とはせず、保留を優先し、次いで不適格とする。初回の適格比較は `shadow_history` に残り、最終の対象外で失効・削除しない。Shadow不足はProductionの独立FIXと価格不要推奨の保存を失敗にしない。

`chat_calibration_review.py` は前向き網羅が返す `submitted_pair_bindings` のphase・固定gate SHA・baseline・cutoff・item_idを厳密に照合する。INITIALの固定Shadow比較では、日別行の最新FINAL推奨を対応する推奨と扱わず `recommendation_input=null`、`recommendation_binding_status=DIFFERENT_PHASE` として元の比較を出力する。FINAL比較に限り、最新推奨を正式validatorに通し、phase=FINAL・cutoff・baseline・固定Production原本（artifact path/SHA/id）が一致する場合のみ `MATCHED_FINAL` として結合する。FINALの参照なしは `NOT_RECORDED`、FINALでの異なるcutoff/基準/原本・phaseの偽装は拒否する。初回比較だけを除外・実測ゼロ化しない。\n\n`chat_review_package.py` は最新レースKPIと `shadow_comparisons_by_fixed_phase` を別々に出力し、同一レース・phase・gate SHA・baseline・cutoff・項目IDの組を一意の比較キーとする。異なるcutoff・基準を合算しない。`chat_forward_coverage.py` は最新gateだけでなく当時の固定phase履歴へ提出ペアを照合する。`chat_calibration_review.py` もphase/baseline/cutoffを維持する。対象が未確定の場合は保留を保ち、実測0や自動性能昇格に変換しない。旧台帳と初回比較の真正性は保存済みgate/receiptから検査し、未知の適用判断を自動補完しない。

## サイクル完了・理由付き終了（P1）

「正常一巡完了」は6開催日の実依頼scopeが登録され、各対象の初回Prediction・独立本体/FIX/hash/receipt/個別検査・公式結果照合・回顧が揃い、選定されたレースはFINALと独立推奨の保存/個別検査まで揃い、さらに集計と日別台帳をGitの固定commitから同一bytesで読戻した場合だけに用いる。初回のみで選定されなかったレースにFINALは要求しない。選定済みでFINALなしは未完了とし、発走後の恣意的な選定取消で隠せない。推奨なし・明示的印のみは独立保存された正当な最終状態であり、未保存PENDINGと同一視しない。

日別と集計の固定参照は、それぞれ次の形式で手動作成する。参照元のGit commitは対象ファイルを実際に含む40桁SHAを指定し、hashは当該bytesのSHA256を指定する。固定参照自体は予定日の事前証跡として作成しない。

`{"day_refs":[{"artifact_path":"docs/validation/records/cycle_04/YYYY-MM-DD.json","sha256":"<実際の64桁SHA256>","git_commit":"<実際の40桁commit>"}],"summary_ref":{"artifact_path":"docs/validation/reports/cycle_04/summary.json","sha256":"<実際の64桁SHA256>","git_commit":"<実際の40桁commit>"}}`

日別は登録した各開催日を漏れなく列挙する。全件回顧後、`python3 scripts/cycle04_workflow.py --summary` のJSON全体を `docs/validation/reports/cycle_04/summary.json` へ保存し、適切な作業ブランチからGitへコミットして読戻す。標準出力の表示、CLI return_code=0、ローカルhash一致だけでは完了ではない。発走前Prediction用receiptを集計へ流用しない。集計用証跡はこの後続Git commitの`git show COMMIT:path`で検証する。必要な全日の固定参照を`completion-manifest.json`へ手動入力する。

`python3 scripts/check_cycle04.py --require-complete --completion-manifest completion-manifest.json` は、6日全件の工程と実際のGit読戻しが揃ったときだけ0を返す。単独の`--require-complete`は集計固定参照がないため失敗する。通常`check_cycle04.py`と`cycle04_workflow.py --summary`は、不足対象・理由を保持して状態を表示するが、正常一巡と自己申告しない。

取得/保存不足・未実施のまま行政的に終了を判断する際は、Ownerが固定済み日別/集計・全初回scope・全不足理由・良好部分の保護・次試験・審査者・Owner・日時を確認し、人間の明示審査記録を`docs/validation/reports/cycle_04/closure-review.json`へ保存してGit読戻しする。必要schemaは`cycle04-closure-review-v1`、`decision=REASONED_CLOSE`、`reviewed_at_jst`、`reviewer`、`owner`、`reason`、`protected_good_parts`（非空list）、`next_validation`、`initial_scope`（全日/全race_id）、`documented_issues`（工程判定器の全不足）、`input_gaps`、`shadow_gaps`、`market_gaps`、`review_owner_gaps`（独立系列・Owner不足の全件）、`day_refs`、`summary_ref`、`performance_promotion=NOT_APPROVED`。審査記録を入力しない限り「理由付き終了」としない。CLIへは審査記録の`artifact_path`/`sha256`/`git_commit`を持つ`closure-ref.json`を渡す：

`python3 scripts/check_cycle04.py --closure-review closure-ref.json`

この判定は審査者の身元証明そのものは行わない。正式なOwner承認は運用側で確認しなければならない。未登録日・未測定KPI・Shadow/市場の不足を勝手に補完せず、終了審査の承認は性能採用、履歴復元、個別予想保存の再認証とは独立する。入力不足/該当Shadow不足/任意市場不足は各々独立表示し、任意市場とShadowの実測未受入だけを標準Prediction・価格不要推奨の完了障害にしない。

### 固定履歴ごとの宣言・FIXと読戻し（PR85のP1回帰）

初回から最終までの各 `prediction_history[]` は、履歴自身の `prediction_gate_path`/`prediction_gate_sha256`、`prediction_ref`、`intent_ref`、`fix_ref` を個別に固定し、工程完了時にそれぞれの実原本・SHA256・同一receipt・発走前保存/読戻しを再照合する。固定gateのレース・日付・発走時刻・baselineと予想本体を一致させ、宣言のrace/snapshot/path/期限、FIX manifestのsnapshot/path/hash/固定時刻・宣言参照を一致させる。必須順序は「宣言の読戻し ≤ 予想FIX時刻 ≤ FIX manifest保存 ≤ FIX manifest読戻し ≤ 予想本体保存」。原本欠落・改変・時刻逆転は初回履歴の工程不足として残し、最新FINALの正常な宣言/FIX、最新 `row.operations`、同一予想本体hashで補完しない。通常の最終gateの証拠と過去FIX原本の確認は別の検査であり、過去証跡を後付けで作成しない。

`cycle04_workflow.py --summary` は修復前の原本を消さず履歴単位の `PREDICTION_CHECK_PENDING` とその理由を出す。正常一巡の `--require-complete` は当該不足がある限り拒否する。理由付き終了でも不足を全件保持し、性能適格化しない。


## 回顧Owner必須項目・独立成績・追記履歴（PR88）

- 新規回顧入力は `docs/validation/templates/cycle04_review_entry_v2.json` を使用し、`schema_version=cycle04-review-v2` と `state=DRAFT/COMPLETE` を明示する。既存の旧schema回顧は読取可能だが `HISTORICAL_REVIEW_SCHEMA` とOwner不足を示し、現在の完了条件へ遡及昇格しない。上記の旧3項目だけの入力例は新規Writerでは受け付けない。
- `protected_good_parts`、`revalidation_targets`、`improvement_targets` は空文字なしの配列、`_status=RECORDED/NOT_APPLICABLE/PENDING`、非空の `_reason`、`_required_inputs` を持つ。RECORDEDは項目1件以上・必要入力空、NOT_APPLICABLEは項目空・理由付き・必要入力空、PENDINGは項目空・理由と必要入力1件以上。COMPLETEはPENDING/未入力を拒否する。
- 公式結果はDRAFTでも従来の本文/変換/manifest検査を満たせば固定できるが、`reviewed_scope` に入るのはCOMPLETEだけ。DRAFTを回顧完了数・正常一巡へ算入しない。未最終・低確信・推奨なしも回顧scopeから除外しない。
- 初版は日別 `review_history[0]` に固定hashと内容を残す。回顧の追記・訂正は、元のreviewを上書きせず、`docs/validation/review-revisions/YYYY-MM-DD/RACE_ID/<revision>.json` の独立原本を保存・読戻しし、review-entryへ `revision_ref={artifact_path,sha256}` を指定する。revision原本は `schema_version=cycle04-review-revision-v1`、`race_date_jst`、`race_id`、単調増加 `revision`、直前のreview内容hash `supersedes_sha256`、新しい `review` を持つ。過去の内容/hash/参照は履歴へ残す。結果原本・結果manifestの差替えはこの回顧改訂で許可しない。
- 初回→最終の変更根拠は `change_evidence` に `initial_gate_sha256/final_gate_sha256`、双方の `baseline_forecast_id` と `cutoff`、`status=PRE_RACE_CONFIRMED/INSUFFICIENT/PENDING`、非空の `reason` を持つ。事前確認済みは固定 `evidence_ref`、元の事前原本に実在する正確な `fixed_quote`、発走前receipt、最終cutoff以前の読戻し・同一race/dateを必要とする。PENDINGには `required_inputs` を残してCOMPLETEを拒否する。複数FINALなど比較phaseが曖昧な事例を混ぜない。Ownerの「強い新事実」を結果から自動分類しない。
- `cycle04_workflow.py --summary` と `chat_review_package.py` の `independent_review_metrics` は、固定INITIAL/FINAL時点での無印馬の1着・2着・3着内、事前変更根拠、推奨失敗（軸崩れ・着順不一致・相手/第三馬漏れ）を独立表示する。各系列は `target_ids`、`eligible_ids`、`included_ids`、`missing`（理由と必要入力）を持つ。0適格は率null。複数原因は同じ券に付与できるため、ラベル件数と `unique_races`/`unique_tickets` を別表示する。
- 推奨失敗は固定 `RECOMMENDED` の独立gate、公式全頭結果、既存settleを使用する。取消券INVALIDは適格な的中分母から除く。NO_RECOMMENDATION・EXPLICIT_MARKS_ONLY・PENDINGをMISSに算入しない。価格、購入、払戻、性能昇格は追加しない。
- 正常一巡は全COMPLETE回顧・保存証拠・集計Git読戻しを必要とする。Owner効果採否と性能昇格は人間の別審査とし、自動承認しない。理由付き終了はOwner不足とGit固定参照を記録する。


### PR88 追加レビューの3件是正（2026-10-15）

- phase別無印成績は、固定された当該INITIAL/FINAL `prediction_gate_path` を再検査し、日別race modeと各gate modeがともに `FORWARD`、かつ `kpi_eligibility.production=ELIGIBLE` の場合だけ適格とする。`PENDING` / `INELIGIBLE` / `REPLAY` と未完了回顧は、`coverage.missing` に原因・必要入力を残して対象集合から脱落させず、eligible/includedの分母へ加えない。初回→最終比較は**両方**の固定phaseが前向きProduction適格な場合だけ可能であり、最新FINALの適格性をINITIALへ流用しない。
- `DRAFT` は `error_classification` / `non_degradation` / `next_validation` が空でもOwner不足として記録・公式結果固定可能。ただし `reviewed_scope` と精度/追加集計には算入しない。`COMPLETE` のみ既存の必須項目と保護・再検証・改善の確定状態を満たす必要がある。旧記録の既存3項目チェックは継続する。
- 順序付き馬単・三連単の失敗 `ORDER_MISMATCH` は、同着を含む `finish_groups` と矛盾しない上位N着の全順序（境界同着は必要着数だけ）から判定する。候補中に同じ馬の組合せが存在し、並びだけ不一致の場合に分類する。的中/無効の判定は従来の `recommendation.settle` のまま。順序不要券に着順不一致を誤付与しない。

- 推奨失敗分類の `recommendation_failure_classification` も無印・phase比較と同様に、`reviewed_scope` に入ったCOMPLETE回顧だけを分母（`eligible_ids`/`included_ids`、`unique_races`/`unique_tickets`、`miss_tickets`）へ算入する。正式なFINAL推奨・公式結果・SETTLED精算が先に固定されていても、回顧がDRAFTなら `coverage.target_ids` を維持し、`missing[date:race]={reason:REVIEW_NOT_COMPLETE,required_inputs:[completed_review]}` に記録して未算入とする。回顧を独立revision原本でCOMPLETEへ改訂した場合にのみ、元の推奨・公式結果・精算をそのまま再利用し算入する。
 

## 第4サイクルの移行後入口・日別状態・過去不足の判別

この章を第4の運用開始から終了までの唯一の統合手順とする。第2/第3の採否・残件は `reviews/cycle_04/carryover.json`、原本保持/削除は `reviews/cycle_04/migration-manifest.json` へ移した。正式予想判断は引き続き `docs/manual/` を唯一のOwnerとする。

前向きの依頼を受けたら、当日について `run_release_readiness.py --require-main` で取得済みmainを確認し、予想作成前に宣言を独立保存・読戻しする。公式scopeの `cycle04_workflow.py --register-scope` または同日追加の `--extend-scope` が成功し、対象日の台帳をGit保存・同一bytesで読戻すまでは初回Predictionの作成・正式完了判定へ進まない。登録日と対象開催日を混同しない。宣言があり台帳がない場合は `cycle04_migration.py --audit` が不足として非0で終わる。CIはチャット外の未取得依頼を自動発見できない。

初回/選定FINAL/結果確定後の各工程では上記の既存writerを用い、実際のFIX bytes/receipt/gateを一件ずつ確認する。各段階が完了したら `cycle04_workflow.py --summary` と `cycle04_migration.py --write-summary --audit` の集計結果を照合し、日別台帳とsummaryを同じ日次branchへコミットしてGit読戻しする。合成受入の成功や準備成功は正常一巡を意味しない。新規保存・時計の復旧はPR94の統合済み版を確認してから既存の安全な手順で行う。ツール安全性拒否を迂回せず、未保存原本を改変しない。

10/17は `records/cycle_04/2026-10-17.json` の `registration_origin=POSTRACE_RECONCILIATION` として登録した。36Rは事後の結果照合対象で、`initial_scope/selected_scope/final_scope/reviewed_scope` は前向き認証として空のまま。元IDと正規化IDの両方を保持し、6Rのみ公式個別結果照合、残り30Rは二次情報と区分する。旧認証拒否、未保存の初回予想、推奨4診断、発走前scope未登録は変更しない。将来の前向き依頼にこの日の事後台帳を転用しない。

通常監査は `python3 scripts/check_cycle04.py`、事後原票照合は `python3 scripts/check_cycle04_full_day_reconciliation.py`、移管正本/集計/欠測判別は `python3 scripts/cycle04_migration.py --audit` を使用する。推奨の厳格CLI `python3 scripts/recommendation.py --audit` は従来の過去不足4件で非0。CIの `cycle04_recommendation_diagnostics.py --audit` は厳格CLIの実出力と固定原票SHA-256を照合し、4件が増減・改変したら非0にする。基準一致時も厳格CLIは非0であり、正常な推薦が完了したと表現しない。正常な実レース一巡・全6日終了・性能採用はそれぞれ別の検査/審査が必要。


## 段階別監査と固定履歴への移管

`python3 scripts/check_cycle04.py` は第4の準備整合に加え、実際に依頼・登録された日別scopeの段階別監査を実行する。初回は初回scope、FINALは選定scopeだけを対象にする。発走前に不足があればWAITINGとして表示し、公式変更履歴を適用した発走予定時刻以上で不足があれば終了1。未選定レースのFINALと未依頼の未来日は要求しない。準備だけを確認する場合は `--preparation-only` を明示し、日次成功の証明には使わない。全期間終了は引き続き `--require-complete --completion-manifest ...` で独立審査する。

回顧開始時は、先に保存した公式結果と照合manifestを指定したJSON（`race_id / result_path / result_reconciliation_ref`）を、`cycle04_workflow.py --date YYYY-MM-DD --request-review <JSON>` に渡す。既存の日次branch・writer・排他制御を使い、公式結果の実本文/hash/取得時刻/照合manifestを検査して `result_ready_ref` を記録する。公式結果未確認はWAITING_RESULT。結果確認済みで回顧未完了は終了1となる。結果の確認前後をタスク開始時刻や発走からの推測時間で代用しない。CI/checkerが失敗しても予想の固定・保存・提示を継続し、該当工程の未完了を残す。

第2/第3の終了資料・採否・旧操作説明は第4の繰越正本と本書へ統合した。削除対象7資料は移行manifestに固定commit/path/blob/SHA-256と統合先を記録し、`cycle04_history.py --audit` が64原入力をGitから実取得して集合・KPI・精算を再計算する。第4の通常検査は第3作業ツリーの採否/集計ファイルを読まない。固定履歴が取得不能・誤blob・本文hash不一致・再計算差分なら失敗し、確認フラグで代用しない。未解決の第2件数や第3保留57件を第4の前向き母数へ移していない。


### 回顧前固定結果の保全と公式訂正

`result_ready_ref` と `result_ready_reconciliation_ref` は、回顧後も原本として毎回照合する。同じ結果を採用するときは、回顧の `result_ref` / `result_reconciliation_ref` が両方とも一致しなければならない。通常の日別検査、日次監査、回顧writer、再度の回顧依頼で共通の固定参照検査を実行し、元結果・元manifest・内部のcapture/conversionを上書きしてはならない。回顧前固定を持たない既存回顧は既存の結果参照を維持し、新規回顧は `result_origin_ref` / `result_origin_reconciliation_ref` も保存する。

公式訂正がある場合は、訂正結果と照合manifestおよび内部原票を新規pathへ保存する。さらに `docs/validation/result-corrections/YYYY-MM-DD/<race_id>/RNN.json` へ次のJSONを独立保存し、pathと実本文SHA-256を回顧入力の `result_correction_ref` として渡す。訂正原本は `schema_version: cycle04-result-correction-v1`、`race_id`、`race_date_jst`、連続した `revision`、前訂正の `previous_sha256`（初回null）、`from` / `to`（それぞれ `result_ref` と `reconciliation_ref`）、空でない `reason`、実際の `recorded_at_jst` を持つ。既存原票と訂正原票、対象・連鎖・時刻・全hashを検査し、訂正後も元の固定結果を保持する。既に回顧済みなら、従来の `revision_ref` による回顧改訂履歴も必須。結果訂正履歴と回顧文の改訂履歴を混同しない。

日次対象0件は `target_count: 0` / `state: NOT_REQUESTED` と表示し、CI終了0でも工程完了とはしない。過去台帳の表示用リンクは固定commitの原文から削除先リンクだけを置換したものと照合する。移行監査は全Markdown・HTMLの相対リンク、参照形式、HTML属性も走査し、削除資料へのリンク切れを拒否する。旧集計の再計算には引き続き固定履歴の原文bytesを使う。
