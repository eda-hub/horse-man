# P1：Shadow原本と発走前読戻し検査の修正実施計画

## 目的・対象・状態

- 作成日：2026-10-14（JST）
- 作業branch：`fix/p1-shadow-evidence-integrity`
- 調査基準main：`b288bc1f39f61d68c6cf536608c11689575315e8`
- 状態：実装・回帰758件PASS（失敗0・skip0）・合成受入PASS・release生成・統合受入PASS・3系統同一ジョブPASS。過去保存記録の通常checker不合格と先行PR #82未統合は残存（Draft・未マージ）。
- 目的：新規Shadowの適格性を、同じ原本・内容hash・receipt・発走前保存/読戻しで確認する。
- 対象外：Shadowの効果採用、新しい比較モデル、全13仮説の性能証明、旧履歴の再認証。

## 再現・原因・影響

新規v1.7.0 gateのELIGIBLE Shadowは `check_prediction_compliance.evidence` を呼ぶ。既存関数はartifactの存在/ID、receiptのidentity/status、保存確認時刻を照合するが、原本bytesとcontent_sha256、receipt自体の読戻し時刻を同じ強さで照合していない。

一時fixtureで正常なPredictionと独立Shadowを用意し、Shadow原本の値を変更して当時のhashを残し、receiptの読戻し時刻を発走後11時へ変更した。標準 `record_prediction → read_day` は成功し、Shadowの適格集合へ算入した。合成再現であり、実測比較ではない。

Production/入力/FIXには `verified_artifact` 等の追加照合があるが、汎用Shadowの標準適格判定では同じ検査が必須接続されていない。現在のhashから期待hashを新規生成する修正では、当時固定した内容の同一性を証明できない。

## 修正方針

1. 新規v1.7.0の前向き適格Shadow専用に強い検査を接続する。旧v1.6.1が呼ぶ共通 `evidence` の意味を一括変更して過去履歴を壊さない。
2. 参照にはartifact_id/path・当時固定したsha256・receipt_id/pathを要求し、receiptのcontent_sha256と実原本bytesを一致させる。既存 `verified_artifact` を責任分離した共通部へ置くか、安全なimportで再利用する。
3. 保存確認時刻≦receipt読戻し時刻＜実発走予定を照合し、gateの発走予定とreceiptの期限を一致させる。検査実時刻より未来の保存/読戻しも正式完了へ使わない。比較入力cutoff以前の読戻しを要求する原本は既存比較契約の条件も維持する。
4. 欠けたhash/時刻を既存本文や現在時刻から後付けしない。独立証跡不足・改変・遅延はそのShadow項目を理由付き保留/不適格にする。明示的にELIGIBLEと自己申告した不正gateは拒否する。
5. Predictionの本体保存成功とShadow不足を分ける。Production/推奨の適格性・bytes・順位・確率・買い目へ逆流させない。
6. 専用のクラス移行比較、校正入力、個別完了表示でも同じ原本照合を使う。既存のrace/cutoff/baseline/common-input binding検査を弱めない。汎用保存検査を性能・真正性・比較方法の認証へ拡張しない。

## 実装対象・境界

| ファイル | 変更内容 |
|---|---|
| scripts/check_prediction_compliance.py | v1.7.0の適格Shadowを内容hashと発走前読戻し検査へ接続 |
| scripts/cycle04_operations.py または責任分離した共通module | verified_artifactの再利用とimport循環回避。旧契約は維持 |
| scripts/task_completion.py | 個別Shadow完了判定にも同じ検査を接続し、不足を局所表示 |
| scripts/class_transition_shadow.py、chat_forward_coverage.py、chat_calibration_review.py | 既存強い照合との整合・二重基準がないことを確認。必要箇所だけ修正 |
| scripts/test_next_prediction_compliance.py、test_task_completion.py、test_cycle04_acceptance.py、test_class_transition_shadow.py | 原本改変・時刻・receipt・旧互換の回帰 |
| docs/validation/contracts/cycle04_operations.md、該当テンプレート/保存説明 | 新規Shadow参照の必須項目と不足時手順を更新 |

