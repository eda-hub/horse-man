# P1：公式結果の適格性と標準回顧接続の修正実施計画

## 目的・対象・状態

- 作成日：2026-10-14（JST）
- 作業branch：`fix/p1-official-result-eligibility`
- 調査基準main：`b288bc1f39f61d68c6cf536608c11689575315e8`
- 状態：全758回帰・標準受入PASS/release生成・通常検査・実main統合受入・3系統CI成功。PR87でmain証跡を修復し、取得済みmain 509368351cc45046fcd524b9ac4905a5a40b6b8e に整合。候補の未マージ拒否は維持。
- 目的：通常の回顧・日別検査・サイクル集計が、固定された公式本文と対応する結果だけを新規の前向き成績へ算入するようにする。
- 完了対象：結果の出所・本文・変換・本体・時点・実測区分の接続欠陥。結果取得サイトの自動収集や新しい性能評価モデルは対象外。

## 再現・原因・影響

`cycle04_operations.validate_official_result` は結果のstatus、race/date、HTTPS URL、発走以降の取得時刻、全頭集合を検査するが、保存本文との一致、FORWARD/REPLAY/SYNTHETICの出所区分、現在時刻より未来でないことを標準入口で要求していない。

一時fixtureで、正常な独立保存済みProductionを日別台帳に登録し、全頭結果へ `mode=SYNTHETIC` または `mode=REPLAY` を付けて `cycle04_workflow.review → summary` を実行した。両方とも回顧登録が成功し、Predictionの適格回顧1件・◎勝率1.0へ算入された。REPLAY例のsource_urlを非公式のexample.comへ変更しても通った。これは合成再現であり、実レースの成績ではない。

既存 `chat_result_reconciliation.audit_saved` は保存本文・変換・結果・固定予想を再照合するが、標準writer/validator/summaryから必須接続されていない。別入口の診断成功を正式適格性へ転用せず、同じ検査を正式算入条件へ接続する。

## 修正方針

1. 形式検査と正式結果の適格性を分離する。旧履歴や診断用Replay/Syntheticの読取を禁止せず、新規前向き成績への算入を拒否する。
2. 新規日別回顧entryに、保存したcapture/conversion/resultと固定予想・推奨への参照を持つ独立の結果照合manifestを接続する。各参照は既存の固定path/hash形式を使い、`result_ref` と同じ結果bytesを指すことを要求する。単独の「検査成功」フラグを信用しない。
3. 保存本文から変換を再構成し、race/date/発走予定・公式確定引用・全頭結果・複勝対象着数を既存照合で検査する。公式ドメインだけを真正性の証明にせず、実際に取得した本文と追跡可能な固定参照を残す。
4. captureとconversionの実測区分を保持し、正式算入はFORWARDに限定する。本体から区分を取り除いてもmanifest側で判定できる構造にする。診断結果の `formal_kpi_certified=false` をwriter側で無条件にtrueへ置換しない。
5. 結果の取得時刻を「発走予定以降、実際の検査時刻以下」に制限する。writerの検査時刻は実時刻を使い、CLIの任意未来時刻で回避できないようにする。テストは時計を明示的に固定する。
6. 結果の掲載更新時刻不明は、既存結果変換が許す範囲で不足情報として保持する。更新時刻の不明だけから本文取得時刻を捏造せず、結果用の規約を発走前入力へ流用しない。
7. 結果照合不足は結果artifactと保存済み予想を保全し、そのレースの結果/回顧を未完了または不適格として明示する。他レース・予想保存・価格不要推奨を止めない。source/ref不足を持つ既存第4記録を発見した場合も、後付け真正性で再認証しない。

## 実装対象・境界

| ファイル | 変更内容 |
|---|---|
| scripts/cycle04_operations.py | 共通の正式結果適格性検査を追加。旧形式検査とは責任を分離 |
| scripts/chat_result_reconciliation.py | 保存本文からの再照合を再利用可能にし、循環importを回避 |
| scripts/cycle04_workflow.py | review entryに固定照合参照を接続し、summaryの結果算入も同条件で検査 |
| scripts/check_cycle04.py | 直接編集台帳でもwriterと同じ結果照合を要求 |
| scripts/chat_review_package.py | 同じ結果参照・適格性・不足を引き継ぐ |
| scripts/test_cycle04_workflow.py、test_cycle04_acceptance.py、test_chat_result_reconciliation.py、test_chat_review_package.py | 正常/不正/不足/旧互換の回帰 |
| docs/validation/contracts/cycle04_operations.md、templates/chatgpt_prediction_task.md | 実際に実行できる結果保存・参照組立・回顧手順を追記 |

