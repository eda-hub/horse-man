# 第3サイクル 3段階記録テンプレート

書式だけを提供する。対象・取得契約は `docs/manual/00_core.md` 0.0.12、サイクル適用と回顧完了は `50_review.md` 0.12.3 / 0.14.3、保存状態は既存snapshot/receipt契約がOwner。実データは元予想の日次branchへ保存する。各欄の未測定は実測値でだけ置換し、結果後に発走前の空欄を補わない。

## 初回snapshotに含める台帳

- cycle_id / race_date_jst: 対象レースごとの所属と公式開催日（50_review 0.12.3）。実行日・branch日付で代用しない
- manual_release / manual_ref_commit / contract_effective_date: 実行時の参照値
- scope_revision / previous_snapshot_ref / working_branch / 依頼参照: 実行時の値
- initial_scope / validation_candidates / purchase_candidates / selected_final_scope: race_id集合
- 出力先: snapshots/YYYY-MM-DD.md（時刻未確認・発走後は既存preservation契約）

| race_id | baseline_forecast_id | 検証候補 | 購入候補 | 選定理由・時刻 | 現在の買い/見送り | initial_snapshot_ref / latest_snapshot_ref | 元branch |
|---|---|---|---|---|---|---|---|
| 実行時に記入 | 同左 | true/false | true/false | 根拠・JST | 判定 | 参照 | prediction/YYYY-MM-DD |

初回参照例（Owner: core 0.0.12）：今回本体S01にR1の初回Productionを収録し、`previous_snapshot_ref=null`、`initial_snapshot_ref={snapshot_id:S01,race_id:R1}`、`latest_snapshot_ref={snapshot_id:S01,race_id:R1}` とする。履歴の自己参照は禁止し、同一本体内の内容参照は許可する。後続S02にR1の最終内容を収録した場合は履歴と初回参照がS01、最新内容参照がS02。保存後情報をS01へ書き戻さない。

再開時は元branchの台帳snapshotを取得し、両内容参照をrace_id・baseline・実内容まで照合する。receiptも別に確認する。前日予想・翌日回顧でもrace_date_jstとcycle_idを引き継ぎ、日別からサイクル集計まで実行する。

### 項目別取得・比較の引継ぎ

| item_id / Owner | stage_due | 適用/非該当/要確認と根拠 | 取得状態 | 出所URL・取得時刻 | 対象/取得範囲・欠測 | 出力参照 | 未完了理由 |
|---|---|---|---|---|---|---|---|
| 50_review 0.12.3の各項目 | 初回/最終/回顧 | 条件根拠 | 取得済み/更新待ち/未取得/取得不能 | 未取得はnull | 頭数等 | snapshotの該当節 | 事実を記入 |

## 最終snapshotに含める記録

- 台帳revisionと選定対象を読戻したcommit、今回依頼対象、他候補の残件
- 動的入力の取得状態、非価格更新理由・証拠・情報時刻、Production NEW/REUSED/UPDATED
- 各Shadowの適用判定、開始/固定時刻、入力・比較元・結果参照
- 購入監査：単勝整合、自然な候補、券種別確率下側・価格/時刻、依存額/率、崩れるシナリオ、採否理由、監査後判断の参照
- ticket_purposeと正式買い/見送り、投資額、検証用/反実仮想/Shadowの案・比較元
- 最終内容の完了/未完了と理由（保存状態はreceipt・引継ぎへ）

## 回答・引継ぎ票（不変本体へ書き戻さない）

| 段階 | 依頼有無 / 実行有無 | 内容状態 | 本体ID / commit / 保存状態 | receipt ID / 保存状態 / 時刻適格性 | 不足・影響・次の処理 |
|---|---|---|---|---|---|
| 初回/最終/回顧 | 参照と時刻 | 完了/未完了/正常対象外 | 実際の値 | 実際の値 | 未依頼/工程失念等を区別 |

## 回顧recordと集計

- initial_scope / selected_final_scope / final_completed_scope / record_scope
- 最終不足 = selected_final_scope − final_completed_scope
- 最終対象外混入 = final_completed_scope − selected_final_scope
- scope重複 / 期待集合との差 / snapshot参照整合
- 確定結果・払戻・最終オッズ・通過順/ラップの出所と時刻

