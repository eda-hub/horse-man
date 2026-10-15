# 第3サイクル旧適格宣言の訂正・監査契約

第4サイクルのProduction契約ではない。旧v1.6.1 `cycle03-day-v1` 原本および当時の `execution-gates` / `snapshots` / `persistence-receipts` / `persistence-intents` を変更せず、別の訂正参照を追加するための**履歴監査専用**仕様。

## 原本・訂正・表示の境界

- 元日別台帳・receipt・gate・固定買い目・結果・仮想精算は改変・削除しない。原票のGit履歴を正本とする。
- 訂正は `docs/validation/historical-corrections/*.json` に、1レース×1KPI×1改訂のJSONとして保存する。実記録への訂正は利用者の確認とOwner・確認者の特定後だけ。2026-10-15の利用者判断に基づき9/26のProduction3件のみ訂正overlayを確定。原台帳・結果・保存証跡の改変は**0件**。
- 訂正対象は厳密に `race_date_jst` / `race_id` / `kpi` / `original.path` / `original.commit_sha` / `original.blob_sha` / `original.status` で特定する。コミットは実在する完全SHA、blobは当時のバイト列のGit object SHAと照合し、当時のday blockにも同じ宣言が存在することを要求する。
- `before` → `after` は **ELIGIBLE → PENDING → INELIGIBLE** の方向のみ許す。適格への昇格は訂正記録だけではできない。過去の発走前証跡を後から作成してFORWARD適格に見せない。
- `basis` は1件以上の `{path, commit_sha, blob_sha, role}` を持ち、Gitの原本と照合する。欠落を判断した説明は `reason` に書き、単なる自己申告を当時の事前証跡と呼ばない。
- `owner`、`reviewed_by`、タイムゾーン付き `reviewed_at_jst`、影響する `affected_aggregates`（最低 `cycle03:<kpi>`）を必須とする。未来時刻は拒否する。これらの文字列の本人性・判断の妥当性はリポジトリレビューで別途確認する。
- `correction_id` はファイルstemと一致。改訂番号 `revision` は1から連番、初回 `previous_record_sha256=null`、改訂2以降は**前の訂正JSONファイル全体のSHA-256**。元の `original` を保持し、`before` に直前の有効状態を指定し、確認時刻を単調増加させる。同一改訂の分岐・別hash・巻戻しは拒否する。
- 未確認・REPLAY・本文だけの保存・receipt不足・当時のgate不足はそれぞれ区別して説明する。任意の免除リスト・日付指定スキップ・audit成功・訂正済みフラグでは通常checkerを通さない。

## 機械検査の挙動

`scripts/historical_eligibility.py` はまず全訂正JSONと原本を検証する。不正な訂正が1件でもあれば通常検査・auditとも不合格となる。Git履歴がcheckoutされていない場合、参照commitを推測せず不合格にする。CIで訂正を有効にする時は `git fetch --unshallow` または `fetch-depth: 0` で必要な過去Git objectを取得する。

`scripts/check_prediction_compliance.py` は次を分離して報告する。

1. 原台帳の適格宣言に必要なgateが無い場合、`ORIGINAL_DECLARATION_CONFLICT` として**訂正後も元の問題を表示**する。
2. Git原本と改訂chainを照合済みの承認済み訂正がある場合だけ、そのrace/KPIの有効な状態を使用する。別レース・別KPIを免除しない。
3. 旧gateが適格を自己申告していても旧台帳のrace IDとの対応が証明できない場合は `UNLINKED_GATE_CLAIM`。日付や競馬場名から暗黙にJRA race IDを推測しない。
4. `--audit` は不足の可視化であり、正式適格の認証ではない。構造違反・偽のhash・履歴分岐はauditでも拒否する。

旧第3の `scripts/check_cycle03.py` は元台帳の集合・精算一致を引き続き検査し、`--effective-kpis` で別ビューを表示する。 `scripts/build_cycle03_review.py --historical-view` は元の `collection.json` を書き換えず同じ独立ビューを表示し、`--write` / `--check` との併用を拒否する。

訂正後ビューには原宣言と訂正後のKPI別件数、個別訂正、分離契約の旧固定全券精算値と正式性能参照（適格券だけ）を**別項目**で出す。正式性能の適格性は従来の `fixed-plan-source-v1` が必要。保存品質と購入ルールのKPIへ勝手に連動させない。未認証のROIはnullであり参考精算を正式成績へ昇格しない。

## 確認手順（リポジトリ直下）

```bash
python3 scripts/historical_eligibility.py --json
python3 scripts/check_prediction_compliance.py
python3 scripts/check_prediction_compliance.py --audit
python3 scripts/check_cycle03.py --require-data --require-complete --effective-kpis
python3 scripts/build_cycle03_review.py --check --require-complete
python3 scripts/build_cycle03_review.py --historical-view
python3 -m unittest scripts/test_historical_eligibility.py
```

通常checkerの不合格は、旧宣言の未解決証跡不足か最新コードの回帰失敗かを分離して記録する。合成テストで受理できても、過去の正式証跡が増えたことにはならない。必要な歴史的判断は[監査棚卸し](../reviews/cycle_03/historical_eligibility_inventory.md)の対象・根拠を提示し利用者判断を得たうえで、別途改訂JSONを追加する。

## 切り戻し

変更commitのみrevertし、承認済み訂正が後から書かれた場合は削除せず改訂chainで追跡する。旧原票・正式終了資料・receiptの直接変更は禁止。旧契約をv1.7.0へ再解釈しない。