共通検査の配置はimport依存を確認して決める。writerをimportする診断moduleをそのまま逆importして循環を作らない。新規参照項目のschema/契約は明示し、全fixtureを同じ契約へ更新する。過去本文や既存結果を合成の真正原票へ置換しない。

## 小項目別の実装・コミット計画

| 小項目 | 作業と完了条件 | 日本語コミット案 |
|---|---|---|
| 01 | 上記の合成・再演・非公式出所・未来取得の受入漏れを一時fixtureの回帰テストにし、現行で失敗することを確認 | 公式結果の適格性抜けを回帰テストで再現 |
| 02 | 固定照合manifestと共通正式結果validatorを実装。本文/変換/結果の一致・区分・時点・identityを検査 | 固定公式本文に基づく結果適格性検査を追加 |
| 03 | review/validate_day/summaryへ接続。直接編集・区分削除・参照差替えの回避を拒否し、不足時の保存保全を確認 | 標準回顧と集計を公式結果照合へ接続 |
| 04 | 回顧資料・テンプレート・契約・関連fixtureを更新し、旧履歴と未最終/推奨なしを維持 | 結果照合の運用手順と不足表示を整備 |
| 05 | 全受入・manifest・統合検証・CIを実施し、要件対応を本書へ記録 | 結果適格性修正の統合受入とリリース整合を固定 |

## 受入条件

- 正常なFORWARD公式本文、確認済み注釈、固定結果、同一予想/推奨が一致すれば、初回のみ・最終あり・推奨なしのいずれも結果/回顧を保存できる。
- 合成・再演・区分不明、本文未接続、別レース/別日/別発走、別予想、hash不一致、未来取得、未確定、全頭不足は正式成績へ算入されない。
- 単独resultのmode削除、statusのOFFICIAL自己申告、別URLへの変更だけで適格化できない。
- 同着・取消・競走中止・複勝対象着数は既存の結果変換と券照合を保全する。未知の表示形式は理由付き不足のままにする。
- read_only診断、旧履歴、任意市場、保存済みProduction/Recommendationのbytesと独立KPIを変更しない。
- writer・日別validator・summary・回顧資料の同一ケース判定が一致する。チェック失敗時に旧台帳を中途半端に書換えない。

## 検証・実装結果の記録

関連テストから開始し、全回帰と通常checkerへ広げる。少なくとも `test_cycle04_workflow`、`test_cycle04_acceptance`、`test_chat_result_conversion`、`test_chat_result_reconciliation`、`test_chat_review_package` と旧予想/推奨の回帰を実施する。全回帰は `python3 -m unittest discover -s scripts -p 'test_*.py'`。受入更新・release整合・統合受入は共通規約に従う。

実装時に本書へ「小項目／commit SHA／変更path／実行コマンド／期待結果／実結果／残件」を追記する。最新実績・残件は本書末尾を参照。

## 共通の作業・統合規約

