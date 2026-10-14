# P1：初回から最終へのShadow状態管理の修正実施計画

## 目的・対象・状態

- 作成日：2026-10-14（JST）
- 作業branch：`fix/p1-final-shadow-state`
- 調査基準main：`b288bc1f39f61d68c6cf536608c11689575315e8`
- 状態：01〜04のコード・文書変更をブランチへコミット済み／実行受入・先行PR統合は未完了。
- 目的：初回Shadowの履歴を保全し、最終時点の比較状態を正しいgateへ結び付け、Shadow状態の持越しで正常な最終Prediction/推奨登録が失敗しないようにする。
- 対象外：Shadow仮説の削除/昇格、Production再予想、推奨ロジック変更、実測性能の受入。

## 再現・原因・影響

`cycle04_workflow.record_prediction` は最新のPrediction gateへrowを更新するが、Shadow項目が非空の場合だけ日別Shadow KPIを更新する。初回ShadowがELIGIBLE、最終gateのShadow項目が空なら、日別の古いELIGIBLE状態が残る。一方、`check_cycle04.validate_day` は最新Prediction gateのShadow状態と突合するため不一致になる。

一時fixtureで初回の独立保存済み適格Shadowを登録し、別pathの正常な最終gate（Shadowなし）と正常な固定推奨を渡したところ、`KPI gate not eligible` で最終登録が拒否され、final_scopeは空のまま残った。初回履歴を消さず、Production/推奨を比較状態から独立させる必要がある。

## 修正方針

1. Shadowを単一の「最新row状態」だけに押し込まず、INITIAL/FINAL・固定Prediction gate hash・baseline・Shadow項目に結び付けた履歴として保持する。
2. 本計画の集計単位は既存のレース単位を維持する。日別Shadow KPIは「最新Predictionに対応する明示的な適用状態」を表し、初回の比較成績は独立履歴から追跡する。項目/phase別の追加追跡で同一レースを重複計上しない。
3. 新規履歴にはphase、固定gate path/hash、基準参照、項目IDと各状態/証跡を保存する。既存prediction_historyの固定gate参照を再利用し、同じgateの重複登録は冪等にする。
4. 最終が明示的に適用なしなら、最新KPIのtarget/eligible/ineligible/pending/reasonsを一貫して更新する。単に空配列だったことだけで、既に該当していた比較の未実施を適用なしに見せない。entryには適用判定と理由を明示し、該当判定は既存仮説の条件に従う。未確認は保留とする。
5. 初回適格→最終対象外、初回適格→最終保留/不適格、初回対象外→最終該当を区別する。最終の不足はその時点のShadowへ局所化し、独立保存済みProduction/推奨を失敗へ置換しない。
6. 初回比較が最終で実施されなくても、保存済み初回原本・receipt・固定gate・当時状態を削除しない。初回と最終の比較ペアを混ぜず、基準/cutoffが違うペアを同一比較として合算しない。
7. 既存記録の新履歴化が必要なら、保存済み固定gate/historyから確認できる事実のみを読取で構成する。未保存の適用判定やreceiptを後から作らず、不足は明示する。

## 実装対象・境界

| ファイル | 変更内容 |
|---|---|
| scripts/cycle04_workflow.py | phase別Shadow履歴と最新KPI状態を一貫更新。FINAL登録の局所性・冪等性を維持 |
| scripts/check_cycle04.py | 履歴の固定hash・最新状態・適用理由・KPI集合を共通検査。初回を最新gateで認証しない |
| scripts/chat_entry_assembly.py | previewとwriterで同じ適用判定・履歴更新を使う |
| scripts/chat_review_package.py | 初回/最終の履歴・不足を分けて出力 |
| scripts/chat_forward_coverage.py、chat_calibration_review.py、class_transition_shadow.py | 対象phaseの固定gate参照が同じ比較基準を指すか確認。必要箇所だけ修正 |
| scripts/test_cycle04_workflow.py、test_cycle04_acceptance.py、test_chat_entry_assembly.py、test_chat_review_package.py | phase遷移・不正履歴・原子的保存の回帰 |
| docs/validation/contracts/cycle04_operations.md、templates/chatgpt_prediction_task.md | 適用判定、履歴、最新KPIと比較履歴の区別を記載 |

