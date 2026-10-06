# Execution Compliance Gate

このディレクトリは、チャットやAIの自己申告ではなく、機械判定で予想・回顧・適用Shadowのルール準拠状態を確定するための実行台帳を置く。

## 契約version

checkerは `manual_release + schema_version` の組み合わせで検証契約を選択する。

| manual release | gate schema | 用途 |
|---|---|---|
| `v1.6.1` | `prediction-compliance-v1` | 第3サイクルまでの旧契約。Betting監査を含む |
| `v1.7.0` | `prediction-compliance-v2` | 次期Prediction中心契約。2026-10-13以降に有効化予定 |

`prediction-compliance-v1` の意味は変更しない。mainの現行releaseが将来更新されても、過去のv1 gateは旧validatorで検証する。未知のrelease/schema組み合わせはfail closedとする。

`prediction-compliance-v2` は実購入・BettingをProduction正式性の必須入力にしない。Production、適用Shadow、発走前証跡、data cutoff相当の時点性、結果後回顧を監査する。市場・仮想収益検証を行う場合は任意sidecarとして別契約に分離する。

### v2 Production必須構造

- `ranking`: Production順位。3頭以上、馬番重複不可
- `marks.honmei / taikou / tanana`: ranking 1〜3位と完全一致
- `marks.renka`: 4位以下を順位順に保持する任意配列
- `probabilities`: 少なくとも上位3頭の勝率・連対相当・3着内率
- `prediction_confidence`: `A / B / C / D`
- `evidence_items`: 少なくとも上位3頭について、根拠事実・出所・観測時刻・方向・強度を保持
- `evidence_ref`: Production KPIをELIGIBLEとする場合の発走前snapshot/receipt参照

印は順位から導出する。4位以下にも勝利可能性は認め、確率・レンジ・シナリオで表現する。勝利可能性があることだけを理由に3位以内へ順位を操作しない。

### v2 最小例

```json
{
  "schema_version": "prediction-compliance-v2",
  "race_id": "20261013-TOK-01",
  "race_date_jst": "2026-10-13",
  "mode": "FORWARD",
  "working_branch": "prediction/2026-10-13",
  "manual_release": "v1.7.0",
  "manual_ref_commit": "40文字のcommit SHA",
  "scheduled_post_time_jst": "2026-10-13T10:10:00+09:00",
  "timing_route": "SNAPSHOT_CANDIDATE",
  "production": {
    "baseline_forecast_id": "20261013-TOK-01-P001",
    "ranking": [5, 2, 6, 4, 1, 3],
    "marks": {"honmei": 5, "taikou": 2, "tanana": 6, "renka": [4, 1, 3]},
    "probabilities": [
      {"horse_no": 5, "win_probability": 0.22, "top2_probability": 0.39, "top3_probability": 0.53},
      {"horse_no": 2, "win_probability": 0.18, "top2_probability": 0.34, "top3_probability": 0.49},
      {"horse_no": 6, "win_probability": 0.14, "top2_probability": 0.29, "top3_probability": 0.43}
    ],
    "prediction_confidence": "B",
    "evidence_items": [
      {
        "horse_no": 5,
        "factor": "ability",
        "fact": "確認済み事実",
        "source_ref": "source-or-provenance-id",
        "observed_at_jst": "2026-10-13T09:40:00+09:00",
        "direction": "plus",
        "strength": "medium"
      },
      {
        "horse_no": 2,
        "factor": "recent_form",
        "fact": "確認済み事実",
        "source_ref": "source-or-provenance-id",
        "observed_at_jst": "2026-10-13T09:40:00+09:00",
        "direction": "plus",
        "strength": "medium"
      },
      {
        "horse_no": 6,
        "factor": "opponent_strength",
        "fact": "確認済み事実",
        "source_ref": "source-or-provenance-id",
        "observed_at_jst": "2026-10-13T09:40:00+09:00",
        "direction": "neutral",
        "strength": "weak"
      }
    ],
    "fixed_at_jst": "2026-10-13T09:55:00+09:00"
  },
  "kpi_eligibility": {
    "production": "INELIGIBLE",
    "shadow": "INELIGIBLE"
  },
  "shadow_items": [],
  "review": {"status": "NOT_STARTED"}
}
```