- 対象は常に `eda-hub/horse-man`。本書は実装計画であり、現行Productionルールの代用にしない。
- 本書作成時の依頼は計画書作成までだったが、2026-10-14の追加指示によりPR #82の実装を開始した。実レースの記録作成・性能昇格は今回の対象外。
- 既存v1.7.0の予想骨格、価格不要推奨、Production/Shadow/任意市場の分離、旧v1.6.1履歴を維持する。実購入・価格・払戻・実測性能を標準完了の必須入力に戻さない。
- 合成fixtureは一時領域で検査し、実日別台帳・未来の事前証跡・実測0を作らない。第4開催の実測、過去研究の網羅、性能昇格を本修正PRのマージ条件にしない。
- コミット・PR説明・作業記録は日本語。各小項目を実装・対応テスト・セルフレビューまで行い、小項目ごとにコミットする。未完了項目を完了と記載しない。
- 実装開始時に本書、AGENTS、最新main、対象branch、関連Ownerと対象コードを読戻す。本書の基準以降に変更があれば差分を確認して計画を更新し、確認した再現・受入条件を維持する。
- 4件の統合順は「結果の適格性 → Shadow証跡 → 初回/最終Shadow状態 → サイクル完了」。各計画は単独の基準から作成するが、後続の実装では先行修正を取り込んだ最新mainを反映してから着手する。共通ファイルの変更は機械的なours/theirsで解消しない。
- 対象コード・テスト・運用契約を変更した最終内容で `python3 scripts/run_cycle04_acceptance.py --write` を成功させ、その後 `python3 scripts/build_v170_manifest.py` でrelease manifestを再生成する。先行PRの受入・manifestを単純にコピーしない。
- 全回帰、通常checker、合成受入、release整合、統合受入と3系統CIを確認する。開始認証の `--require-main` は未マージの候補branchを認証するために改変しない。統合受入は取得済みmainと候補branchの契約一致/未マージ拒否を正しく区別する。
- 必要な過去Git履歴・原票・PDF依存を取得できない検査は実行不能として残す。失敗をコード欠陥と混同せず、未実行を成功にしない。完了報告には実行コマンド・結果・CI対象SHA・残件を対応付ける。
- 修正の切り戻しは対象変更のrevertで行い、保存済み予想・receipt・結果・比較履歴を削除しない。後続PR統合後は依存を確認し、関連契約・受入・manifestを同時に整合させる。

## 実装実績・検証記録（2026-10-14）

対象branchは `fix/p1-official-result-eligibility`、調査基準mainは `b288bc1f39f61d68c6cf536608c11689575315e8`。mainは変更していない。実レースの結果や未来の事前証跡、実測0は作成していない。

| 小項目 | 代表commit SHA／変更path | 実施・検査結果 | 未完了事項 |
|---|---|---|---|
| 01 | `15fc27edea6465f42de1c4bd18889bae2c83c9b6`, `69d3a541110160581d4a7e05dc69e1954271b82b` ／ `scripts/test_cycle04_result_eligibility.py` | 単独OFFICIAL、Replay/Synthetic、未来取得、URL差替え、固定参照切離し、日別台帳改変を負例に固定。変更前の算入成功は本書の再現欄に記録。 | 最終CI再実行 |
| 02 | `62e6f6625f4e3a1d029d37470954a5d35c6f5388`, `0d0ca7164bc4f3dedd35e167ff787c8cd809ab8b`, `b44bd3872456387c96edda4a25c85a41519693eb` ／ `scripts/chat_result_reconciliation.py`, `scripts/cycle04_operations.py` | capture/conversion/resultの固定6参照を独立manifestに固定し、原文再変換、FORWARD、実時計、レース/発走と予想/推奨の同一原本を要求。遅延importで循環防止、読取診断の認証フラグは保持。 | 追加修正後の全回帰 |
| 03 | `a39c53c72dbfe65b6a7b4bcad75e55883f210039`, `189244fdc1d37642d4615c8e3e59667a63452d7c` ／ `scripts/cycle04_workflow.py`, `scripts/check_cycle04.py` | writer保存前・validate_day・summaryで同じ適格性検査。照合不合格時は既存台帳を上書きせず、他の保存済み原票を保全。 | 最終CI再実行 |
| 04 | `37976cf0e8665a88625e1721d807414322a8852b`, `47f544aa0942737b8f5bd3c7fc619c70854af349`, `c8eec2a46909121bf73dc48c93882b39282a78c9`, `e15508e43e8a3757791fa24667a7ba3958cdd74d`, `3aeec23af9b1a0f058a57dd735616d7cb5b5f7f4` ／ `scripts/chat_review_package.py`, `scripts/test_cycle04_workflow.py`, `scripts/test_chat_review_package.py`, 既存運用契約と標準テンプレート | 初回のみ・FINAL・推奨有無、同着・取消・複勝対象着数を既存ロジックで検査。回顧資料にも原本参照と照合状態を出す。 | 新規回顧資料テストのCI確認 |
| 05 | `143ccbbccc23dc581966ee0b7583eea063014d50`, `6c44d4df7fc669a1a7a22133c3abddc8ab20b079` ／ `docs/validation/reviews/cycle_04/acceptance.json`, `docs/validation/contracts/v170-release.json` | GitHubから取得したソースbytesのSHA-256を再計算し、受入750件・143ソース、release162ソースのmanifestへ反映。ファイル再生成用コマンドの実行成功を主張しない。 | **最新750件の全回帰、実行コマンドでの再生成、通常checker、統合受入、3系統CI成功確認が未完了** |