既存 `cycle04_operations` は `check_prediction_compliance` をimportするため、gate検査からmodule全体を逆importして循環を作らない。共通検査を切り出す場合は呼出し元・例外型・旧契約を棚卸しする。

## 小項目別の実装・コミット計画

| 小項目 | 作業と完了条件 | 日本語コミット案 |
|---|---|---|
| 01 | 改変原本、hash差替え、遅い読戻しを個別ケースへ分け、現行の通過を回帰テストで再現 | Shadow証跡の改変と発走後読戻しを再現 |
| 02 | 新規Shadow専用のhash/receipt/時刻検査を実装。旧evidence契約は保全 | 新規Shadowの原本と発走前読戻しを厳密照合 |
| 03 | gate・個別完了・日別適格性へ接続し、Prediction/推奨の独立性と項目別不足を確認 | Shadowの適格性と個別完了の検査を統一 |
| 04 | 専用比較入口との整合、運用契約・fixtureの正しい新規参照形式を整備 | Shadow独立証跡の運用契約と互換検査を整備 |
| 05 | 全受入・manifest・統合検証・CIを実施し、本書へ対応記録を追記 | Shadow証跡修正の統合受入とリリース整合を固定 |

## 受入条件

- 独立原本・当時hash・同一receipt・保存/読戻し順・発走期限が正しければ、新規FORWARD Shadowの保存適格性を判定できる。
- 原本改変、ref/receipt/content hash不一致、receipt欠落/重複、artifact取り違え、別raceの期限、読戻し逆転、発走同時/発走後、未来時刻を拒否する。
- hashまたはreceipt読戻し時刻がない記録は、現在値の補完で適格化しない。
- Replay・合成の診断を前向き適格へ変換しない。旧receipt/旧gate/第3台帳の既存結果と保留状態を維持する。
- 適用Shadowなしは対象外、該当Shadow不足は局所的な不足として表示し、Prediction/推奨保存の成功を消さない。誤ったELIGIBLE宣言の拒否と、不足を明示したgateの保全を両方試験する。
- 専用比較の同一cutoff・基準予想・共通入力binding・独立固定と、性能未昇格を維持する。

## 検証・実装結果の記録

最低限 `test_next_prediction_compliance`、`test_task_completion`、`test_cycle04_acceptance`、`test_class_transition_shadow`、`test_chat_forward_coverage`、`test_chat_calibration_review` と旧 `test_check_prediction_compliance` /保存回帰を実施する。全回帰・合成受入・release/統合検証は共通規約に従う。

実装時に本書へ「小項目／commit SHA／変更path／実行コマンド／期待結果／実結果／残件」を追記する。実装反映状況と検証未了の詳細は末尾の作業結果に記録する。

## 共通の作業・統合規約

- 対象は常に `eda-hub/horse-man`。本書は実装計画であり、現行Productionルールの代用にしない。
- 当初の依頼は計画書作成までだったが、2026-10-14のPR83実施指示により実装に着手した。実レース記録作成は対象外のままとする。
- 既存v1.7.0の予想骨格、価格不要推奨、Production/Shadow/任意市場の分離、旧v1.6.1履歴を維持する。実購入・価格・払戻・実測性能を標準完了の必須入力に戻さない。
- 合成fixtureは一時領域で検査し、実日別台帳・未来の事前証跡・実測0を作らない。第4開催の実測、過去研究の網羅、性能昇格を本修正PRのマージ条件にしない。
- コミット・PR説明・作業記録は日本語。各小項目を実装・対応テスト・セルフレビューまで行い、小項目ごとにコミットする。未完了項目を完了と記載しない。
- 実装開始時に本書、AGENTS、最新main、対象branch、関連Ownerと対象コードを読戻す。本書の基準以降に変更があれば差分を確認して計画を更新し、確認した再現・受入条件を維持する。
- 4件の統合順は「結果の適格性 → Shadow証跡 → 初回/最終Shadow状態 → サイクル完了」。各計画は単独の基準から作成するが、後続の実装では先行修正を取り込んだ最新mainを反映してから着手する。共通ファイルの変更は機械的なours/theirsで解消しない。
- 対象コード・テスト・運用契約を変更した最終内容で `python3 scripts/run_cycle04_acceptance.py --write` を成功させ、その後 `python3 scripts/build_v170_manifest.py` でrelease manifestを再生成する。先行PRの受入・manifestを単純にコピーしない。
- 全回帰、通常checker、合成受入、release整合、統合受入と3系統CIを確認する。開始認証の `--require-main` は未マージの候補branchを認証するために改変しない。統合受入は取得済みmainと候補branchの契約一致/未マージ拒否を正しく区別する。
- 必要な過去Git履歴・原票・PDF依存を取得できない検査は実行不能として残す。失敗をコード欠陥と混同せず、未実行を成功にしない。完了報告には実行コマンド・結果・CI対象SHA・残件を対応付ける。
- 修正の切り戻しは対象変更のrevertで行い、保存済み予想・receipt・結果・比較履歴を削除しない。後続PR統合後は依存を確認し、関連契約・受入・manifestを同時に整合させる。

