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

## 9/26確定の訂正と9/27未解決の原票対応

| 対象race | KPI | 元宣言 | 原台帳の参照 | 確認された証跡 | 欠けた確認 | 訂正候補 |
|---|---|---|---|---|---|---|
| 202606040811（9/26中山11R） | production | ELIGIBLE | 上記原commit/blob | S01/R02のGit snapshot・receipt、発走前と記録 | execution gate原票なし、個別の当時契約認証 | INELIGIBLE（2026-10-15利用者判断。訂正overlay固定済み） |
| 202609040810（9/26阪神10R） | production | ELIGIBLE | 同上 | S01/R02のGit snapshot・receipt、発走前と記録 | execution gate原票なし、個別の当時契約認証 | INELIGIBLE（2026-10-15利用者判断。訂正overlay固定済み） |
| 202609040811（9/26阪神11R） | production | ELIGIBLE | 同上 | S01/R02のGit snapshot・receipt、発走前と記録 | execution gate原票なし、個別の当時契約認証 | INELIGIBLE（2026-10-15利用者判断。訂正overlay固定済み） |
| 20260927-HAN-07（9/27阪神7R） | production | PENDING（台帳）/ ELIGIBLE（gate） | 台帳9/27・execution-gates/2026-09-27/20260927-HAN-07.json | gate原本あり | gate側と再審査後の台帳状態が不一致。識別子対応も未証明 | 元gateを消さず同一性・保留の正当性を監査 |
| 20260927-HAN-08（9/27阪神8R） | production | PENDING（台帳）/ ELIGIBLE（gate） | 台帳9/27・execution-gates/2026-09-27/20260927-HAN-08.json | gate原本あり | 同上（識別子対応未証明） | 同上 |

- 9/26の3件は **receipt未保存とは言えない**。原票には `PERSIST_VERIFIED` / `RECEIPT_VERIFIED` / `PRE_RACE_ELIGIBLE` のR02がある。一方、当時gate原票がないことは別の欠落である。これだけで予想精度や仮想精算が失敗だったとは断定しない。
- 9/27既存gate2件の `production=ELIGIBLE` は、台帳内の阪神7R/8R（`202609040907` / `202609040908`）の `production=PENDING` と意味上異なる。ただしgateキーは `20260927-HAN-07` / `20260927-HAN-08` と異なり、現在のcheckerはIDを直接結合できない。このため機械的に「同一raceのgate不一致」と断定せず、**紐付け未証明の適格自己申告**として別に報告・拒否する。実証なしのID推測・昇格・黙示変更はしない。
- **9/26の3件だけ**、2026-10-15の利用者判断に基づき `production: ELIGIBLE → INELIGIBLE` の監査overlayを3件保存した。原台帳の宣言はELIGIBLEのまま保持し、訂正後ビューは適格0/不適格24/保留0とする。原宣言との相違は診断として残すが、訂正済みの3件についてgate欠落による拒否を繰り返さない。結果・予想・receipt・仮想精算の原本は変更しない。
- 訂正記録は `docs/validation/historical-corrections/` の `cycle03-20260926-{nak11,han10,han11}-production-r1.json`（3ファイル）に固定。旧台帳・snapshot・receiptのGit commit/path/blobを照合し、発走前gate/FIX/receipt/intentを新設しない。
- KPI影響: 9/26の訂正後Production正式分母から旧適格宣言3件を除外する。9/27の未認証Production2件は別件で未解決。Betting性能・保存品質・購入ルール・Shadow・参考仮想精算へ横展開しない。
- 9/26の判断者: 利用者（2026-10-15本チャットでINELIGIBLEと指定）。原本照合: ChatGPT。判断記録日時: 2026-10-15T14:50:10+09:00。9/27のgate自己申告とrace ID対応は未解決として保持。

## 原本照合と追加検証

- `scripts/check_prediction_compliance.py` の `cycle_links` は、適格レースにgateが無い場合に通常実行を不合格とし、`--audit` のみ不足として出力する構造である。9/27の既存gateと台帳のJRA形式race IDは異なるため、元コードはgateの状態不一致を直接検出しない。今回の実装は紐付けのない旧ELIGIBLE gateを `UNLINKED_GATE_CLAIM` として別途拒否する。
- 旧原本と現在の台帳のバイト列は異なる（別blob）。その事実を「当時の宣言が存在しない」と読み替えず、Git履歴のoriginal commitに固定する。
- 保存済み第3レビュー `docs/validation/reviews/cycle_03/collection.json` は当時の集計。独立した訂正後ビューを生成しても元資料を改変しない。
- 実装後の実行環境で通常/audit checker、全回帰、標準受入、release、統合、3系統CIの実コマンド出力を取得するまで合格とは呼ばない。