以下のv1節は、`v1.6.1 + prediction-compliance-v1` の履歴契約として保持する。


このディレクトリは、チャットやAIの自己申告ではなく、機械判定で予想・買い目・回顧のルール準拠状態を確定するための実行台帳を置く。

## 原則

- AIが `PASS` と書いても準拠扱いにしない。
- `scripts/check_prediction_compliance.py` の通常実行は、存在する全ゲートと正式なKPI適格宣言を厳格に照合する。終了コード0は、予想の保存や全レースのKPI適格性を意味しない。
- 日別machine ledgerで `ELIGIBLE` と宣言したレース、またはsnapshotが `execution-gate-ref-v1` で明示的にゲート認証を主張したレースにゲートJSONを必須とする。見送り・不適格・保留のレースは予想や台帳に保存し、内容がないのにダミーの印や基準IDを作ってゲートを埋めない。
- 既存・将来を問わず、日別台帳とsnapshotに記録された全日付を監査対象にする。適格宣言の証跡が欠けている事実を監査結果へ残し、結果後の推測値で補わない。
- snapshotの `snapshot_id` から読み取れるレースと、明示的な構造化参照を監査する。予想本文に登場する他レースのIDは対象へ混ぜない。

```execution-gate-ref-v1
{"race_date_jst":"2026-09-27","race_id":"20260927-NAK-11"}
```

- GitHub Actionsは `--audit` で欠落一覧を報告する。これは書込後の監査であり、予想とreceiptの保存を止める判定ではない。終了コード0でも `AUDIT_INCOMPLETE` があれば、該当レースはゲート認証済みではない。正式KPIへ登録する前に通常の厳格照合を通す。
- `COVERAGE YYYY-MM-DD: gates=N missing_certifications=M ungated_snapshots=K` は、保存済みゲート件数、正式適格を主張しているのに証跡がない件数、ゲート未登録のsnapshot参照数を表す。未登録のsnapshotは予想記録として保持されるが、KPI適格の認証ではない。日付はファイルから読み取り、特定日の例外は設けない。
- 発走後に作ったReplay Shadowは、結果を入力へ直接使っていなくても `ELIGIBLE` にできない。
- KPIを `ELIGIBLE` にするには、参照artifactとreceiptが実在し、receipt近傍に `PRE_RACE_ELIGIBLE` が存在することをcheckerが確認する。
- 既存の `## persistence_receipt` 形式と `persistence-receipt-v1` JSON形式の両方を同一レコードとして照合する。両形式が同じreceipt_idで矛盾する場合は拒否する。receiptの形式差だけを理由に、発走前保存済みの予想を見落とさない。
- E-11はv1.6.1の確信度尺度矛盾が解消されるまで `PENDING_RULE_CONFLICT` 以外を許可しない。
- 買い目は採用前の `natural_candidates` を必ず保持する。採用しなかった候補には `rejected_candidates.reason` を要求する。
- ◎を含まない馬連・ワイド・馬単は例外扱い。保険、依存率低下、予算消化では通さない。独立シナリオ、保守側成立確率、価格、`EV > 1.0` を機械確認する。
- 非◎縦目の `reason_code` は allowlist 方式とし、現行は `INDEPENDENT_POSITIVE_EV` だけを許可する。未知の理由コードは拒否する。
- 非◎縦目の `probability_low` と `odds` はgate内の自己申告値だけでは認証しない。`betting-evidence-v1` の発走前構造化証跡と完全一致し、そのartifactのreceiptが同一レコードで `PRE_RACE_ELIGIBLE` / `PERSIST_VERIFIED` / `RECEIPT_VERIFIED` を満たす場合だけ監査済みとする。
- 発走後Replayで新規算出した確率・価格は `betting-evidence-v1` の前向き証跡として扱わない。必要証跡がない買い目は `FIXED` にせず `BLOCKED` または参考案として保持する。
- 検証用正式買い目は合計10,000円を機械確認する。
- 回顧完了には結果取得URL・取得時刻、KPI適格性、反実仮想、非劣化の「保護/再検証/改善対象」を必須とする。