先行するShadow証跡修正の強いvalidatorを再利用する。参照を残すだけで証跡検査を省略しない。共通moduleの変更・日別契約の追加項目は先行結果修正とも整合させる。

## 小項目別の実装・コミット計画

| 小項目 | 作業と完了条件 | 日本語コミット案 |
|---|---|---|
| 01 | 初回適格→最終ShadowなしでFINAL登録が拒否される現行挙動を回帰化し、phase遷移表をテストへ固定 | 初回Shadow状態が最終登録を阻む問題を再現 |
| 02 | phase/gateに結び付いた履歴と明示適用判定を実装。古い原本は保持 | 初回と最終のShadow状態を固定履歴で分離 |
| 03 | writer/validator/previewで最新KPIを一貫更新し、Production/推奨の登録独立性を確認 | 最終登録とShadow最新状態の整合を修正 |
| 04 | 回顧・比較読取入口へ履歴を接続し、重複計上と基準混在を防止。運用契約を更新 | Shadow履歴の回顧参照と運用手順を整備 |
| 05 | `c47ec1316527888d724ba312d6620d5c55ebd07f`, `2832f86be53ecb34d046d4284571490f82159c44` | PR #82・#83を含むmain取込み、全回帰、合成受入PASS生成、release manifest再生成、通常・原子的・取得main統合受入 | `python3 -m unittest discover -s scripts -p 'test_*.py'`、`python3 scripts/run_cycle04_acceptance.py --write`、`python3 scripts/build_v170_manifest.py`、`python3 scripts/check_cycle04.py`、`python3 scripts/run_release_readiness.py --root .`、`python3 scripts/check_integration_acceptance.py --full` | **実行成功：783件、失敗0、skip0**。標準コマンド生成の`acceptance.json=PASS`、release manifest165件を保存。一時CI run `38561404284`成功。最終ブランチCI3系統の確認のみ継続。 |

## 受入条件

- 初回適格→最終明示対象外でも、正常な独立Prediction/推奨のFINAL登録が成功し、初回の比較履歴が残る。
- 初回適格→最終保留/不適格では、最新Shadowの不足が正しく表示され、Production/推奨の独立保存成功が維持される。
- 初回なし→最終該当、同じ証跡の再登録、複数項目で適格/不足が混在する場合も、各状態・対象集合・理由が一致する。
- 適用判定なしの空配列、根拠のない対象外化、古いELIGIBLEの持越し、履歴hash差替え・巻戻し・基準混在は拒否または理由付き保留となる。
- 予想・推奨・入力・receiptの既存bytesは不変。プレビューとwriterの判定が一致し、失敗時は旧台帳を保全する。
- 最新レース単位KPIと初回/最終の比較履歴を混同せず、同一レース・同一ペアを二重に集計しない。

## 検証・実装結果の記録

最低限 `test_cycle04_workflow`、`test_cycle04_acceptance`、`test_chat_entry_assembly`、`test_chat_review_package`、`test_chat_helper_market_independence`、`test_chat_forward_coverage`、`test_chat_calibration_review`、`test_class_transition_shadow` を実施する。全回帰・合成受入・release/統合検証は共通規約に従う。

実装時に本書へ「小項目／commit SHA／変更path／実行コマンド／期待結果／実結果／残件」を追記する。実施状態の詳細は末尾の実装記録を正とする。

## 共通の作業・統合規約