### コマンド・CI結果・阻害事項

- `python3 -m unittest discover -s scripts -p 'test_*.py'` は `c3a13ff6b937107f8917b457e7659502274a82d5` のActions「予想実行と第3サイクル台帳の機械監査」で**回帰テストステップ成功**（当時749件）。予想保存の監査・第3台帳検査も成功、第4checkerは旧受入source hashの不一致で停止。その後変更されたテスト1件を含む最新750件の実行結果は未取得。
- `python3 scripts/check_integration_acceptance.py --full` は上記時点で旧release source hash不一致により停止。後続でmanifestを再計算したが、最終検証の実行結果は未取得。
- `python3 scripts/run_cycle04_acceptance.py --write` および `python3 scripts/build_v170_manifest.py` は、GitHubファイル編集経路では直接コマンドを実行できないため**未実行**。該当JSONは取得した各ファイルbytesからSHA-256を計算し更新した。次回の標準スクリプトで生成結果と照合する必要がある。
- `6c44d4df7fc669a1a7a22133c3abddc8ab20b079` の3系統CIはすべて失敗したが、いずれも開始から2〜3秒で終了し**ジョブステップ数0**。ジョブログの取得は404（BlobNotFound）。コードエラーと判別できず、外部Actions実行基盤の阻害として区別。実行IDは統合 `38522232059`、台帳 `38522232035`、血統 `38522232023`。同種の事象は直前のCIで発生し、3系統の失敗ジョブを再実行しても再発。
- **完全な統合完了判定は保留。** 最新の全回帰→受入 `--write`→release manifest生成→通常checker→統合受入 `--full`→3系統CIの順で再実行する。未マージbranchの `--require-main` が拒否することは正常であり、開始認証を緩めない。

セルフレビュー：変更は当該公式結果経路と回帰・文書・manifestに限定。実日別台帳、既存Production/Recommendation保存原本、旧v1.6.1履歴、Shadow、任意市場は書き換えていない。

## 再開確認（2026-10-14 15:35 JST）

- PR #82、対象branch、AGENTS、本計画と最新base/headを読戻した。base mainは `b288bc1f39f61d68c6cf536608c11689575315e8`、検証対象headは `c9acf111d3767a4f655445ec9ad0e492f57bfc35`。前回のGitHub connector方式で再開し、実装済み部分は作り直していない。
- 上記headの統合 `38522451242`、台帳 `38522451232`、血統 `38522451304` の失敗ジョブを再実行した。3系統ともattempt 2でfailure。check-run/jobはそれぞれ `115717080399`、`115717083264`、`115717086607`、実行stepsなし。ジョブログは404 BlobNotFound。check-runに失敗注釈2件ずつ存在するが、annotations URLはconnectorの許可endpoint外として400で拒否され、内容未取得。原因を課金・runner・コードのいずれとも断定しない。
- ローカルのGit取得も試みたが、GitHubおよび環境のGit proxy経路ともUsername取得不能でclone失敗。全回帰・標準スクリプトによるmanifest生成・通常checker・統合受入の直接実行はできていない。
- 実装、実レース原票、manifestの検証結果を偽装せずDraftを維持。完了条件は前節のまま。実行環境の復旧、またはAGENTSの再開方式規約に沿って利用者が承認した実行可能な方式が必要。

## レビュー指摘対応：未検証PASSの撤回（2026-10-14）

- 指摘は妥当。小項目05でソースhash更新に合わせて750件・失敗0・skip0・PASSを記録したことは、実行成功の証拠がなく不適切だった。前節のmanifest更新記録は履歴として保持するが、成功認証として撤回する。
- `65a68a287ae4ab80785f9afd3198624d36017359` でacceptance.jsonのresultをNOT_RUNへ変更し、tests_run/failures/skippedをnullへ訂正。残したsource_manifestは同一性の参考情報にすぎず、成功証明ではないことをnoteに明示。失敗0やskip0の自己申告は残していない。
- 保存後にGitHubから読戻し、NOT_RUNとnullを確認。取得したscripts/check_cycle04.pyのcheck_preparation内の受入検査ブロックを変更せず抽出し、訂正後のJSONを入力としてローカルpython3で実行した。`acceptance not passed`で拒否し、未実行件数がnullであることもassert成功（終了0）。これは受入判定ブロックの限定検査であり、通常checker全体・全750回帰・標準受入スクリプト成功を意味しない。
- 当時はCIの利用上限が報告され、再実行は未実施だった。既存release manifestの受入ファイルhashも変更後は不一致のままとし、未検証状態を認証するための手動hash追従は行わない。
- 残件：実行可能な環境で最新コードの全回帰→run_cycle04_acceptance.py --write→build_v170_manifest.py→通常checker→統合受入を実行し、成功出力でのみ受入/releaseを更新。3系統CIを実行して結果を確認する。Draft継続・main変更なし。

