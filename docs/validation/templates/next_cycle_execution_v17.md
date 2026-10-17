# 次期検証サイクル記録テンプレート（v1.7.0予定）

> 状態: 次期契約用。第3サイクルの既存記録・`cycle03_execution.md` を変更しない。

## 日別scope

- race_date_jst:
- cycle_id:
- manual_release:
- manual_ref_commit:
- initial_scope:
- final_scope:
- reviewed_scope:

## Prediction KPI

| 項目 | 対象 | 適格 | 不適格 | 保留 | 備考 |
|---|---:|---:|---:|---:|---|
| Production |  |  |  |  |  |
| Shadow |  |  |  |  |  |

## レース別記録

| race_id | baseline_forecast_id | 初回順位 | 最終順位 | 予想確信度 | 主要根拠 | 順位変更理由 | Production gate | Shadow | 回顧 |
|---|---|---|---|---|---|---|---|---|---|

## 集計

- ◎勝率:
- ◎連対率:
- ◎3着内率:
- 上位3頭勝ち馬捕捉率:
- Brier Score:
- 順位変更改善件数:
- 順位変更悪化件数:
- 無印好走馬件数:
- 根拠不足変更件数:
- 無印馬の固定INITIAL / FINALごとの1着・2着・3着内件数（対象・適格・算入・欠測）:
- 初回→最終の固定根拠状態（事前証拠確認済み／不足／未評価）とゲートSHA・cutoff:
- 推奨失敗（軸崩れ／着順不一致／相手・第三馬漏れ）、ユニークレース・券分母:
- 合成「無印好走」指標: Owner未定義ならnull（新たな閾値は設けない）:

## 推奨買い目（正式切替後の独立契約）

- 最終予想の対象レースを RECOMMENDED / NO_RECOMMENDATION / EXPLICIT_MARKS_ONLY / PENDING に漏れなく区分する。
- RECOMMENDEDに該当するレースの的中KPI対象を eligible / ineligible / pending に分け、他の3状態を的中率分母へ混入させない。
- `recommendations` は `prediction-day-v2` JSONの直下、`kpis.recommendation` は既存production / shadowと並列に保存する。下記は `recommendation_effective_race_date` 以降のみ必須。旧v2履歴へ遡及しない。
- 公式結果未確定時はPENDING、取消で有効券がないときはINVALID。券種別レース的中数と券単位的中数、対象数、点数を保存する（払戻・実購入ROIなし）。

```json
"recommendations": {
  "recommended_ids": ["race-1"],
  "no_recommendation_ids": [],
  "marks_only_ids": [],
  "pending_ids": []
},
"kpis": {
  "recommendation": {
    "target_ids": ["race-1"],
    "eligible_ids": ["race-1"],
    "ineligible_ids": [],
    "pending_ids": []
  }
}
```

実際のJSONでは上記の `kpis.recommendation` を既存 `kpis.production/shadow` と結合する。推奨gateの照合は `scripts/check_prediction_cycle.py`、推奨認証・全件不足監査・公式着順との照合は `scripts/recommendation.py` を使用する。

## 任意sidecar

市場・仮想収益検証を実行した場合だけ別集計へ記録する。Prediction対象集合・適格性へ混入しない。

- market_validation_scope:
- eligible:
- ineligible:
- pending:
- fixed_rule_return:

## 完了条件

- Prediction対象集合 = 適格 + 不適格 + 保留
- 初回・最終・回顧のrace_idを照合
- 発走後に順位・確率・根拠を新設して適格化しない
- 実購入情報なしで日別Prediction集計が完了する


## 機械可読日別台帳

日別recordでは次の `prediction-day-v2` を1日・1cycleにつき1ブロック保存する。表とJSONが矛盾する場合は修正し、結果後に対象race_idを都合よく削除しない。

```prediction-day-v2
{
  "race_date_jst": "2026-10-17",
  "cycle_id": "cycle_04",
  "manual_release": "v1.7.0",
  "initial_scope": ["race-1", "race-2"],
  "final_scope": ["race-1"],
  "reviewed_scope": ["race-1", "race-2"],
  "kpis": {
    "production": {
      "target_ids": ["race-1", "race-2"],
      "eligible_ids": ["race-1"],
      "ineligible_ids": [],
      "pending_ids": ["race-2"]
    },
    "shadow": {
      "target_ids": ["race-1"],
      "eligible_ids": [],
      "ineligible_ids": [],
      "pending_ids": ["race-1"]
    }
  }
}
```

`market_validation` はsidecarを実行した日だけ追加する。Production / Shadowの対象集合や適格性とは独立して分類する。

機械照合:

```bash
python3 scripts/check_prediction_cycle.py
```


## execution gateとの照合

`production.eligible_ids` または `shadow.eligible_ids` にrace_idを登録する場合、同日・同race_idの `prediction-compliance-v2` execution gateを必須とする。

- gateが存在しないELIGIBLEは不正。
- 日別台帳のELIGIBLE / INELIGIBLE / PENDINGとgateの `kpi_eligibility` が一致しない場合は不正。
- Production ELIGIBLEでは、gateが参照する `prediction-snapshot-v2` の内容とgate内の順位・印・確率・根拠・baseline ID等が完全一致しなければならない。
- Shadow ELIGIBLEでは、少なくとも1件のELIGIBLEなShadow evidence itemと発走前receiptを要求する。
- 新規FORWARD ShadowのELIGIBLE参照には `artifact_id`/`artifact_path`/`sha256`/`receipt_id`/`receipt_path`/`timing_eligibility`/`persist_verified_at_jst` を必須とする。receiptの`content_sha256`と実原本bytesのハッシュを一致させ、保存確認≤receipt読戻し＜発走予定、かつ未来の確認ではないことを照合する。
- refのSHA-256は当時固定した値を保存し、欠落・改変・発走後読戻しを現在の内容や時刻で補完しない。該当項目を保留・不適格として理由を保存し、Productionと価格不要推奨の保存結果は変更しない。
- クラス移行の比較原本・共通入力・bindingは、上記に加えて共通cutoff以前の読戻しと保存順を専用比較入口で検査する。
- 非ELIGIBLEでgate自体が存在しないレースに、内容のないダミーgateを作る必要はない。

