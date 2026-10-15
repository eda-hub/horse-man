# 旧履歴の適格宣言・実行gate棚卸し（実装01）

- 調査基点: main `e731b857b082f555fa9c3d2a4b4fe9b37cb42b36`（PR88/89統合済み）
- 対象: 第3サイクル7日（2026-09-26、09-27、10-03、10-04、10-10、10-11、10-12）
- 元原票: `docs/validation/records/YYYY-MM-DD.md` 内の `cycle03-day-v1`
- 歴史的原本の固定参照: 9/26の日別台帳は commit `8e4e3a59a4ffce60bde751554abc4fa8cf34cee2`、Git blob `80ca492ac9bc9ca8b10bbf29504a10d84c60f49d`。本修正のmain時点の同ファイルblobは `9caeaf512a4d3f852521e16d669cc43e240a28bb`。原台帳の更新はしない。
- 確認法: GitHubの保存済み原commitで原台帳を読み、現行mainで日別7件、execution-gates各日、9/26のsnapshotとreceipt、9/27の既存gate2件を読戻した。実行コマンドによる通常checkerの終了コード確認は未実施（GitHubコネクタではPython実行不可）。以下はコードと原票を突き合わせた「再現条件」であり、CLI実測PASS/FAILとは区別する。

## 全日棚卸し（旧台帳でELIGIBLEを宣言したKPI）

| 開催日 | Production | Betting（性能） | Betting rules | Betting evidence | Shadow | 登録済みgate |
|---|---:|---:|---:|---:|---:|---:|
| 09/26 | 3 | 0 | 旧未分離 | 旧未分離 | 0 | 0 |
| 09/27 | 0 | 0 | 0 | 0 | 0 | 2 |
| 10/03 | 0 | 0 | 0 | 0 | 0 | 0 |
| 10/04 | 0 | 0 | 0 | 0 | 0 | 0 |
| 10/10 | 0 | 0 | 0 | 0 | 0 | 0 |
| 10/11 | 0 | 0 | 0 | 0 | 0 | 0 |
| 10/12 | 0 | 0 | 0 | 0 | 0 | 0 |

※ Betting（性能）は分離契約下の固定買い目出所認証であり、購入ルール・保存品質とは独立。各KPIの「0」は適格宣言数であって対象数や有効成績の0件確定ではない。過去の精算値は不変。

## 未解決の対象・訂正候補（利用者判断待ち）

| 対象race | KPI | 元宣言 | 原台帳の参照 | 確認された証跡 | 欠けた確認 | 訂正候補 |
|---|---|---|---|---|---|---|
| 202606040811（9/26中山11R） | production | ELIGIBLE | 上記原commit/blob | S01/R02のGit snapshot・receipt、発走前と記録 | execution gate原票なし、個別の当時契約認証 | PENDING / INELIGIBLE の要判断 |
| 202609040810（9/26阪神10R） | production | ELIGIBLE | 同上 | S01/R02のGit snapshot・receipt、発走前と記録 | execution gate原票なし、個別の当時契約認証 | PENDING / INELIGIBLE の要判断 |
| 202609040811（9/26阪神11R） | production | ELIGIBLE | 同上 | S01/R02のGit snapshot・receipt、発走前と記録 | execution gate原票なし、個別の当時契約認証 | PENDING / INELIGIBLE の要判断 |
| 20260927-HAN-07（9/27阪神7R） | production | PENDING（台帳）/ ELIGIBLE（gate） | 台帳9/27・execution-gates/2026-09-27/20260927-HAN-07.json | gate原本あり | gate側と再審査後の台帳状態が不一致 | 元gateを消さず保留の正当性を監査 |
| 20260927-HAN-08（9/27阪神8R） | production | PENDING（台帳）/ ELIGIBLE（gate） | 台帳9/27・execution-gates/2026-09-27/20260927-HAN-08.json | gate原本あり | 同上 | 同上 |

- 9/26の3件は **receipt未保存とは言えない**。原票には `PERSIST_VERIFIED` / `RECEIPT_VERIFIED` / `PRE_RACE_ELIGIBLE` のR02がある。一方、当時gate原票がないことは別の欠落である。これだけで予想精度や仮想精算が失敗だったとは断定しない。
- 9/27既存gate2件の `production=ELIGIBLE` は、現行台帳 `production=PENDING` と異なる。gateの自己申告による自動昇格、台帳の黙示変更はしない。
- 対象が未確定のため、**承認済み訂正overlayは0件**。元宣言の違反候補は通常checkerに残す。証跡なしの事後gate/FIX/receipt/intentは作らない。
- 正式KPI影響候補: 9/26旧Production適格3件の分母、9/27の未認証Production 2件の扱い。旧Betting性能・保存品質・購入ルール・Shadow・参考仮想精算へ横展開しない。
- 判断依頼: 上記3レースを保留とするか不適格とするか、判断者（Owner・確認者）と確定日時・根拠を確認する。9/27のgate自己申告の意味は当時の提出時刻・原commit確認後に整理する。結果や推奨を上書きしない。

## 原本照合と追加検証

- `scripts/check_prediction_compliance.py` の `cycle_links` は、適格レースにgateが無い場合に通常実行を不合格とし、`--audit` のみ不足として出力する構造である。9/27は台帳とgateの状態が異なるため別途不一致判定が発生する。
- 旧原本と現在の台帳のバイト列は異なる（別blob）。その事実を「当時の宣言が存在しない」と読み替えず、Git履歴のoriginal commitに固定する。
- 保存済み第3レビュー `docs/validation/reviews/cycle_03/collection.json` は当時の集計。独立した訂正後ビューを生成しても元資料を改変しない。
- 実装後の実行環境で通常/audit checker、全回帰、標準受入、release、統合、3系統CIの実コマンド出力を取得するまで合格とは呼ばない。
