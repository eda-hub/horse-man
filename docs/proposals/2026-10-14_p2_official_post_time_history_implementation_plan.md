# P2：公式発走時刻変更の修正実施計画

- 作成日：2026-10-14（JST）
- 作業branch：`fix/p2-official-post-time-history`
- 優先順位：P2の2番目。実際の公式変更発生時は先行対応する。
- 状態：実装・合成回帰受入済み。実レースの変更履歴・時刻・receiptは作成していない。

## 問題・根拠・目的

現行register_scopeは既存race/postの再定義を拒否し、day/gate/receipt/結果requestはscheduled_post_time_jstの直接一致を要求する。この保全条件は必要だが、公式変更後の時刻を通常入口から追記し、旧固定予想と結果を同一レースへ結ぶ経路がない。

公式変更を、既存時刻の上書きではなく出所付きの追加履歴として保存する。後から遅延を知ったことによる発走前適格化を防ぎ、時刻変更のない通常系・PR82〜85の固定参照と工程検査を維持する。

## 実装契約案

1. レースごとの独立schedule-change artifactにrace/date、旧/新予定、公式本文の固定path/hash・引用位置、公式掲載時刻（不明はnull）、取得/読戻し時刻、改訂順・前原本hashを保存する。writerは公式本文との一致・対象・時刻順・未来取得・改訂連続性を共通検査する。任意URLや変更フラグだけで真正性を認証しない。
2. 初回登録の予定時刻は保持し、変更参照を追記する。現時点の有効予定時刻は検証済み履歴から算出する。既存Prediction/Recommendation/Shadow gate、本体、receipt、FIX、事前宣言とその期限を書き換えない。
3. 発走前判定は、各保存/読戻し時点までに実際に取得・確認した公式変更だけを使用する。変更取得より前の遅延を仮定してLATE/REPLAYを適格化しない。延長後に新規固定する場合は当時確認済みの新予定に結び付けた独立証跡を作る。変更前の既存証跡と変更後の新規証跡を別履歴として照合する。
4. 変更のない場合は従来の直接一致を維持。変更がある場合だけ、gate/receiptの当時の予定と公式履歴の対応を共通関数で検証する。読戻しが適用予定以後なら拒否。前倒しや変更観測遅延で適格性が確認できない記録は不足/不適格を明示する。
5. 結果本文の公式予定と固定予想の当時予定が異なる場合は、同一race/dateの検証済み変更履歴を必須とする。単に予定一致検査を削除しない。結果取得の発走以後判定にも対応する公式時刻を使用し、旧snapshotを変換し直して上書きしない。
6. 複数遅延、前倒し、取消、中止、翌日延期を区別する。開催日/レース識別変更が同一レースとして扱えるか不明なら利用者・公式資料確認まで保留。cycle_idや依頼scopeを自動移動しない。予想保存の継続と正式適格性の宣言は分離する。

## 修正対象・依存確認

- scripts/cycle04_workflow.py、check_cycle04.py：追記入口、公式scope/予定履歴、共通検査。
- scripts/cycle04_operations.py、check_prediction_compliance.py、verify_prediction_persistence.py、task_completion.py、cycle04_completion.py：既存証跡の当時予定照合。旧v1.6.1へ暗黙適用しない。
- scripts/chat_fact_capture.py、chat_result_conversion.py、chat_result_reconciliation.py、recommendation.py、selection_history.py：発走境界の参照と結果同一性。新規共通moduleの必要性をimport依存調査で決める。
- 運用契約、scope/予想/結果テンプレート、test_cycle04_period.pyと保存・結果・Shadow・選定・完了の関係テスト。
- 実装01で全scheduled_post_time_jstの参照一覧を作り、未接続の入口を残さない。

## 小項目・コミット単位