## 公式発走時刻の変更があった場合

- 日次台帳の初回発走予定は書き換えない。登録済みrace/dateの `schedule_changes` に公式原文path/hash・引用位置・旧/新予定・取得/確認/読戻し時刻・改訂順を追記する。
- 詳細は `docs/validation/contracts/cycle04_post_changes.md`。変更取得前のLATE/REPLAYは不適格のまま残す。前倒し・開催日移動・取消・確認不能は保留する。
- 新規FIX・事前宣言・receipt・gateは取得済みの新予定に固定し、変更前の原本は残す。

## 第4回顧の新規記録（PR88・v1.7.0・Owner未変更）

新規の回顧は `docs/validation/templates/cycle04_review_entry_v2.json` の `cycle04-review-v2` を用い、`DRAFT` または `COMPLETE` を明示する。`COMPLETE` は `error_classification` / `non_degradation` / `next_validation` と、`protected_good_parts`（保護）、`revalidation_targets`（再検証）、`improvement_targets`（改善対象）それぞれの状態・理由・必要入力が確定しているときだけ宣言する。該当なしも `NOT_APPLICABLE` と非空の理由が必要。未評価は `PENDING` と必要入力を残し、Prediction/結果固定とは独立に回顧完了へ算入しない。

回顧の訂正は既存原本の書換えではなく `review_history` と独立 `review-revisions` 原本参照を追記する。初回/最終順位変更は両方の固定gate SHA、baseline、cutoffと事前根拠receiptが紐づかなければ不足にする。結果から事前の「強い新事実」を逆算しない。

終了審査は正常一巡と人間Ownerの採否/性能昇格を分離する。第4以前の回顧に新項目がない場合、現在の証跡を後付けせず履歴不足として扱う。


## 保存拒否と発走時計の是正（2026-10-17、実装後の新規試行に適用）

正式レースでの発走前保存は次の順序を必須とする。未マージのPR・計画を既存本番で有効と自己申告しない。

1. 対象開催日とrace ID、公式scope、公式発走変更chain、日次branchと作業対象pathを確認する。実際のChatGPT/GitHub連携の権限と利用経路を確認する。未確認なら成功と表現しない。
2. 書込み直前・本体読戻し直後・receipt読戻し直後に、現在UTCを取得して `prediction_clock.py` / `verify_prediction_persistence.py --clock-status --date YYYY-MM-DD --clock-race-id RACE_ID` で判定する。第4運用入口は `cycle04_workflow.py --clock-status --date YYYY-MM-DD --clock-race-id RACE_ID`。JST表示、残秒、根拠、状態を返す。実時計が取れない環境では読取専用の計算値を用意できても、実測と混同せず時刻未判定とする。公式scopeと発走変更chainの読取りが終わった**後**に判定時計を新規取得する。取得前の時計を読取り後まで流用しない。時計が5秒超古い、オフセット/秒精度がない、monotonicとの乖離が2秒超、境界不明なら未判定。予定到達は実発走確認済みではない。
3. 正式intentは分析前にGit保存・固定commitから同一bytes読戻しする。FIX独立manifest→本体→receipt→個別検査の順序を守る。自己申告のreadback、ローカル保存、Actions成功だけで正式完了にしない。
4. 固定bytesとSHA-256を保持し、障害を `prediction_persistence_io.py` の拒否分類・操作記録に残す。権限/branch制約、SHA競合、通信/timeout、CI失敗、安全性拒否、理由不明を分ける。拒否された操作を別経路や高権限で迂回しない。通信系のみ、同一原本の遠隔読取り後に最大2回まで許可済みの保存を再試行する。独立した許可済み経路がなければ切替不可と明記する。
5. 実行環境にPythonと承認済みGitHub Contents API認証情報がある場合は、`python3 scripts/prediction_persistence_io.py --date YYYY-MM-DD --race-id RACE_ID --path RELATIVE_PATH --payload-file FIXED_FILE --operation-id UNIQUE_ID --write` を使用できる。同一bytesの既存原本はcommit固定で読戻し、再書込みせず存在確認済みとして扱う。固定原本と異なる内容は `--allow-update` を指定しても上書きせず、新しいrevision/pathで独立保存する。トークンや権限の自動取得・branch自動作成はしない。ChatGPTのGitHub連携利用時は同等の書込→返却commit固定読戻しを連携ツールで実行し、Pythonアダプター成功と取り違えない。
6. 失敗時は固定原本と秘匿済み障害記録を実行環境に保全し、GitHub正式保存は未完了と表示する。branch初期確認段階の拒否（HTTP 403等）でも `--local-incident` へ要求ID・応答分類・API到達状態を保存する。ローカルログ保存失敗も別途表示する。機密文字列を公開リポジトリに記録しない。事故記録の正式保存先は `docs/validation/persistence-incidents/YYYY-MM-DD/` だが、これは当時のreceiptを代替しない。旧データ・過去の証跡を遡及補完しない。

時計判定・保存成功・読戻し一致・宣言/FIX順序・個別完了・正式KPIは独立した項目として表示する。現在の時計が発走後というだけで、過去の固定commitによる発走前保存を遅延へ書換えない。実チャット/予約/再開の経路試験は合成CIと別に記録する。安全性拒否の内部理由はログ未取得につき未確定のまま扱う。
