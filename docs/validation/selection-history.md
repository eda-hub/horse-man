# 用途・選定revisionの履歴検査（27番・未有効の準備）

現行v1.6.1を変更せず、`scripts/selection_history.py` で追加選定・用途・取消変更の不連続を検出する。履歴の連続性の成功は、発走前保存の認証、旧Betting KPI、次期Recommendation KPIの認証を与えない。Stage採否と正式接続は後続番号で扱う。

## 明示した新規履歴

`selection-history-v1` のJSONに `scheduled_posts`（race_id→時差付き発走時刻）と非空の `events` を持つ。全イベントに1から連続した整数 `revision`、前イベント原本の `previous_sha256`（初回null）、`race_id`、`purpose`、`action`、時差付き `at`、非空 `reason`、`evidence` が必要。発走時刻以降と時刻の逆行を拒否する。

用途は `VALIDATION_ONLY` / `OFFICIAL_VIRTUAL` / `ACTUAL_PURCHASE`。用途ごとの選定とplan IDを分離し、同じplanを別用途・別レースへ転用しない。検証から正式仮想へ移すには別用途の明示SELECTが必要。古いBUYの用途を書き換える操作はない。

| action | 必要な参照・判定 |
|---|---|
| SELECT | race・purposeに新しい選定を追加。重複した現役選定を拒否 |
| BUY | 同じrace・purposeの現役 `selection_revision`、新規 `plan_id`、非空 `tickets` |
| CHANGE | 同じ選定、現役planの直前 `plan_revision`、新しいtickets |
| CANCEL | 同じ選定、現役planの直前plan_revision。planは履歴に残す |
| DESELECT | 現役selection_revision。関連する現役planを先に取消す |

ticketsは券オブジェクトの配列。重複した同一券と異なるpurposeの券を拒否する。本検査は履歴連続性を担当し、券種・確率・購入ルールは既存または後続の担当checkerで検査する。取消済plan IDの再使用、取消後の変更、古い選定・plan revisionの参照を拒否。全イベントを入力に残し、検査処理は原本・台帳を変更しない。

各イベントの `evidence={"path":相対パス,"sha256":原本bytesのSHA256}` はリポジトリ内のJSON原本を参照する。原本はeventからevidenceだけ除いたオブジェクトと同一であることを照合。前イベントhashは同じ原本オブジェクトをキー順・コンパクトJSON・UTF-8で正規化したSHA256（`digest`）を使う。原本の読戻しと変更鎖を検査するが、自己記載のatだけで発走前保存を証明できない。正式採用時には独立した固定commit・receipt・cutoff・担当契約検査が別途必須。結果後作成の原本を過去の発走前証拠にできない。

```sh
python scripts/selection_history.py --root . --history /path/to/history.json
python scripts/selection_history.py --root . --audit-oct11
```

新規履歴不整合は終了1。履歴成功も `kpi_certified=false`。旧履歴監査の終了0は監査実行の成功であり、対象の適格性を示さない。

## 11日5BUYの既存証跡監査

`audit_oct11` は既存朝snapshotの空購入候補、最終5BUY/OFFICIAL_VIRTUAL、原本の7券、日別台帳の保留5と固定参考精算50,000円→0円を読取専用で照合する。旧契約を新規履歴schemaへ変換せず、追加選定イベントを生成しない。receiptと10事前宣言は出所hashを固定するが、この監査だけで個別保存・実行ゲート・fixed-plan-source認証を与えない。

旧正式Bettingは適格0・保留5・正式ROI null。参考精算を別に保持し、実購入0円を仮想購入へ混ぜない。次期Recommendation KPIは旧サンプルに非適用。Prediction/Recommendationの価格不要の完了とは独立した任意市場sidecarの準備である。

受入・固定出所は `docs/validation/implementation/2026-10-11-task27.json`。既存FIX元5commitも照合し、4件は後続追記の区切り行だけが差分、1件はsection完全一致。元買い目本文は一致するが、生section hashの不一致を一致に言い換えない。追加選定revision・目的移行証跡の欠測は元の課題OPENとして残し、今回の合成・実証跡25回帰と既存証跡監査の完了を、実履歴課題の解消と混同しない。
