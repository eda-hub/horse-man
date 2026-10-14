# P2：回顧の必須項目と独立集計の修正実施計画

- 作成日：2026-10-14（JST）
- 作業branch：`fix/p2-review-metrics`
- 優先順位：P2の1番目。サイクル終了審査までに実装・受入する。
- 状態：2026-10-15に実装・合成受入原本固定まで完了。最終PRの既存CIとレビュー待ち。実測レース/Owner承認/性能昇格は実行していない。

## 問題・根拠・修正境界

現行`cycle04_workflow.review`と`check_cycle04.validate_day`はerror_classification/non_degradation/next_validationを要求するが、manual 50_reviewの良好部分保全を保存必須にしていない。`cycle04_completion`はprotected_good_parts欠落をreview_owner_gapsへ出す。summaryには確信度・入力充足・午前午後・初回最終変化の集計がある一方、無印好走・変更根拠別成績・推奨失敗分類の接続が不足する。

目的は既存Owner規約を標準writer→validator→日別/サイクル集計→回顧資料→終了審査へ接続すること。確率モデル・推奨生成・性能昇格の条件を変更しない。

## 実装契約案

1. 新規回顧では、保護・再検証・改善対象を明示する。各項目は状態と理由を持ち、該当なしも理由付きで保存する。protected_good_partsは既存参照を保ち、非空の保護内容または明示的な該当なし理由を表現する。自由文の空文字で必須項目を満たした扱いにしない。
2. 未評価はPENDINGと必要入力を保持し、完全回顧の宣言を拒否する。ただし保存済み予想・公式結果の保全を止めない。回顧下書きと完了宣言を分離し、回顧内容の追記・訂正は独立履歴へ保存する。既存review済み原本を上書きしない。
3. 無印は各固定phaseの当時のmarksから判定する。結果の1着・2着・3着内を別々に集計し、取消/中止/同着は公式変換規約を使用する。「好走」の新しい人気・着差閾値は作らない。正式な合成指標が必要でOwnerに定義がなければ利用者確認まで未定義として残す。
4. 初回→最終の変更を固定gate SHA/baseline/cutoffへ結合し、変更根拠の状態（事前根拠確認済み、根拠不足、未評価）と固定引用を保存する。「強い新事実」は結果から自動判定せず、Ownerの事前根拠分類を参照する。初回のみ・同順位・複数FINALは別扱いにする。比較phase/revisionの選択を明示し、混在させない。
5. Recommendationは正式な固定推奨・全頭公式結果から、軸崩れ・着順不一致・相手/第三馬漏れを独立分類する。複数原因は併記可とし、ラベル集計の重複とユニークレース/券の分母を別表示する。NO_RECOMMENDATION/EXPLICIT_MARKS_ONLY/PENDINGを不的中0標本へ入れない。価格・実購入・払戻は不要。
6. 各指標に対象、適格、算入、欠測の集合・件数・理由・必要入力を付ける。0適格はnull。旧記録の新項目欠落は履歴不足とし、現在の分類を遡及捏造しない。正常一巡とOwner評価完了の境界を契約に記載する。

## 修正対象

- scripts/cycle04_workflow.py、check_cycle04.py、cycle04_completion.py：保存と同一共通回顧検査・独立集計・完了/不足表示。
- scripts/chat_review_package.py、chat_improvement_handoff.py：分類と原本参照を引継ぐ。
- scripts/recommendation.py：既存settleを再利用。集計分類を推奨生成へ逆流させない。
- test_cycle04_workflow.py、test_cycle04_acceptance.py、test_cycle04_completion.py、test_chat_review_package.py、test_chat_improvement_handoff.py、必要な専用集計テスト。
- docs/validation/contracts/cycle04_operations.md、標準テンプレート、終了資料。manualの意味を変える必要がある場合はOwner変更を別途明示する。

## 小項目・コミット単位

| 項目 | 実装と検証 | 日本語コミット案 |
|---|---|---|
| 01 | 現行必須項目・指標対応表を作り、保護欠落と未接続分類の再現fixtureを追加 | 回顧の必須項目と集計不足を回帰化 |
| 02 | 共通schema/検査・下書き/完了・旧記録不足・追記履歴を実装 | 回顧の保護と評価状態を標準保存へ接続 |
| 03 | 無印結果・事前変更根拠・推奨失敗を分母付き独立集計へ接続 | 回顧の原因別成績と欠測を独立集計 |
| 04 | 回顧資料・改善引継ぎ・終了判定・契約・テンプレートを整合 | 回顧集計とOwner不足の運用手順を統一 |
| 05 | 標準受入/manifest/統合/CIを成功させ対応表を記録 | 回顧項目と集計の統合受入を固定 |