## 再レビュー2件への修正（2026-10-14）

- 正式開始経路の受入未検査を修正。`check_cycle04.validate_acceptance`へ共通のschema/合成区分/未実行・失敗/skip/ソースcoverage/hash検査を分離し、準備検査と`run_release_readiness.check(..., require_main=True)`の両方へ接続。全scriptsと全Ownerの省略も拒否する。取得済みmainとローカル受入bytesも一致必須。
- `build_v170_manifest.py`にacceptance.jsonを追加し、開始検査でその固定対象への包含も要求。前節で記載した「既存releaseの受入hashが不一致」は誤りだった。従来acceptance.jsonはrelease対象外であり、その未接続を今回修正した。未検証の現行releaseを手動で再認証していない。
- 実ファイルのPASSをコピーしていた準備テストを、`synthetic_acceptance(root)`が明示的に組み立てる独立した合成fixtureへ置換。正常系・NOT_RUN/FAIL/skip拒否・古いhash・実測自己申告を分けて確認。正式開始テストも一時Git環境だけで合成受入を作成し、実acceptanceを書換えない。
- 変更commit：共通validator `e57007efcb391a48d77ba49fd7dd3af21bf78f86`、正式開始 `b631fe79a9805177b0006ba61620096ff72cbfb0`、manifest生成対象 `e3017c3c7d7abf3b066a187afc92d8b924faf414`、準備fixture `76a7df5130b0c039d0a3fdf19b73cb141dda1aae`、隔離main回帰 `baf6a91f96d87cbda8d64c2ccbd95ac9d7b37ad2`、全コードcoverage `50c433f2f3a42ddb8701bb045e82e8ec1f4e2aa5`。
- GitHub connectorから164ソースと準備/結果変換テストに必要な既存原票をローカル一時領域へ取得し、前回のGitHub接続で編集した内容を検査した。`python3 -m unittest test_cycle04_acceptance test_cycle04_workflow test_cycle04_result_eligibility test_chat_result_conversion test_chat_result_reconciliation test_chat_review_package test_release_readiness`をscriptsで実行：**90件成功、失敗0・skip0、終了0**。coverage強化後の最終内容でも再実行し90件成功。release単独10件、準備単独32件も成功。変更5ファイルのcompileall成功。
- ローカル全回帰 `python3 -m unittest discover -s scripts -p 'test_*.py'`は取得済みの部分環境で740件、failure1/error25/skip4、終了1。未取得の血統原票、過去snapshot、Git履歴などへの依存が残る。これを最新全回帰成功とは扱わない。実ファイルNOT_RUNの共通validator拒否も直接確認した。
- acceptance.jsonはNOT_RUNのまま。最新全回帰成功と標準受入生成、release再生成、通常/統合検査は未完了。今回の2欠陥に対する関連回帰成功と、PR全体の未完了は区別する。

- 続けて部分取得環境で `python3 scripts/run_cycle04_acceptance.py --write` を実際に実行：740件、failure1/error24/skip4で終了1。結果変換原票の追加取得でerrorが1件減ったが、他の原票・履歴不足が残る。コマンド前後のacceptance bytes一致をassertし、NOT_RUNが保全されたことを確認（検査wrapper終了0）。標準スクリプトは未実行ではなく**実行失敗・PASS未生成**であり、成功した受入生成は引き続き残件。


## 最新mainの期間延長との整合（2026-10-14）