## 保存先

`docs/validation/execution-gates/YYYY-MM-DD/<race_id>.json`

保存済みsnapshotの形式・日付にかかわらず、正式KPIへ登録するレースはその予想・receiptに基づくゲートをこの保存先へ追加し、厳格照合を通す。予想とreceiptの保存が先であり、ゲートが未作成でも予想自体を消さない。発走前保存が確認できないものを `ELIGIBLE` にせず、欠けた予想内容や時刻を推測してゲートを生成しない。既に適格宣言のある過去の日付も、証拠が不足する限り厳格照合は失敗したまま残す。

日別台帳のrace_idがJRA形式（例: `202606040811`）で、snapshot_idに日付・競馬場・Rの短い形式（例: `20260926-NAK-11`）を使う場合は、同じgate JSONへ `"snapshot_race_ids": ["20260926-NAK-11"]` を置く。checkerは両方を同一レースとして照合する。別日や重複した別レースへの割当は拒否する。

## 最小例

```json
{
  "schema_version": "prediction-compliance-v1",
  "race_id": "20260926-NAK-01",
  "race_date_jst": "2026-09-26",
  "mode": "FORWARD",
  "working_branch": "prediction/2026-09-26",
  "manual_release": "v1.6.1",
  "manual_ref_commit": "40文字のcommit SHA",
  "scheduled_post_time_jst": "2026-09-26T10:10:00+09:00",
  "timing_route": "SNAPSHOT_CANDIDATE",
  "production": {
    "baseline_forecast_id": "20260926-NAK-01-P001",
    "marks": {"honmei": 1, "taikou": 2, "tanana": 3},
    "fixed_at_jst": "2026-09-26T09:50:00+09:00",
    "evidence_ref": {
      "artifact_path": "docs/validation/snapshots/2026-09-26.md",
      "artifact_id": "20260926-NAK-01-P001-S01",
      "receipt_path": "docs/validation/persistence-receipts/2026-09-26.md",
      "receipt_id": "20260926-NAK-01-P001-S01-R02",
      "timing_eligibility": "PRE_RACE_ELIGIBLE",
      "persist_verified_at_jst": "2026-09-26T09:51:00+09:00"
    }
  },
  "kpi_eligibility": {
    "production": "ELIGIBLE",
    "betting": "PENDING",
    "shadow": "PENDING"
  },
  "shadow_items": [
    {"item_id": "E-11", "state": "PENDING_RULE_CONFLICT", "kpi_eligibility": "PENDING"}
  ],
  "betting": {"status": "NOT_REQUIRED"},
  "review": {"status": "NOT_STARTED"}
}
```

## 機械判定

ローカル:

```bash
python3 -m unittest discover -s scripts -p 'test_*.py'
python3 scripts/check_prediction_compliance.py --audit
python3 scripts/check_prediction_compliance.py
python3 scripts/check_cycle03.py
```

GitHub Actionsでも同じcheckerを実行する。

## 強制境界

このgateは「チャットが回答文を表示すること」自体をOSレベルで止めるものではない。代わりに、gateを通っていない出力を正式Production、正式Betting、Shadow KPI、cycle集計へ登録できないようにする。

つまりチャットは提案者であり、**正式性の判定者はchecker**とする。


## 非◎縦目の発走前数値証跡

`vertical_exception` は次を満たす必要がある。

- `reason_code=INDEPENDENT_POSITIVE_EV`
- `scenario_id`
- `probability_low`
- `odds`
- `ev_low = probability_low * odds > 1.0`
- `evidence_ref`

`evidence_ref` は `docs/validation/betting-evidence/YYYY-MM-DD/<race_id>.json` 等の
`betting-evidence-v1` artifactを参照し、そのartifact自身が発走前receiptで検証済みでなければならない。

checkerは、gateの `type / horses / scenario_id / probability_low / odds` と、
artifact内の対応するprice/probability recordを完全一致で照合する。