| 項目 | 実装と検証 | 日本語コミット案 |
|---|---|---|
| 01 | 全時刻参照の依存表、旧予定固定後の公式延長を合成再現 | 公式発走変更と固定証跡の境界を回帰化 |
| 02 | 公式本文引用・追記chain・観測時点の共通契約を実装 | 公式発走変更を出所付き追加履歴で保存 |
| 03 | 保存/ゲート/推奨/Shadow/選定/結果/完了へ共通検査を接続 | 発走変更を当時の証跡と結果照合へ接続 |
| 04 | 旧互換・不足・訂正履歴、writer/preview・資料・手順を整合 | 発走変更の不足表示と実運用手順を整備 |
| 05 | 標準受入/manifest/統合/CIと旧履歴回帰を完了 | 公式発走変更の統合受入を固定 |

## 受入条件・異常系

- 正式な延長を発走前に確認した新規固定と、変更前に固定済みの正常な原本を保持して結果照合できる。
- 変更なし、複数延長、前倒し、時刻逆転、別race/date、同じ改訂の再登録、chain分岐、非公式/未連結本文、未来取得、変更取得後付けを検査する。
- 旧予定を過ぎて取得した変更で、過去の発走後読戻しを自動適格化できない。前倒しで境界が崩れたものは保留/不適格となる。
- 改変・異レース差替え・変更参照なしはwriter/checker/summary/正式結果/個別完了で一致して拒否する。
- 不成功時も旧台帳・gate・receipt・本文のbytesは不変。新しい期間/場/予定race台帳を勝手に生成しない。

## 未確定事項の扱い・実績

翌日延期・race ID変更等は現行Owner/公式情報で判断可能な範囲を調査し、不明なら利用者へ影響と選択肢を提示する。定義不足を適当な時刻やrace IDで補わない。
後述の実装実績に項目、commit SHA、変更path、コマンド、結果、未確認事項を記録する。

## 共通作業・統合規約

- 対象：`eda-hub/horse-man`。作業時に統合したmain：`082a0209ef1ba5579b1cdf9abde1a2bd0b4d5953`（merge commit `bc0e5636e0cb40954c83d3fd8f8678c5d7004777`）。現行版v1.7.0、PR82〜85統合済み。
- 初回PR作成時は計画書までだったが、2026-10-15に当該計画の実装・合成受入を追加した。実レースの変更記録・結果/receipt作成・既存適格性の訂正・mainマージは実施していない。本書だけをProductionルールとして扱わない。
- 再開時に最新main、AGENTS、manual README、関係Owner、本書、対象branchを読戻す。基点後の変更と実測追加を確認し、従来のGitHub接続・作業記録を踏襲する。
- 統合順は回顧項目・集計→公式発走変更→旧履歴整理。後続は先行PR統合後の最新mainへ追従し、共通validator・契約・テストを手動で整合する。公式時刻変更が実際に発生した場合は、その課題を先行してよい。
- Production/Shadow/任意市場、Prediction/Recommendation/購入を分離。価格・実購入・払戻を標準入力へ戻さない。第4の6開催日・11/1までの収集日程は維持する。実測未取得はnull・不足とし、予定192Rやfixtureを実績にしない。
- PR82〜85の公式本文照合、Shadow原本/receipt、phase履歴・未解決累積、初回FIX再照合、集計Git読戻しを保持する。旧原本・receipt・固定予想・結果・比較を消さず、発走前証跡を後付けしない。
- 小項目ごとに実装・異常系/正常系検証・セルフレビューを完了し、日本語でコミットする。実績表へcommit SHA、変更path、コマンド、対象SHA、実結果、残件を追記する。
- 最終ソースで `python3 scripts/run_cycle04_acceptance.py --write` を成功させ、`python3 scripts/build_v170_manifest.py` でreleaseを生成。`python3 scripts/check_cycle04.py`、`python3 scripts/run_release_readiness.py`、`python3 scripts/check_integration_acceptance.py --full` と既存3系統CIを確認する。CI禁止・日付待ち・スキップ指定はしない。
- 標準受入は全回帰失敗0・skip0の実出力だけをPASSにする。手動hash追従や先行PRの成功証跡コピーをしない。候補branchの `--require-main` 拒否と、取得済みmainの開始認証成功を区別する。
- 過去の通常checker不合格は、最新コードの回帰失敗とは切り分けて原因と対象を記録する。黙ってauditへ切り替えて全正常と報告せず、合成試験と実運用・過去記録の状態を区別する。
- 切り戻しは変更commitのrevertと契約/受入/releaseの再整合で行う。新しく保存された記録を削除しない。schema変更には旧記録の読取・不足表示を残す。