- 対象は常に `eda-hub/horse-man`。本書は実装計画であり、現行Productionルールの代用にしない。
- 計画書作成時の依頼範囲は計画までだったが、2026-10-14にPR #84の実施を新たに指示されたため、対象の実装修正を開始した。実レース記録作成・性能昇格は依頼されていない。
- 既存v1.7.0の予想骨格、価格不要推奨、Production/Shadow/任意市場の分離、旧v1.6.1履歴を維持する。実購入・価格・払戻・実測性能を標準完了の必須入力に戻さない。
- 合成fixtureは一時領域で検査し、実日別台帳・未来の事前証跡・実測0を作らない。第4開催の実測、過去研究の網羅、性能昇格を本修正PRのマージ条件にしない。
- コミット・PR説明・作業記録は日本語。各小項目を実装・対応テスト・セルフレビューまで行い、小項目ごとにコミットする。未完了項目を完了と記載しない。
- 実装開始時に本書、AGENTS、最新main、対象branch、関連Ownerと対象コードを読戻す。本書の基準以降に変更があれば差分を確認して計画を更新し、確認した再現・受入条件を維持する。
- 4件の統合順は「結果の適格性 → Shadow証跡 → 初回/最終Shadow状態 → サイクル完了」。各計画は単独の基準から作成するが、後続の実装では先行修正を取り込んだ最新mainを反映してから着手する。共通ファイルの変更は機械的なours/theirsで解消しない。
- 対象コード・テスト・運用契約を変更した最終内容で `python3 scripts/run_cycle04_acceptance.py --write` を成功させ、その後 `python3 scripts/build_v170_manifest.py` でrelease manifestを再生成する。先行PRの受入・manifestを単純にコピーしない。
- 全回帰、通常checker、合成受入、release整合、統合受入と3系統CIを確認する。開始認証の `--require-main` は未マージの候補branchを認証するために改変しない。統合受入は取得済みmainと候補branchの契約一致/未マージ拒否を正しく区別する。
- 必要な過去Git履歴・原票・PDF依存を取得できない検査は実行不能として残す。失敗をコード欠陥と混同せず、未実行を成功にしない。完了報告には実行コマンド・結果・CI対象SHA・残件を対応付ける。
- 修正の切り戻しは対象変更のrevertで行い、保存済み予想・receipt・結果・比較履歴を削除しない。後続PR統合後は依存を確認し、関連契約・受入・manifestを同時に整合させる。

## 実装記録（2026-10-14 JST、PR #84）

本表の「追加済み」はGitHubブランチへの保存・読戻しを指す。**Python回帰の実行成功・CI合格を意味しない**。先行PR #82/#83はいずれも実装中かつ未マージであり、共通ファイルの最終統合を未実施のまま完了としない。

| 小項目 | 代表commit SHA | 変更path・内容 | 検証コマンドと期待結果 | 実結果・残件 |
|---|---|---|---|---|
| 01 | `b2cc23531b25494bbec4d2f007399d1eed9dcd38` | `scripts/test_cycle04_workflow.py`。初回Shadow適格→最終Shadow空が旧実装では失敗する回帰、明示対象外・保留の遷移を追加 | `PYTHONPATH=scripts python3 -m unittest test_cycle04_workflow`：最終独立保存成功・初回固定原本存続 | テスト追加コミット済み。ローカルPython実行環境に対象private repoを取得できず実行未確認。 |
| 02 | `f34203c2ab3c078b2563f833631777a7288f0775`, `81af0a4a4f7fbd8dbca319f5011c0b09b697ae51` | 新規`scripts/cycle04_shadow_state.py`、`scripts/cycle04_workflow.py`。明示適用判定・項目別取扱い・phase/gate SHA・baseline/cutoffと証跡を固定した追記型履歴を保存。最新KPIは履歴と分離 | `PYTHONPATH=scripts python3 -m unittest test_cycle04_workflow test_cycle04_acceptance`：最新KPI持越しなし、旧履歴改ざん拒否、同一gate冪等 | コード追加済み。複数項目・差替え・旧履歴欠落・最終不適格等の追加試験もコミット。テスト未実行。 |
| 03 | `4317eb14a2615825f38255a398a6924cfa7a8d4e`, `d3e0cf9325c7182e81cdbddaf68e94fca7090b97` | `scripts/check_cycle04.py`・writer・`scripts/test_chat_entry_assembly.py`。履歴hash・状態・KPI集合を照合、適用なしなら最新Shadowをクリア、保留と不適格の最新状態を認証。previewとwriterは同じ`record_prediction`を通す | `PYTHONPATH=scripts python3 -m unittest test_cycle04_workflow test_chat_entry_assembly test_chat_helper_market_independence`：FINAL登録のProduction/推奨独立性、preview無書込み | コード・試験追加済み。テスト未実行。 |
| 04 | `14280e8cf090b9646b7ea793581a8a7296189909`, `4d2b58955adbd914128429b4c9c80a643185441c`, `1045f95f00432ebb0e137e380f48ec0c66471587` | `scripts/chat_review_package.py`、`chat_forward_coverage.py`、`chat_calibration_review.py`、関連テスト、`docs/validation/contracts/cycle04_operations.md`、`docs/validation/templates/chatgpt_prediction_task.md`。phase別履歴・旧履歴不足・固定比較キー、提出時点のgate/baseline/cutoff照合、重複・混在防止 | `PYTHONPATH=scripts python3 -m unittest test_chat_review_package test_chat_forward_coverage test_chat_calibration_review test_class_transition_shadow`：初回/最終を独立回顧、欠測や重複を非適格として扱う | コード・契約・試験追加済み。テスト未実行。 |
| 05 | 未作成（統合受入成功を示すSHAなし） | 全回帰→合成受入`--write`→release manifest再生成→3系統CI→統合受入 | `python3 -m unittest discover -s scripts -p 'test_*.py'`、`python3 scripts/run_cycle04_acceptance.py --write`、`python3 scripts/build_v170_manifest.py`、`python3 scripts/check_cycle04.py`、`python3 scripts/check_integration_acceptance.py --full`。すべて成功し、生成物とCI対象SHAの一致を確認 | **未完了**。private repoの完全なcheckoutを現環境で取得できずPython回帰は未実行。当時のActionsは利用上限が報告されており、3系統の`failure`はコードテストの成否を表さない。成功受入/manifestの再生成なし。 |

