# 第4検証サイクル — 検証・日次証拠の入口

現行正式版は **v1.7.0**。JRAの第4サイクル対象日は2026-10-17・18・24・25・31、11-01の計6開催日。正式Prediction/Recommendationの判断規則は `../manual/README.md` と各Ownerを唯一の正本とし、ここへ重複定義しない。

## 役割ごとの正本

- **期間・開催場・進行状態**：[`cycle_04.md`](cycle_04.md)（日程を予想依頼scopeや実測に変換しない）。
- **運用手順・保存・読戻し・回顧・CI**：[`contracts/cycle04_operations.md`](contracts/cycle04_operations.md)。依頼時の実行入口は[`templates/chatgpt_prediction_task.md`](templates/chatgpt_prediction_task.md)。
- **第2/第3から引き継ぐ判断・未完了項目**：[`reviews/cycle_04/carryover.json`](reviews/cycle_04/carryover.json)。個別採否・Owner・原証拠・次試験を含む第4唯一の継続管理台帳。
- **原票保持・削除安全審査**：[`reviews/cycle_04/migration-manifest.json`](reviews/cycle_04/migration-manifest.json)。削除候補は履歴固定・参照移管・再計算のすべてが検証できるまで削除しない。
- **日別の固定事実**：`records/cycle_04/YYYY-MM-DD.json`。10月17日は[36R事後照合](records/cycle_04/2026-10-17.json)のみであり、発走前に登録された公式初回scopeでも正式回顧完了でもない。
- **集計の導出値**：[`reviews/cycle_04/summary.json`](reviews/cycle_04/summary.json)。前向き対象・事後照合と独立KPI不適格を混ぜない。
- **システム設計**：`../../DECISIONS.md`、`../jravan/`。ルール変更の正本にはしない。

## 現時点の移行境界

2026-10-17の36Rは結果照合済みで、JRA公式個別結果確認6R・二次情報のみ30R。事前公式scope未登録、前向き正式KPI適格0、推奨厳格監査の既存不足4診断を保持する。将来の依頼対象・対象日に推測で台帳を作らず、原票・FIX時刻・保存証拠を結果から再生成しない。合成受入成功、main反映、実開催正常一巡、性能認証は異なる状態である。

第2と第3の原記録は監査証拠として保存する。`cycle_02.md`、`cycle_03.md`、`reviews/cycle_03/`、`../proposals/2026-09-22_cycle02_summary_cycle03_handoff.md`、`../proposals/2026-10-12_cycle03_summary_application_plan.md` は**履歴資料**であり、現行作業の主指示・新しいKPIの母数ではない。重複した旧README説明の固定版は[移行基準commit](https://github.com/eda-hub/horse-man/blob/885d7d490245ba4d948bb4594017371d17eadc04/docs/validation/README.md)に保存されている。

## 検査入口

```bash
python3 scripts/run_release_readiness.py --require-main
python3 scripts/check_cycle04.py --require-active
python3 scripts/cycle04_migration.py --audit
python3 scripts/check_cycle04_full_day_reconciliation.py
python3 scripts/cycle04_recommendation_diagnostics.py --audit
```

上記は実施済み工程の監査であり、全6日終了または有効性の自動承認ではない。正常一巡は `check_cycle04.py --require-complete --completion-manifest ...` とGit読戻し固定参照を必要とし、未実施の理由付き終了は別の審査履歴で扱う。