- 反映main：`52e666b5406bc44700b0426ea2aa337f744b5d44`（PR86）。本書の以前の4開催日・10/25終了という記載は旧基準の履歴とし、今後の実装・受入は本節を優先する。
- 第4は10/17・18・24・25・31・11/1の6開催日。10/17〜25は東京・京都・新潟、10/31・11/1は東京・京都。予定192Rを依頼scope・実測へ代用しない。
- mainの期間契約、開催場制限、期間終了のJST境界、登録・集計・追加期間テストを取り込み、本PRの修正を保持して共通ファイルを統合した。各PRは独立したまま、他の未マージPRの実装を取り込まない。
- 期間整合時点では2026-11-01以降へ延期していたが、2026-10-14 19:00 JSTの利用者指示で延期を撤回。現在は直ちに実装・検証を進める。3系統CIを実行し、対象SHAと結果を確認する。
- 全枝のacceptanceはNOT_RUN。旧source_manifestは参考情報であり成功証明ではない。releaseは取得済みmainの固定情報を保持するが、本PR統合後のbytesを認証しない。ソースhashを手動追従させず、標準受入成功後に標準生成コマンドで再生成する。
- 作業中に予想原本・receipt・公式本文・結果・回顧が追加されても保全する。回顧内容とデータ照合は先行可能。正式算入・サイクル完了は修正版で再検査し、発走前証跡を後付けしない。
- 再開順序：最新main・追加記録の確認→先行PRの結果適格性/Shadow証跡/最終状態/完了判定の順に統合→各段階で全回帰と標準受入生成→release生成→通常/統合検査→CI→レビュー・マージ判断。修正作業は第4の収集完了を待たずに進める。実測のサイクル終了審査は最終日の全回顧後に行い、コード受入とは分ける。
- 本整合の限定ローカル回帰：73件成功、失敗0・skip0。これは全回帰・標準受入・Git実main統合試験・CI成功ではない。
- 実行コマンド（当該候補のローカル取得ルート）：`PYTHONPATH=scripts python3 -m unittest test_cycle04_period test_cycle04_acceptance test_cycle04_workflow test_release_readiness`。終了0。変更Pythonファイルのcompile検査も成功。

## 実施時期の変更 — 2026-10-14 19:00 JST

- 利用者が第4サイクル後・11/1以降への延期を撤回。今から修正・残件検証を進める。本節が以前の延期方針に優先する。
- 順序はPR82→83→84→85。最新mainと先行修正へ整合し、全回帰・標準受入生成・release再生成・通常/統合検査・レビューを進める。3系統CIを実行し、対象SHAと結果を確認する。実装・ローカル検証・CIを進める。
- マージ判断は検証結果に基づく。今から実施する指示を、未検証PASSへの変更や即時マージの指示として扱わない。
- 第4の6開催日・11/1までの収集日程は維持する。修正の受入に第4実測の完了を要求しない。既存原本と追加される予想・結果・回顧・receiptを保全する。

## 標準コマンドによる実受入・release再生成（2026-10-14 19:09 JST以降）