### 補足の追加修正

- `32e8006805dd3297053dff58744884f7c936c7ca`：前向き網羅のassessmentを、最終の可変参照ではなく提出比較の固定phase/cutoffに結合。
- `bd1dcf4dc41756c809078b9f7790c1a67529faeb`：先行PR #83が導入する未来時刻のShadow適格拒否に対応し、合成fixtureだけ固定時計を使用。実記録は生成しない。
- `f3f585e1847e437eb521fe8824c5eae2298b13e1`：合成Shadow比較原本の保存時刻をProduction固定後へ修正。
- `ebf6636dc054d5d1cc7270c85201a996288ef0bf`：初回対象外→最終適格、および初回適格→最終不適格の回帰ケースを追加。
- 最新のコード状態はPR #84 headのコミットを正とし、途中SHAでCIを代用しない。

### 最終確認したActions実行（実装記録commit時点）

- 対象head SHA：`feb473de8bb2c6fa6f8cae515a0be3127a1bc6f1`。
- 第3台帳・予想の機械監査：<https://github.com/eda-hub/horse-man/actions/runs/38523410281> — `failure`。
- 新旧契約の統合受入：<https://github.com/eda-hub/horse-man/actions/runs/38523410278> — `failure`。
- 血統原票の監査：<https://github.com/eda-hub/horse-man/actions/runs/38523410280> — `failure`。
- 各runのjobs APIは`completed/failure`と、ジョブの実行ステップ一覧が空であることを返す。ジョブログ取得は404 `BlobNotFound`。利用者から**GitHub Actionsは利用上限のため2026-11-01まで利用できない**と確認済みであり、3系統の失敗表示はPythonテスト不合格を示さない。
- 本記録を追記する後続commitは別SHAとなるため、その後も最新headに対するCI確認が必要。

### 統合時の必須作業・未解決

1. **先行順序**：#82（公式結果の適格性）、#83（Shadow発走前原本）を`main`へ統合後、このブランチで最新`main`差分と共通ファイルを手動照合する。#83の強化済み`forward_shadow_evidence`を外さず、当時の固定原本・hash・receipt・発走前時刻を保持する。#85（サイクル完了）は本修正の後。
2. **検証環境**：全履歴・依存資料・PDFツールを備えたcheckoutで上記コマンドを実行し、最新head SHAの3系統CIを実行する。実行できない検証は原因と結果を記録し、未実行を成功扱いにしない。
3. **受入・manifest**：先行統合後の最終ファイルで、全回帰と`run_cycle04_acceptance.py --write`をローカルで成功させてから`build_v170_manifest.py`で全hashを再生成し、通常checker、release/readiness、統合受入を確認する。最新head SHAの3系統CIを実行して確認する。`--require-main`は未マージbranchの認証に使わない。
4. **保存保全**：実レース原本、固定Prediction/推奨の既存bytes、過去のreceipt・履歴は変更しない。現時点で完成・CI合格・本番開始・性能昇格を宣言しない。

### CI利用上限の確定記録（2026-10-14 JST）

過去の実行時点では利用上限が報告され、実行ステップが開始していなかった。この記録を現在のCI実行禁止・日付待ちの条件にはしない。3系統CIを実行してログと対象SHAを確認し、成功・失敗・未実行を区別する。