## 2026-10-14 作業結果・未完了検証（PR #83）

計画基準 `main` は開始時も `b288bc1f39f61d68c6cf536608c11689575315e8`。既存 `AGENTS.md`、作業branch、計画書、実装対象と比較入口を確認した。以下は「コードの反映」と「受入検査の成功」を区別する。GitHubにコードが存在することだけで受入完了とはしない。

| 小項目 | 主なcommit SHA | 変更path | 期待結果 | 現在の実結果・残件 |
|---|---|---|---|---|
| 01 改変再現 | `ce92c76`、`b7d19a5`、`c2c0ee7`、`06c87a2` | `scripts/test_next_prediction_compliance.py` | 原本改変・hash不一致・発走後読戻しを個別テスト化し不正を拒否 | 合成fixtureとテスト関数を保存。旧コードでの実行再現／修正後の実行成功は未確認。 |
| 02 厳密証跡 | `2243639`、`9f815c0`、`2b334f8`、`4f2cb28`、`db63e8a` | `scripts/check_prediction_compliance.py` | 新規v1.7.0適格Shadowのみbytes/hash/receipt/時刻を検証し、旧共通`evidence`維持 | 分離した関数を実装し、循環回避の関数内importを使用。旧契約の回帰実行は未確認。 |
| 03 個別完了／日別台帳 | `634fcaf`、`72726ca`、`72898a2`、`631976d` | `scripts/task_completion.py`、`scripts/test_task_completion.py`、`scripts/test_cycle04_acceptance.py` | 不正ELIGIBLE gateを拒否し、本体保存成功とShadow項目別不足を分離 | 実装・合成受入ケースを保存。保存/推奨独立の回帰実行は未確認。 |
| 04 専用入口／運用契約 | `760446d`、`26e7f79`、`6dc30d4` | `scripts/test_class_transition_shadow.py`、`docs/validation/contracts/cycle04_operations.md`、`docs/validation/templates/next_cycle_execution_v17.md` | 比較専用のrace/cutoff/baseline/bindingを維持し参照仕様を明文化 | 既存の`class_transition_shadow.py`、`chat_forward_coverage.py`、`chat_calibration_review.py`は変更せず読取整合を確認。実行回帰は未確認。 |
| 05 全受入・release/CI | `b3e9a6a`、`7941a84` | `docs/validation/contracts/v170-release.json` | 全回帰・合成受入PASS、release manifest整合、通常checker・統合受入・3系統CIが成功 | 変更した7入力のSHA-256を読戻し内容から更新した。直接の生成コマンド実行、合成受入更新、CI成功は**未完了**。 |

### 実行予定コマンドと結果

```bash
python3 -m unittest discover -s scripts -p 'test_*.py'
python3 -m unittest discover -s scripts -p 'test_*.py' -k shadow
python3 scripts/check_prediction_compliance.py
python3 scripts/check_prediction_compliance.py --audit
python3 scripts/run_cycle04_acceptance.py --write
python3 scripts/build_v170_manifest.py
python3 scripts/check_integration_acceptance.py --full
python3 scripts/run_release_readiness.py
```