- Git cloneが今回成功し、原票・PDF・全Git履歴を含むeda-hub/horse-manを取得。対象branchはfix/p1-official-result-eligibility、開始HEADは89922388fc4ab9f716486845cc34c8a2d6c4117e、取得済みorigin/mainは52e666b5406bc44700b0426ea2aa337f744b5d44。AGENTSを読戻し、前回と同じPython検査・GitHub connector反映を継続。既存予想・receipt・結果は変更していない。
- 初回全回帰 `python3 -m unittest discover -s scripts -p 'test_*.py'`：757件、失敗0・skip0、終了0。`python3 scripts/run_cycle04_acceptance.py --write`も757件成功してPASS生成。手動のhash追従ではない。
- 最初のrelease生成・通常検査は成功したが、統合検査が候補の新しい固定対象要件を旧mainへ適用してcoverage不足で停止した。`check_integration_acceptance.py`を修正し、取得済みmainの実スクリプトをそのworktreeで実行する。その後候補の共通受入validatorでもmainのPASS・skip・coverage/hashを照合する。未検証mainを未マージ正常拒否と混同しない回帰を追加。候補のrequire-main条件は緩めない。
- 修正後 `python3 -m unittest discover -s scripts -p 'test_release_readiness.py'`：11件成功。最終内容で `python3 scripts/run_cycle04_acceptance.py --write`：**758件、失敗0・skip0、終了0**。全回帰を実行した成功出力からacceptanceを生成。受入source144件。
- その後 `python3 scripts/build_v170_manifest.py`：終了0、release source164件。acceptance.jsonを固定対象として包含。`python3 scripts/check_cycle04.py`：終了0、準備整合成功、実測0/6日。`python3 scripts/run_release_readiness.py`：終了0、atomic_contract_verified=true、operational_ready=false（未マージ候補）。
- CIの通常系と同じ `check_prediction_compliance.py --audit`、`verify_prediction_persistence.py --audit`、`check_cycle03.py --require-data --require-complete`、`build_cycle03_review.py --check --require-complete`、`recommendation.py --audit`を実行しすべて終了0。第3の7/7日整合と推奨監査を確認。通常監査は過去証跡を新規認証しない。
- `python3 scripts/check_integration_acceptance.py --full --expected-main-sha 52e666b5406bc44700b0426ea2aa337f744b5d44`：**終了1、acceptance source coverage missing**。候補の証跡ではなく、取得済みmainの保存受入が期間延長後も741件PASSの旧証跡であるため。main証跡はscripts/test_cycle04_period.pyを含まず、記載済みsourceにも10件のhash不一致を実Git bytesで確認（00_core、50_review、README、forward-plan、cycle04_operations、cycle_04契約、標準テンプレート、check_cycle04、class_transition_shadow、本回帰）。mainの古い受入をPASSと認証せず拒否した。mainを無断変更していない。
- `python3 scripts/run_release_readiness.py --require-main`：終了1、未マージ候補として正常拒否。main未統合を理由に開始要件を緩めない。
- セルフレビュー：差分は統合checker・回帰・標準生成acceptance/release・本書のみ、diff --check成功。一時ログをPRに含めない。当時のCIは未実行。
- 今回の3残件のうち、全回帰成功からのPASS生成・release再生成・通常検査成功は完了。実main統合検査成功はmain側の受入更新/修正統合に依存して残る。取得済みmainの成功認証を捏造せずDraft継続。

## CI実行方針の訂正 — 2026-10-14 19:23 JST

- 利用者指示により、CIを実行しない・再実行しない・11/1まで待つという指示を撤回した。今後のコミットにCIスキップ指定を付けない。
- 最新の対象SHAで3系統CIを実行し、結果・ログ・対象SHAを確認する。過去の未実行・利用上限・0ステップ失敗は履歴であり、今後の実行禁止条件ではない。

## 統合受入の成功確認（2026-10-14 19:28 JST以降）

- 利用者の統合受入成功要求に沿い、旧main証跡だけを独立PR87で修復。mainのコード/原票/PDF/全Git履歴を使い `run_cycle04_acceptance.py --write` で747件・失敗0・skip0の実成功から再生成。build_v170_manifest.pyも実行しreleaseが同一bytesであることを確認。変更は受入JSONのみ。候補758件の証跡をmainへコピーしていない。
- PR87 head b5e3debda689de9a7159c9256f9f16f4f0849b8d の統合38550176813・台帳38550176863・血統38550176885がすべてsuccess。実受入の747件PASS、追加期間テスト包含を読戻し、候補の厳格validatorでも正常照合を確認。その後PR87をmainへ統合：509368351cc45046fcd524b9ac4905a5a40b6b8e。
- PR82の統合38549491427を再実行しsuccess（job115806835563）。ログの実JSONで、上記実mainのoperational_ready=true、候補はUNMERGED_CONTRACT_REJECTED/operational_ready=false、monitored_sources_unchanged=true、合成758件PASS・失敗0・skip0を確認。台帳38549491383・血統38549491331もsuccess。対象候補SHAは9f79f9b5939514e80f28acb673fb4c9f24c18e8a。
- 修復済み実mainを候補へ履歴保持で取り込む。競合はmain747件と候補758件の受入JSONだけ。実候補コードで標準受入を再実行し758件成功、その後release再生成と通常第4/release検査も成功。生成acceptance/releaseは候補の以前の成功出力と同一bytesであり、main証跡との混合・手動hash追従はしていない。
- 開始判定の拒否条件は維持し、未検証mainを合成の成功証跡へ置換していない。今回の修復と実CI成功により、以前の実main統合検査失敗は解消した。PR82のmainマージは別途レビュー判断とし、修復PR87以外をマージしていない。