## 最新mainの期間延長との整合（2026-10-14）

- 反映main：`52e666b5406bc44700b0426ea2aa337f744b5d44`（PR86）。本書の以前の4開催日・10/25終了という記載は旧基準の履歴とし、今後の実装・受入は本節を優先する。
- 第4は10/17・18・24・25・31・11/1の6開催日。10/17〜25は東京・京都・新潟、10/31・11/1は東京・京都。予定192Rを依頼scope・実測へ代用しない。
- mainの期間契約、開催場制限、期間終了のJST境界、登録・集計・追加期間テストを取り込み、本PRの修正を保持して共通ファイルを統合した。各PRは独立したまま、他の未マージPRの実装を取り込まない。
- 期間整合時点では2026-11-01以降へ延期していたが、2026-10-14 19:00 JSTの利用者指示で延期を撤回。現在は直ちに実装・検証を進める。3系統CIを実行し、対象SHAと結果を確認する。
- 全枝のacceptanceはNOT_RUN。旧source_manifestは参考情報であり成功証明ではない。releaseは取得済みmainの固定情報を保持するが、本PR統合後のbytesを認証しない。ソースhashを手動追従させず、標準受入成功後に標準生成コマンドで再生成する。
- 作業中に予想原本・receipt・公式本文・結果・回顧が追加されても保全する。回顧内容とデータ照合は先行可能。正式算入・サイクル完了は修正版で再検査し、発走前証跡を後付けしない。
- 再開順序：最新main・追加記録の確認→先行PRの結果適格性/Shadow証跡/最終状態/完了判定の順に統合→各段階で全回帰と標準受入生成→release生成→通常/統合検査→CI→レビュー・マージ判断。修正作業は第4の収集完了を待たずに進める。実測のサイクル終了審査は最終日の全回顧後に行い、コード受入とは分ける。
- 本整合の限定ローカル回帰：80件成功、失敗0・skip0。これは全回帰・標準受入・Git実main統合試験・CI成功ではない。
- 実行コマンド（当該候補のローカル取得ルート）：`PYTHONPATH=scripts python3 -m unittest test_cycle04_period test_cycle04_workflow test_chat_forward_coverage test_cycle04_acceptance`。終了0。変更Pythonファイルのcompile検査も成功。

## 実施時期の変更 — 2026-10-14 19:00 JST

- 利用者が第4サイクル後・11/1以降への延期を撤回。今から修正・残件検証を進める。本節が以前の延期方針に優先する。
- 順序はPR82→83→84→85。最新mainと先行修正へ整合し、全回帰・標準受入生成・release再生成・通常/統合検査・レビューを進める。3系統CIを実行し、対象SHAと結果を確認する。実装・ローカル検証・CIを進める。
- マージ判断は検証結果に基づく。今から実施する指示を、未検証PASSへの変更や即時マージの指示として扱わない。
- 第4の6開催日・11/1までの収集日程は維持する。修正の受入に第4実測の完了を要求しない。既存原本と追加される予想・結果・回顧・receiptを保全する。

## CI実行方針の訂正 — 2026-10-14 19:23 JST

- 利用者指示により、CIを実行しない・再実行しない・11/1まで待つという指示を撤回した。今後のコミットにCIスキップ指定を付けない。
- 最新の対象SHAで3系統CIを実行し、結果・ログ・対象SHAを確認する。過去の未実行・利用上限・0ステップ失敗は履歴であり、今後の実行禁止条件ではない。

## 最新main統合・CI再開指示への対応（2026-10-14 JST）

- 利用者からPR #83のmainマージと、最新mainの取込み・再検証、CI実行の許可が明示された。以前のCI利用停止・11月1日待機の指示は取り消され、CI実行を制限しない。
- 最新main `2d049a636f891debcbe1d955b9bf8419b93df694` はPR #82 → #83を統合済み。PR #84の既存変更と3-way照合し、先行修正の結果適格性、発走前Shadow原本の検査、強化された回顧テストを失わず統合する。mainの他のファイルはそのまま残す。
- 重複したテスト追加・運用追記は両方保持する。先行mainの合成受入769件PASSはPR #84変更後の受入PASSを示さないため、当該PRの `acceptance.json` はNOT_RUNにし、先行source_manifestは参考値として保持する。
- この統合はGitHub Git APIの3-wayテキスト差分で反映し、完全checkoutがない環境でのPython実行が済んだと主張しない。最終headで発火したActionsの3系統を取得し結果とログを照合する。合成受入PASS・release manifest再生成は標準生成コマンドを実行できた場合に限る。
- 以後のCI実行に`skip ci`等の禁止指定を設けない。CIの失敗が利用枠・runner・コードのどれに該当するかはジョブ開始・実ステップ・ログで判定する。PR #84の全受入証跡を確認するまでDraftを保持する。