これらの**ローカル実行結果は未取得**。本セッションの実行コンテナはprivate GitHubリポジトリを取得できず、DNS解決も失敗したため、コードをその場でcheckoutして一括実行できなかった。チェック成功・skip0・受入PASS・manifest生成成功と記録しない。

3系統Actionsをコミット`b3e9a6a8848db8b21e726df38f76347b78912997`で確認した結果、いずれも`failure`（成功ではない）：

- サイクル台帳：run `38522478105`。失敗ジョブだけを再実行したattempt 2も`failure`。
- 統合受入：run `38522478142`、`failure`。
- 血統研究：run `38522478250`、`failure`。

いずれもジョブの`runner_id=0`、`steps=[]`で、ワークフロー処理を開始した検証記録は存在しない。ジョブログ取得は404の`BlobNotFound`。当時はGitHub Actionsの利用上限が報告されていた。runner未割当はこの制約によるものとして扱い、アプリケーションのテスト失敗と断定しない。対象SHAの差分を読戻し、後から出た別SHAの成功と取り違えないこと。

`docs/validation/reviews/cycle_04/acceptance.json` は**従来の741件の成功記録のままであり、今回の変更・新規テストの合格証跡ではない**。全回帰成功後に前掲の`--write`で最新入力について生成し、続けてmanifestを再生成・読戻ししなければならない。テスト不成功の状態でPASSに改ざんしない。

### 残件と完了判定

1. 最新の対象SHAで3系統CIを実行し、実行ステップ・結果・ログを確認する。
2. 本計画の対象回帰、通常checker、保存回帰、`run_cycle04_acceptance.py --write`、`build_v170_manifest.py`、統合受入の実結果を取得し、生成物のSHAを再読戻しする。
3. 全項目がPASSになった後で本表・PR本文・検証SHAを更新し、Draft解除とマージ可否を判断する。現時点の受入状態は**未完了**。

新規実レース記録、過去のreceipt、既存予想、性能昇格は書き換えていない。


### セルフレビュー追記

- `check_prediction_compliance.validate_gate_v2`は発走時刻を`datetime`で扱う一方、共通`verified_artifact`の`post`引数はISO文字列である。逆importを避けた呼出しで型が食い違わないよう、`db63e8a`でISO文字列へ変換した。誤った型のままでは正常な適格Shadowを全件拒否するため、計画の正常系受入に直結する修正。
- 変更後の`scripts/check_prediction_compliance.py`のSHA-256を`5a11fd443810af3d0ff69adc5fe62551ae1a2e6e04159591a08ed5f84e6ac567`としてrelease manifestへ再反映した（`7941a84`）。固定ハッシュを読戻し原本から計算し、保存済み実レース証跡を操作していない。
- `cycle04_operations.verified_artifact`の既存責務（bytes/hash・receipt・保存/読戻し時刻）を再利用し、`class_transition_shadow.py`／`chat_forward_coverage.py`／`chat_calibration_review.py`の専用比較契約は変更していない。静的差分確認は実施したが、実行検証の代わりとはしない。
- CIのrunner未割当は少なくとも上記3系統・サイクル台帳の再実行で再現し、すべて0ステップ。ホスト側要因の詳細は未確定。


### CI利用上限に関する確定事項（2026-10-14 ユーザー確認）

- 過去の実行時点ではGitHub Actionsの利用上限が報告されていた。前掲CIで`runner_id=0`かつ`steps=[]`となった理由を、単なるrunner設定不備と推測しない。
- **CI停止は開発停止を意味しない**。ローカルにリポジトリがある環境では、対象回帰 → 全`unittest`（skip 0を確認）→ 通常checker → `run_cycle04_acceptance.py --write` → `build_v170_manifest.py` → 統合受入 → release整合の順で進められる。成功ログ・入力SHA・結果を本書とPRに追記する。過去の741件の合成受入ファイルを今回の成功証跡とみなさず、実行成功後に再生成する。
- 本セッションではプライベートGitHubリポジトリの直接checkoutがDNS解決不能のため、ローカル全回帰の実行は確認できない。**CI未実行とローカル未実行を明確に分け**、どちらもPASSとして記載しない。
- 対象branchはDraft保持。CIが成功しても、後続PR取込みによるコード・manifest・計画書の差分があれば検証対象SHAを更新してから判断する。自動的な日付到来だけで合格・Draft解除・マージしない。


