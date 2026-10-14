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

予想entryは`race_id`、`phase=INITIAL/FINAL`、`prediction_gate_path`、`operations`（下記の独立証跡）、`input_complete`、不足理由/影響、`market`を持つ。FINALは`recommendation_gate_path`も必須。selection entryはrace_idとselection_ref。SELECTだけで候補を登録でき、買い目固定を先に要求しない。同じ入口でCANCEL→DESELECTまたは再SELECTの連続履歴を適用する。履歴の巻戻し・分岐は拒否し、最終は最新の選定履歴へ買い目固定イベントを追記した連続履歴も受け取り、独立証跡を照合して保存する。選定後に買い目を作る通常の順序で完了できる。review entryはrace_idとresult_path、review（error_classification / non_degradation / next_validation）。公式結果はOFFICIAL、同一ID/開催日、source_url、発走後retrieved_at_jst、同着をまとめたfinish_groups、place_placesを持つ。着順・non_finishers・scratched_horsesの和は固定予想の全頭と一致させ、不完全な結果を完了へ算入しない。

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

各レース行の `scheduled_post_time_jst` は開催日（JST）と一致し、適格gateの実発走予定と同じ時刻であることを必須とする。別日・別時刻のreceipt/gateで認証しない。

近5走の `opponent_level` は `{status, value, source_ref, observed_at_jst}` の構造化属性にする。ACQUIREDにはcutoff以前の情報時点・出所・値が必要。MISSINGは値nullとreasonを保持し、入力充足へ含めない。近走の開催日が過去でも、その対戦相手の未来結果を現在の評価に利用しない。

## 再レビューで追加した保全・集計

公式scope登録時刻と追加履歴、全対象・発走予定を検査し、初回/最終のgate bytesと固定本体参照を履歴ごとに照合する。回顧済みの予想・結果・回顧を上書きせず、正式訂正は元記録を保持した別の訂正履歴で扱う。通常CLIで事後変更しない。

日別JSONを直接編集した場合も、全頭の公式結果・誤差/非劣化/次回検証の回顧・推奨結果の再計算一致を要求する。的中数の自己申告を集計しない。新規actual_purchase集合は空を要求する。

確信度別、入力完備/不足別、午前/午後別の◎成績、初回→最終の順位変更と◎的中の改善/悪化、回顧ラベルの件数を集計する。初回比較がないレースは不足IDを残す。固定予想に取消馬が残る場合は精度の分母へ入れず比較不能の理由を記録し、推奨の取消券判定は独立して実施する。取消後に再固定済みの予想は実出走集合で照合する。

任意市場を依頼された場合だけ`--date YYYY-MM-DD --record-market market-entry.json`を使う。entryはrace_idとmarket_ref、独立artifactはmarket-analysis-v1・race_id/race_date_jst・data_cutoff・marketを持つ。価格はPrediction固定後の独立cutoffで取得可能だが、cutoff・保存/読戻しは発走前を要求する。Predictionの順位・確率・基準・推奨・cutoffを変更しない。