### PR #83取込後の実証された受入結果（2026-10-14 JST）

- 先行main：`2d049a636f891debcbe1d955b9bf8419b93df694`（PR #82、#83マージ済み）。取込マージコミット：`c47ec1316527888d724ba312d6620d5c55ebd07f`。
- GitHub Actions一時検証run：<https://github.com/eda-hub/horse-man/actions/runs/38561404284>。`run_cycle04_acceptance.py --write`の全回帰 **783件PASS、失敗0、skip0**。生成された合成受入source_manifestは145ファイル。
- 続く標準`build_v170_manifest.py`でrelease原本165ファイルを固定。`check_cycle04.py`、`run_release_readiness.py --root .`、`check_integration_acceptance.py --full`がそれぞれ成功。生成した2ファイルはGitHub Actions botからブランチコミット `2832f86be53ecb34d046d4284571490f82159c44`へ保存・読戻しした。
- 標準生成のために一時使用したworkflow `.github/workflows/pr84-generate-acceptance-temporary.yml` は、生成完了後にコミット `9a386d27e8fe991cfc39a3991ecdca3698a4774d` で削除し、PRの恒久的な変更対象に残さない。元の3系統CIは最新の対象SHAで再実行・結果を確認する。
- 第4の開催日6日と実レースの未実行部分は、本合成受入の合格とは独立に扱う。予想・公式結果・比較receiptを加工せず、mainへの正式マージと性能昇格を先取りしない。

### P2校正出力の初回比較と最終推奨のphase誤結合（2026-10-14 JST）

- 指摘：`scripts/chat_calibration_review.py` が初回比較にも最新のFINAL推奨を結合し、初回9:50／別時点の最終推奨9:51で `recommendation comparison cutoff differs` により校正入力を不当に停止。
- 原因：先行する `chat_forward_coverage.py` は提出比較の固定phaseを識別しているが、校正出力側では最新の日別 `recommendation_gate_path` を全phaseへ無条件に適用していた。
- 修正：固定phaseの参照が一致することを全受理ペアで必須化。INITIALでは最新FINAL推奨にアクセスせず `recommendation_input=null` と適用外理由 `DIFFERENT_PHASE` を返す。FINALでは既存推奨validatorを通し、phase／cutoff／baseline／Production固定証拠path・SHA・IDのすべてが一致するものだけ結合する。
- 回帰：`scripts/test_chat_calibration_review.py` に初回のFINAL推奨非参照・読取専用確認、FINAL正常結合、FINALの9:51時点不一致拒否、固定phase-binding欠落拒否を追加。初回比較の確率・結果・strataと独立推奨の分離を維持する。
- `python3 scripts/run_cycle04_acceptance.py --write` で合成回帰にPASSした後だけrelease manifestを再生成し、全3系統CIと取得済みmainとの統合受入を最新SHAで再確認する。これらの生成結果が未到着の場合は成功と記さない。
- **検証結果**：<https://github.com/eda-hub/horse-man/actions/runs/38564202940> で全回帰787件・失敗0・skip0、標準合成受入PASS・source_manifest145件、release manifest165件の生成、第4通常検査、release原子的整合、`check_integration_acceptance.py --full` がすべて成功。生成物保存コミット `0457013cb7f7288208fe15ee5d6e5c3867b76789`。一時CIは `92d5f7b1f6bc0ed68decdacad6441dc7f5ae61a0` で削除。最終headの3系統CIは別途確認する。
- 初回比較（9:50）と別時点の最終推奨（9:51）を同一証拠として認証しない。初回比較のphaseを維持し、最終推奨は読まずに校正入力を出力する。FINAL対応推奨の固定時点と原本への不整合は引き続き拒否する。