## 最新mainの期間延長との整合（2026-10-14）

- 反映main：`52e666b5406bc44700b0426ea2aa337f744b5d44`（PR86）。本書の以前の4開催日・10/25終了という記載は旧基準の履歴とし、今後の実装・受入は本節を優先する。
- 第4は10/17・18・24・25・31・11/1の6開催日。10/17〜25は東京・京都・新潟、10/31・11/1は東京・京都。予定192Rを依頼scope・実測へ代用しない。
- mainの期間契約、開催場制限、期間終了のJST境界、登録・集計・追加期間テストを取り込み、本PRの修正を保持して共通ファイルを統合した。各PRは独立したまま、他の未マージPRの実装を取り込まない。
- 期間整合時点では2026-11-01以降へ延期していたが、2026-10-14 19:00 JSTの利用者指示で延期を撤回。現在は直ちに実装・検証を進める。3系統CIを実行し、対象SHAと結果を確認する。
- 全枝のacceptanceはNOT_RUN。旧source_manifestは参考情報であり成功証明ではない。releaseは取得済みmainの固定情報を保持するが、本PR統合後のbytesを認証しない。ソースhashを手動追従させず、標準受入成功後に標準生成コマンドで再生成する。
- 作業中に予想原本・receipt・公式本文・結果・回顧が追加されても保全する。回顧内容とデータ照合は先行可能。正式算入・サイクル完了は修正版で再検査し、発走前証跡を後付けしない。
- 再開順序：最新main・追加記録の確認→先行PRの結果適格性/Shadow証跡/最終状態/完了判定の順に統合→各段階で全回帰と標準受入生成→release生成→通常/統合検査→CI→レビュー・マージ判断。修正作業は第4の収集完了を待たずに進める。実測のサイクル終了審査は最終日の全回顧後に行い、コード受入とは分ける。
- 本整合の限定ローカル回帰：136件成功、失敗0・skip0。これは全回帰・標準受入・Git実main統合試験・CI成功ではない。
- 実行コマンド（当該候補のローカル取得ルート）：`PYTHONPATH=scripts python3 -m unittest test_cycle04_period test_class_transition_shadow test_next_prediction_compliance test_task_completion test_cycle04_acceptance`。終了0。変更Pythonファイルのcompile検査も成功。

## 実施時期の変更 — 2026-10-14 19:00 JST

- 利用者が第4サイクル後・11/1以降への延期を撤回。今から修正・残件検証を進める。本節が以前の延期方針に優先する。
- 順序はPR82→83→84→85。最新mainと先行修正へ整合し、全回帰・標準受入生成・release再生成・通常/統合検査・レビューを進める。3系統CIを実行し、対象SHAと結果を確認する。実装・ローカル検証・CIを進める。
- マージ判断は検証結果に基づく。今から実施する指示を、未検証PASSへの変更や即時マージの指示として扱わない。
- 第4の6開催日・11/1までの収集日程は維持する。修正の受入に第4実測の完了を要求しない。既存原本と追加される予想・結果・回顧・receiptを保全する。

## CI実行方針の訂正 — 2026-10-14 19:23 JST

- 利用者指示により、CIを実行しない・再実行しない・11/1まで待つという指示を撤回した。今後のコミットにCIスキップ指定を付けない。
- 最新の対象SHAで3系統CIを実行し、結果・ログ・対象SHAを確認する。過去の未実行・利用上限・0ステップ失敗は履歴であり、今後の実行禁止条件ではない。


## 2026-10-14 19:50 JST以降の再検証・反映結果（今回の最終記録）

### 変更・原因・小項目対応