| race_id | 初回/最終の使用snapshot・receipt | 結果取得状態 | KPI名 | 対象判定 | 適格/不適格/保留・理由 | 投資/払戻 | 未実施/工程漏れ | 介入 |
|---|---|---|---|---|---|---|---|---|
| scope全件 | 時点を分離 | 未確定も保持 | Production順位/確率/Betting/各Shadow | 対象外と欠測を分離 | 根拠参照 | 帳簿別 | 理由 | 通常依頼を除く |

scope台帳自体は1レース1行。上表のKPI詳細はrace_id×KPIで複数行を許容し、scopeの重複検査と混同しない。

- 日別保存commit / 読戻し: 未実施
- cycle_03集計revision / 保存commit / 読戻し: 未実施
- KPIごとの対象ID / 適格ID / 不適格ID / 保留ID: 未測定
- 日別とサイクルの集合・分子/分母・投資/払戻の照合: 未実施
- 回顧状態 / 集計状態 / 一巡状態: 個別に記入
- 未達項目 / 是正 / 再試験・繰越: 根拠付きで記入

### 日別記録の機械照合欄

日別recordの末尾に以下を置く。日付・レースIDは実際の値へ置換し、対象がない日は配列を空にする。回顧が未実施でも `unreviewed_scope` に残し、測定待ちは `pending_ids` として記録する。各KPIの対象は適格・不適格・保留に漏れなく分ける。`betting` は固定仮想買い目の性能、`betting_evidence` はGit保存証跡として分離する。各Shadow項目は必要に応じて別の `shadow_*` キーに分け、単一の集計へ混ぜない。

```cycle03-day-v1
{
  "cycle_id": "cycle_03", "race_date_jst": "2026-09-26",
  "kpi_contract": "betting-kpi-split-v1",
  "initial_scope": [], "validation_candidates": [], "purchase_candidates": [],
  "final_completed_scope": [], "reviewed_scope": [], "unreviewed_scope": [],
  "kpis": {
    "production": {"target_ids": [], "eligible_ids": [], "ineligible_ids": [], "pending_ids": [], "evidence_refs": {}, "stake_yen": null, "return_yen": null},
    "betting": {"target_ids": [], "eligible_ids": [], "ineligible_ids": [], "pending_ids": [], "evidence_refs": {}, "stake_yen": null, "return_yen": null},
    "betting_evidence": {"target_ids": [], "eligible_ids": [], "ineligible_ids": [], "pending_ids": [], "evidence_refs": {}, "stake_yen": null, "return_yen": null},
    "betting_rules": {"target_ids": [], "eligible_ids": [], "ineligible_ids": [], "pending_ids": [], "evidence_refs": {}, "stake_yen": null, "return_yen": null},
    "shadow": {"target_ids": [], "eligible_ids": [], "ineligible_ids": [], "pending_ids": [], "evidence_refs": {}, "stake_yen": null, "return_yen": null}
  },
  "fixed_plan_settlement": {"stake_yen": 0, "return_yen": 0, "races": {}}
}
```

`betting` の適格レースは `evidence_refs` に `source_type`、`source_ref`、`working_branch` を記し、結果確認前にFIXされた買い目の追跡元を示す。Git snapshot/receiptが揃う場合は追加で参照してよい。`production`、`betting_evidence`、`shadow` の適格レースは従来どおり `snapshot_id`、`receipt_id`、`working_branch` の実在値を記す。Betting性能の適格1レースにつき投資額は10,000円、払戻額は実測値とする。未計測の額は `null` とし、0円と混同しない。コード欄は照合補助であり、発走前固定や保存読戻しの証明にはならない。出所・時刻・欠測理由は上の表にも残す。

日別記録をサイクルへ反映したら `python3 scripts/check_cycle03.py --require-data` を実行し、`docs/validation/cycle_03.md` の集計欄との一致を確認する。全予定日の記録（対象なしの日を含む）を入れた終了確認には `--require-complete` を追加する。これは記録の網羅確認であり、全KPIの成功や証拠の真正性を宣言しない。

新方式は3つのBetting判定を同じ対象集合で必須にする。性能の適格参照にはsource_pathも必須とし、[発走前FIX証跡契約](../performance-sources/README.md) の実在原文・時刻・内容を照合する。fixed_plan_settlement.racesは全対象にsnapshot_path、snapshot_id、stake_yen、return_yen、source_verificationを置く。認証が保留でも全券の仮想精算を保持し、eligibleの金額合計だけを認証済み性能へ反映する。旧方式はkpi_contractなしの従来契約として保持し、混在サイクルでも精算総額と認証金額を分ける。
