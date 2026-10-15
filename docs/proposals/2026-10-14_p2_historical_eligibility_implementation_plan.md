# P2：旧履歴の適格性整理の修正実施計画

- 作成日：2026-10-14（JST）
- 作業branch：`fix/p2-historical-eligibility`
- 優先順位：P2の3番目。現行運用と旧履歴を分離し、終了審査までに整理する。
- 状態：調査・実装計画のみ。今回、過去の適格性/成績は訂正しない。

## 背景・確認が必要な範囲

先行PRの通常check_prediction_compliance検査で、旧2026-09-26の適格宣言とexecution gate欠落が報告された。audit成功を正式適格性の証明にはできない。旧時点の本文、receipt、原コミット、宣言を照合して、実際の不足と集計への影響を確定する必要がある。

過去の通常検査失敗は本課題の調査起点であり、全レースが誤宣言であると断定しない。新規v1.7.0へ古いschemaを読み替えず、当時の契約で検査する。PR82〜85の新規運用条件をこの調査待ちへ戻さない。

## 調査・訂正契約案

1. 旧日別台帳・実行gate・snapshot・receipt・事前宣言・固定案・結果・集計を、保存時点commitと現行参照に対応付ける。リポジトリ全体のeligible宣言を列挙して同型不足の範囲を確定し、9/26だけをハードコードした例外で終了しない。
2. 対象はrace/release/schema/KPI系列ごとに、当時実在した原本、同一性、保存/読戻し時刻、未確認点、checker実結果を記録する。Prediction、購入ルール、保存品質、仮想精算/性能、Shadowを一括で不適格にしない。
3. 固定参照で読める訂正・監査overlayを追加し、元宣言・旧集計・旧原本を保全する。新記録には訂正理由、対象/変更前後、判断根拠commit/path/hash、確認者/Owner、確認時刻、影響する集計を持たせる。checkerは原宣言の違反と有効な訂正後状態を別々に報告する。
4. 証跡不足は保留/不適格の根拠を示す。欠けた発走前gate・receipt・FIX・事前宣言を現在生成して正式化しない。後から作成した診断はREPLAYまたは監査記録であり、FORWARDを認証しない。
5. 実装01で変更候補とKPI影響を表にして利用者へ提示する。意味が不明な状態分類や成績訂正の採否は確認後に確定する。コード実装の判断と、歴史的宣言/成績の訂正承認を混同しない。事実確定前は棚卸し・読取検査を継続する。
6. 旧Bettingでは発走前FIXの追跡性、購入ルール、保存品質、性能出所の分離を維持する。監査違反券だけを除外してROIを書き換えない。保存済み仮想精算は当時の表示を保ち、正式成績への算入可否と訂正後集計を別表示する。
7. 通常checkerは訂正記録のrace/KPI/旧宣言/hash/履歴を検査し、未解決違反を拒否する。任意の免除リスト、日付スキップ、audit結果や訂正済みフラグだけで正常化しない。新しい未記録gateは従来どおり拒否する。

## 修正対象・調査先

- docs/validation/records/、execution-gates/、snapshots/、persistence-receipts/、persistence-intents/、reviews/：現行参照と当時commitを比較する読取調査。
- scripts/check_prediction_compliance.py、check_cycle03.py、check_betting_performance.py、build_cycle03_review.py、verify_prediction_persistence.py：旧契約別の判定と訂正overlay参照。不要な意味変更をしない。
- 旧成績を参照する回顧package/改善引継ぎとREADME、訂正/監査schema・運用契約。
- test_check_prediction_cycle.py、旧v1.6.1/KPI分離/仮想精算/保存監査の回帰、原commit照合テスト。実装01で実在ファイルと依存を確定する。

## 小項目・コミット単位

| 項目 | 実装と検証 | 日本語コミット案 |
|---|---|---|
| 01 | 通常checkerの不足を原票/Git履歴で再現し、対象/KPI/影響候補を棚卸し | 旧適格宣言と当時の保存証跡の差異を固定 |
| 02 | 保全付き訂正overlayと共通schema/照合を実装 | 旧宣言の原本を保全する訂正参照を追加 |
| 03 | 確認済み訂正を通常checker・旧KPI集計へ接続し、未解決を残す | 旧履歴の訂正状態と独立KPIを再照合 |
| 04 | 旧表示/訂正後表示、Owner不足、回顧/引継ぎ/手順を整合 | 歴史的宣言と訂正後状態の表示を分離 |
| 05 | 旧互換/現在全回帰/標準受入/manifest/統合/CIを完了 | 旧履歴整理の保全と統合受入を固定 |

## 受入条件・異常系

- 旧原本・当時の宣言・receipt・精算値のbytesとGit履歴を保持し、訂正前後を追跡できる。
- 同一raceでも独立KPIの適格性を混同しない。未確認・receipt不足・本文だけ保存・REPLAYを理由付きで区分する。
- 訂正の別race/別KPI/別hash、偽の原commit、根拠欠落、訂正chain分岐・巻戻し、時刻未来、部分免除を拒否する。
- 適切な当時証跡の正常系は維持し、訂正記録によって証跡が生まれた扱いにしない。
- 実データの訂正候補は対象と根拠を提示し、必要な確認を得た範囲だけ反映する。未確定候補は原宣言と不足表示のまま保持する。
- 通常checkerとauditの差分を明示し、過去違反を除去したふりで全正常・新性能昇格を宣言しない。