## 受入条件・異常系

- 合法な全件回顧はwriter/checker/summary/packageで同じ判定。未最終・低確信・推奨なしを回顧scopeから落とさない。
- 保護等の欠落・空理由・結果後に作った事前根拠・異phase参照・別レース結果は完了/正式指標へ算入しない。
- 複数原因、取消、同着、初回のみ、順位不変、複数最終、欠測、全件未適格を検査し、既存精度と推奨分母の回帰を維持する。
- 旧記録は読取可能で、不足が明示される。正式成績・予想・結果のbytesを勝手に修正しない。
- 新分類の意味がOwnerに存在しない場合は未確定点と影響を利用者へ示し、依存実装だけを止める。

## 実装時の実績表

項目／commit SHA／変更path／実行コマンド／期待値／実結果／残件を以下の2026-10-15実績表に記録する。未実施の実レース/人間審査を成功とは表現しない。

## 共通作業・統合規約

- 対象：`eda-hub/horse-man`。基点main：`984ee26fac173af8c7f8c4e5b7f5ab4df844bf1a`。現行版v1.7.0、PR82〜85統合済み。
- 本書作成時の依頼は計画書作成までだったが、2026-10-15にPR88の実装指示を受けてコード修正に着手した。実レース記録・適格性訂正・mainマージは対象外。本書を現行Productionルールとして使用しない。
- 再開時に最新main、AGENTS、manual README、関係Owner、本書、対象branchを読戻す。基点後の変更と実測追加を確認し、従来のGitHub接続・作業記録を踏襲する。
- 統合順は回顧項目・集計→公式発走変更→旧履歴整理。後続は先行PR統合後の最新mainへ追従し、共通validator・契約・テストを手動で整合する。公式時刻変更が実際に発生した場合は、その課題を先行してよい。
- Production/Shadow/任意市場、Prediction/Recommendation/購入を分離。価格・実購入・払戻を標準入力へ戻さない。第4の6開催日・11/1までの収集日程は維持する。実測未取得はnull・不足とし、予定192Rやfixtureを実績にしない。
- PR82〜85の公式本文照合、Shadow原本/receipt、phase履歴・未解決累積、初回FIX再照合、集計Git読戻しを保持する。旧原本・receipt・固定予想・結果・比較を消さず、発走前証跡を後付けしない。
- 小項目ごとに実装・異常系/正常系検証・セルフレビューを完了し、日本語でコミットする。実績表へcommit SHA、変更path、コマンド、対象SHA、実結果、残件を追記する。
- 最終ソースで `python3 scripts/run_cycle04_acceptance.py --write` を成功させ、`python3 scripts/build_v170_manifest.py` でreleaseを生成。`python3 scripts/check_cycle04.py`、`python3 scripts/run_release_readiness.py`、`python3 scripts/check_integration_acceptance.py --full` と既存3系統CIを確認する。CI禁止・日付待ち・スキップ指定はしない。
- 標準受入は全回帰失敗0・skip0の実出力だけをPASSにする。手動hash追従や先行PRの成功証跡コピーをしない。候補branchの `--require-main` 拒否と、取得済みmainの開始認証成功を区別する。
- 過去の通常checker不合格は、最新コードの回帰失敗とは切り分けて原因と対象を記録する。黙ってauditへ切り替えて全正常と報告せず、合成試験と実運用・過去記録の状態を区別する。
- 切り戻しは変更commitのrevertと契約/受入/releaseの再整合で行う。新しく保存された記録を削除しない。schema変更には旧記録の読取・不足表示を残す。


## 2026-10-15 実装実績（追記）

対象：`eda-hub/horse-man`、`fix/p2-review-metrics`、main基点 `984ee26fac173af8c7f8c4e5b7f5ab4df844bf1a`。合成回帰の結果は実競馬の成績・Owner採否を意味しない。