- 小項目01〜04の実装は維持。CI復旧後、既存の`scripts/test_check_prediction_cycle.py`の正常系fixtureが旧Shadow形式（テキスト原本・固定SHA-256なし・receiptの読戻し時刻なし）で、新契約の適格性確認に不合格となることを実ジョブログで特定。具体的に`test_eligible_production_and_shadow_with_valid_gate_pass`で`sha256 required`を検出。
- 新規Shadowに必要な独立JSON原本、当時の固定SHA-256、receiptの`content_sha256`と`receipt_verified_at_jst`を持つようfixtureを修正。合成未来開催日（10/17）は同テスト内で検証用時計を発走後へ固定し、本番checkerの未来時刻拒否を緩和しない。コミット`278da70d`、`e943929b`。`scripts/check_prediction_compliance.py`の本番判定は緩めていない。
- 小項目05：GitHub Actions（ubuntu-latest、全Git履歴取得、`pdftotext`依存準備）で標準コマンド`python3 scripts/run_cycle04_acceptance.py --write`を実行し**758件／失敗0／skip0／PASS**を確認。次いで`python3 scripts/build_v170_manifest.py`を実行、`python3 scripts/run_release_readiness.py`と`python3 scripts/check_integration_acceptance.py --full`の成功を確認。
- `docs/validation/reviews/cycle_04/acceptance.json`は`PASS`、対象ソース143個、`docs/validation/contracts/v170-release.json`は対象ソース162個。標準生成物のコミット`1f248e820e386376a5c733048d82a7681ce417ff`。過去741件の成功記録を流用せず、**新たに全758件を実行して生成**した。
- `check_integration_acceptance.py --full`は取得済みmain `509368351cc45046fcd524b9ac4905a5a40b6b8e`で`main.operational_ready=true`を確認し、未マージ候補branchの`UNMERGED_CONTRACT_REJECTED`（想定どおり）と`monitored_sources_unchanged=true`を確認。実レース数、モデル性能、研究昇格、データ収集完了を認証したものではない。

### 3系統CIの最新コード検証

- 既存3個のworkflowから**jobs以下を変更なく抽出**し、作業branchへのpushで起動する一時的な`pr83-three-suites.yml`に統合した。検証対象SHA `2e1359e5ceb6bfe415e1c91661187b24b9cfe097`、run **38552365762**。同run内の`cycle-ledger`、`integration-acceptance`、`pedigree-research`はすべて`success`（各ステップ成功）。元の既存3 workflow自体を当該SHAで個別再実行したという主張はしない。
- 受入生成の成功run **38551842370**、生成前対象SHA `edd1a5f59259bb5cf2046c70c9ad7cdd11d5dbb8`、生成物保存commit `1f248e82`。作業用ワークフローは`cd6a1bad`および`caffff3a`で撤去。最終PRに一時的な実行手順を混入させない。これらの作業用workflowはmanifestの固定対象`.github/workflows/check-cycle03.yml`や合成受入入力に含まれず、撤去後も生成結果の入力bytesは不変。
- 一時workflowの`python3 scripts/check_prediction_compliance.py`通常モードは**失敗**。`docs/validation/records/2026-09-26.md`の過去`ELIGIBLE`宣言に対応するexecution gateが存在せず、当該記録の`NON_COMPLIANT`を正しく検出した。これは合成fixture/今回のShadow修正による回帰エラーとは別。既存の保存原本、実行ゲート、receiptを後付けで作成せず、`--audit`は成功したが正式適格性の代用にしない。

### 現在の残件・判定

1. 上述の過去記録の通常checker不合格が残る。原票・宣言・保存時刻が不在のまま適格として補修しない。正式な解決要否、KPI訂正の範囲は別途実証に基づく判断が必要であり、全体の通常checker成功は未確認。
2. 先行PR **#82は未マージ**である。統合順`#82 → #83 → #84 → #85`を守り、先行結果適格性の統合が済むまで本PRを先にマージしない。現mainの本PR基点以後の2 commitは`acceptance.json`のみの変更で、今回の標準受入で候補branch用に再生成した入力SHAを維持している。先行PRの取込み後には共有契約・生成物を改めて照合する。
3. **受入コードの合成・release・統合・3系統ジョブはPASS、全運用の通常checkerは未PASS**。Draftを維持し、本番運用の未確認原本を改竄しない。