## 実装状況・現在の照合結果（2026-10-15）

- 作業対象は本PR `fix/p2-historical-eligibility`。最新main `e731b857b082f555fa9c3d2a4b4fe9b37cb42b36` を統合し、PR88・89の既存変更を保護した。
- 01 旧適格宣言の[実原票棚卸し](../validation/reviews/cycle_03/historical_eligibility_inventory.md)を追加した。歴史的原commit `8e4e3a59a4ffce60bde751554abc4fa8cf34cee2` と旧日別台帳blob `80ca492ac9bc9ca8b10bbf29504a10d84c60f49d` を確認。旧宣言Production適格3件/9月26日、execution gate原票0件。snapshot/receipt R02は実在し、別の欠落として区別する。9月27日gate2件は旧台帳のrace IDと直接一致しない。
- 02 Git commit/path/blob固定参照、根拠・Owner/確認者・確認日時・影響KPI・厳格なrevision chainを持つ `scripts/historical_eligibility.py` と[監査契約](../validation/contracts/historical_eligibility.md)を追加。発走前証跡の後付けや暗黙の適格昇格は禁止。
- 03 通常checkerで原宣言の不一致と承認済み訂正後状態を区分。紐付け未証明の旧gateは別理由で拒否。旧第3checkerと終了資料には独立JSON表示を追加し、元の正式台帳/仮想精算は不変。
- 04 元表示と訂正後表示、Owner/確認者不足、回顧README・運用READMEの参照を整合。独立KPIを混合しない。
- 05 異常系・正常系のGit原本照合回帰 `test_historical_eligibility.py` を追加し、GitHub Actionsの3系統で検証中。CLI実測・標準受入・release/manifest・統合の最終結果はGitHub Actions実行終了後に更新する。事実確認・承認なしの元成績訂正は未実施。

### 採否未確定・承認待ち

9/26の3つのProduction適格宣言を**保留**とするか**不適格**とするかは、当時の証跡確認と利用者判断が必要。承認するOwner・確認者、判断日時、根拠commitを確定しない限り、訂正overlayは1件も登録しない。9/27の既存gateと旧台帳のレースID対応も未証明なので、勝手に照合済みとしない。この判断待ちはコードの回帰検証・旧履歴の監査を止める理由にしない。

## 実績・未確定事項

実装時に対象race/KPI／元commit/path/hash／判断／確認者・Owner／変更commit／実行コマンド／期待値／実結果／残件を追記する。
各旧宣言の実証、訂正分類と成績影響は未確定。本書作成時は原票の網羅監査・コード変更・実記録訂正を行っていない。

## 共通作業・統合規約

- 対象：`eda-hub/horse-man`。基点main：`984ee26fac173af8c7f8c4e5b7f5ab4df844bf1a`。現行版v1.7.0、PR82〜85統合済み。
- 本依頼はブランチ・修正計画・実施計画書の作成まで。コード修正・実レース記録・適格性訂正・mainマージは未着手。本書を現行Productionルールとして使用しない。
- 再開時に最新main、AGENTS、manual README、関係Owner、本書、対象branchを読戻す。基点後の変更と実測追加を確認し、従来のGitHub接続・作業記録を踏襲する。
- 統合順は回顧項目・集計→公式発走変更→旧履歴整理。後続は先行PR統合後の最新mainへ追従し、共通validator・契約・テストを手動で整合する。公式時刻変更が実際に発生した場合は、その課題を先行してよい。
- Production/Shadow/任意市場、Prediction/Recommendation/購入を分離。価格・実購入・払戻を標準入力へ戻さない。第4の6開催日・11/1までの収集日程は維持する。実測未取得はnull・不足とし、予定192Rやfixtureを実績にしない。
- PR82〜85の公式本文照合、Shadow原本/receipt、phase履歴・未解決累積、初回FIX再照合、集計Git読戻しを保持する。旧原本・receipt・固定予想・結果・比較を消さず、発走前証跡を後付けしない。
- 小項目ごとに実装・異常系/正常系検証・セルフレビューを完了し、日本語でコミットする。実績表へcommit SHA、変更path、コマンド、対象SHA、実結果、残件を追記する。
- 最終ソースで `python3 scripts/run_cycle04_acceptance.py --write` を成功させ、`python3 scripts/build_v170_manifest.py` でreleaseを生成。`python3 scripts/check_cycle04.py`、`python3 scripts/run_release_readiness.py`、`python3 scripts/check_integration_acceptance.py --full` と既存3系統CIを確認する。CI禁止・日付待ち・スキップ指定はしない。
- 標準受入は全回帰失敗0・skip0の実出力だけをPASSにする。手動hash追従や先行PRの成功証跡コピーをしない。候補branchの `--require-main` 拒否と、取得済みmainの開始認証成功を区別する。
- 過去の通常checker不合格は、最新コードの回帰失敗とは切り分けて原因と対象を記録する。黙ってauditへ切り替えて全正常と報告せず、合成試験と実運用・過去記録の状態を区別する。
- 切り戻しは変更commitのrevertと契約/受入/releaseの再整合で行う。新しく保存された記録を削除しない。schema変更には旧記録の読取・不足表示を残す。