## 2026-10-15 実装・合成検証実績

| 項目 | 対象と代表commit | 実績 |
|---|---|---|
| 01：合成再現 | `scripts/test_cycle04_schedule_change.py`（`08749c2`、`7468860`）、`test_selection_history.py`（`4b72401`） | 変更なし、延長、前倒し、時刻逆転、複数改訂、異レース引用、改ざん、未来観測、旧選定予定の保全を追加 |
| 02：変更原本・writer | `scripts/cycle04_schedule_change.py`（`57eea8f`、`c313929`、`e838473`）、`scripts/cycle04_workflow.py`（`25f3dc0`、`060300f`） | 変更原本と公式引用の二重固定、連番・前SHA・観測順、同一race/date、Git初回保存原本bytes照合、--register-post-change と --preview を追加 |
| 03：全工程接続 | `scripts/check_cycle04.py`（`90b6b16`）、`cycle04_operations.py`（`0f909de`）、`check_prediction_compliance.py`（`00e94d4`）、`verify_prediction_persistence.py`（`5a87899`）、`cycle04_completion.py`（`08fb631`）、`recommendation.py`（`0518f7d`）、`selection_history.py`（`ce3d795`）、`chat_result_reconciliation.py`（`e79a5ec`） | 予想・固定receipt・Shadow・推奨・選定・任意市場・正式結果/回顧・完了を、当時の予定と独立原本で照合。旧v1.6.1は変更なし |
| 04：運用・互換 | `docs/validation/contracts/cycle04_post_changes.md`（`89746a6`、`e7cdd9b`）と既存契約/第4テンプレート更新 | 初回時刻の保持、公式の確認不可/取消/中止/翌日延期の保留、旧固定証跡非改変、読み取り専用プレビューを文書化 |
| 05：標準合成受入 | `docs/validation/reviews/cycle_04/acceptance.json`（`82621ed`）、`docs/validation/contracts/v170-release.json`（`c3b70cd`） | GitHub Actionsで `run_cycle04_acceptance.py --write` を実行。**832テスト、失敗0、skip0、PASS**。同じCI実行で `build_v170_manifest.py` を実行し171件のソースSHAを再生成し保存。 |

### 検証実行元と監査境界

- 受入原本生成の実行：GitHub Actions `38668825199`、生成基点 `e7cdd9b7d85818edb8a635f4d46685a7e7597723`、成功（2026-10-15 UTC）。Pythonの合成受入結果をGitHub Actionsログから読戻して同一JSON形式で保存した。検証用一時workflowは `5b7adab` で除去し、v1.7.0 source manifestの管理対象ではないことを `build_v170_manifest.py` の入力一覧で確認した。
- 標準3系統：`check-cycle03.yml`（全回帰/実台帳・release監査）、`check-integration-acceptance.yml`（取得済みmainとの分離）、`check-pedigree-research.yml`（血統監査）。最終コミットについて各CIが成功したログを確認するまで、この項目の最終統合成功を主張しない。
- 本検証は**合成受入のみ**であり、JRAの実際の発走変更、実レース実行数、取消/翌日延期の同一性、Production/Shadowの性能昇格、PR89のmain反映は認証しない。
- 翌日延期・開催日またぎの同一race/date扱いは自動判定しない設計。公式資料またはOwner判断が必要になった時点で保留にし、利用者に対象レースと相違内容を提示する。