| 項目 | commit SHA（先頭8桁） | 保存した主なpath | 実施・結果／残件 |
|---|---|---|---|
| 01 | d4bbf61b, 1876f476 | `docs/proposals/2026-10-15_p2_review_metrics_mapping.md`, `scripts/test_cycle04_review_metrics.py` | 対応表・Owner不足/下書き/改訂/複数原因の合成回帰を追加。 |
| 02 | d439aaf6, 0ae9dc1f, f4c4df7c, ae9560f7 | `scripts/cycle04_review_metrics.py`, `scripts/cycle04_workflow.py`, `scripts/check_cycle04.py` | 共通schema/検査、DRAFT/COMPLETE、追記原本、事前根拠固定をwriter/checkerに接続。 |
| 03 | 774a246f, 600f1b1b | `scripts/cycle04_review_metrics.py`, `scripts/chat_review_package.py` | phase別無印、変更根拠、推奨失敗の独立分母と欠測を作成。複勝対象着数を公式結果から取得。 |
| 04 | 30f2b3ee, 5bab043f, b627107a, d7252013 | `scripts/cycle04_completion.py`, `scripts/chat_improvement_handoff.py`, `docs/validation/contracts/cycle04_operations.md`, `docs/validation/templates/next_cycle_execution_v17.md` | Owner不足を終了判定・回顧資料・運用契約へ接続。テンプレート `cycle04_review_entry_v2.json` を新設。 |
| 05 | 43370aae, 4456bf0e | `docs/validation/reviews/cycle_04/acceptance.json`, `docs/validation/contracts/v170-release.json` | Actions run 38656793421（job 116168349527）の実原本をGitHubへ保存。全818回帰、失敗0、skip0、合成受入PASS。正式切替/実レースは非認証。 |

テスト対応：`test_cycle04_result_eligibility.py`、`test_cycle04_workflow.py`、`test_cycle04_completion.py`、`test_chat_review_package.py`、`test_chat_improvement_handoff.py` に回帰追加・契約更新。GitHub Actionsの`cycle-ledger`では更新途中の旧ハッシュのため後段が失敗したが、commit `d7252013` 対象の `python3 -m unittest discover -s scripts -p 'test_*.py'` は成功。統合は実際の`--write`とrelease生成の出力を待ち、手書きのPASSや先行PRのhash転記をしない。

未確定な新指標：Ownerにない「無印好走」の合成閾値と「強い新事実」の事後自動分類は設けず、合成指標は `null` / 理由で保持。独立1着・2着・3着内、および固定根拠の状態別件数は提供する。


### 実行コマンド・SHAと受入読戻し（2026-10-15）

実際に GitHub Actions の `integration-acceptance` job（run `38656793421`）で実行した順序：

```bash
python3 scripts/run_cycle04_acceptance.py --write
python3 scripts/build_v170_manifest.py
python3 scripts/check_cycle04.py
python3 scripts/run_release_readiness.py
python3 scripts/check_integration_acceptance.py --full
```

- `run_cycle04_acceptance.py --write`：`tests_run=818`、`failures=0`、`skipped=0`、`mode=SYNTHETIC`、`live_race_count=null`。coverage: 149入力source。
- `build_v170_manifest.py`：v1.7.0 / 169対象source。両JSONはrunのstdoutに固定byteのBase64を出力し、それを復号してGithub connectorで直接更新した（手書きの成功・hashなし）。
- `check_cycle04.py`：第4の日別実測0/6日、未開始、正常一巡は未完了。固定受入はPASS。実レースのPrediction適格性は主張しない。
- `run_release_readiness.py`：v1.7.0の原子的固定参照を検証、mainの契約変更とは分ける。
- `check_integration_acceptance.py --full`：取得済みmainの開始認証と候補branchの差分判定、全合成回帰と第3再計算が成功。
- 固定原本コミット：受入 `43370aae5761d25bb9e47e109cd13ac32347b69c`、release `4456bf0edbb42668fdb3e81058a7f9e012113cbf`。
- 受入実測用の一時的な `.github/workflows/check-integration-acceptance.yml` の変更は差分から撤去した。Production Ownerと既存3 CIを弱めない。
- 「無印好走」合成閾値、および「強い新事実」の採用判定は既存Ownerに新基準がないため未定義。独立集計自体は完成、正式な追加閾値はOwner判断があるまで保留。
