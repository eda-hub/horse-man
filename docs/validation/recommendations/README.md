# 次期オッズ非依存・推奨買い目（準備実装）

**状態**: PR68 §25をPR69へ実装する準備契約。第3検証サイクル終了審査・Stage 2の原子的切替前は本機能を現行Productionへ適用しない。現行 `v1.6.1`、旧 `prediction-compliance-v1`、準備済み `prediction-compliance-v2` の意味を変更しない。

## 責任範囲

- 入力: 固定済み `prediction-snapshot-v2`、非市場情報の同時好走シナリオ、着順役割、根拠。
- 出力: `recommendation-snapshot-v1`（契約ID `odds-free-recommendation-v1`）。馬番による券種・具体的組み合わせ・優先順位・ユニーク点数・短い理由と参照根拠。
- 結果: 公式着順（同着を位置配列で表す）を使って各券の HIT/MISS/INVALID、未確定時はPENDING。購入・払戻・資金を扱わない。
- Predictionの認証と推奨の認証は独立。ただし正式な推奨は、認証されたProduction gate・固定Prediction snapshotの内容hash・**予想開始前の推奨scope予定宣言とPrediction固定後の推奨独立宣言の両方**・同一artifactの保存receiptに紐付ける。
- WIN5、非◎の別軸馬連/ワイド/馬単、価格連動の旧例外、印内全頭BOXは対象外。
- 券種ごとの役割: 単勝=◎の勝ち切り、複勝=◎以外を含めた各馬の安定3着内（該当馬のProduction根拠必須）、馬連=◎からの連対、ワイド=◎○同時3着内、馬単=◎1着と根拠ある2着、三連複=◎中心の同時3着内、三連単=◎1着中心に、○または▲1着・◎2着の根拠ある逆転構成も許可する順序付きシナリオ。複数の高難度券種を機械的に追加しない。計画内の未確定数値閾値は勝手に実装しない。

## 新規固定保存のレース・時刻照合（PR #94）

固定原本の保存前には `--race-id`、`--date`、日次branch、対象path、JSON本文のrace ID／開催日／発走予定を照合し、公式scope／発走変更chainから**当該レース**について取得した時刻判定のID・日付・予定時刻とも一致させる。11Rの原本に12Rの時計を使うこと、異なる日付・snapshot IDのパスへ固定することは不可。複数レースの一括intentは最早発走時刻と等しい公式時計を指定する。推奨の独立宣言は `docs/validation/recommendation-intents/YYYY-MM-DD/`、推奨認証は `docs/validation/recommendation-gates/YYYY-MM-DD/`、Prediction固定gateは `docs/validation/recommendation-prediction-gates/YYYY-MM-DD/` に限って新規原本保存を許可する。古い原本や同名gateを異内容上書きせず、新revision・historyによる別pathを使用する。

**ID互換・共有receiptの例外・障害記録復旧**：レースIDは `20261018-TOK-11`（TOK/KYO/NII短縮形式）と `2026-10-18-TOKYO-11`（TOKYO/KYOTO/NIIGATA長形式）を同じ開催日・場・レース番号へ正規化して照合する。異なるレースを混用してはならない。正式推奨は共有 `docs/validation/persistence-receipts/YYYY-MM-DD.md` へ、先行するR01および他レースのreceiptを**1 byteも変更せず**R02を新規追記する。CLIは共有ファイルの既存bytesに追加レコードを末尾連結した完成版を `--payload-file` に渡し、`--append-receipt --write` を明示する。既存blob SHAと原本bytesの両方を再照合し、整合する場合だけ条件付き更新し、返却commitの読戻しを実施する。R02の `previous_receipt_ref`、artifact、内容SHA、保存/読戻し時刻を一致確認する。R01など過去の固定証跡や推奨本体JSONへの変更は引き続き禁止。 `incident_record()` で生成した障害JSONはrace ID・開催日・branchを保持し、`persistence-incidents/YYYY-MM-DD/` へ復旧後（発走後を含む）に新規保存・読戻し可能。ただし事故記録の保全は発走前保存、receipt認証、KPI適格を代替しない。

## 構造・保存経路

| 用途 | パスと契約 |
|---|---|
| 固定予想 | `docs/validation/snapshots/YYYY-MM-DD/<snapshot-id>.json`、`prediction-snapshot-v2` |
| 推奨作成前の宣言 | `docs/validation/recommendation-intents/YYYY-MM-DD/<intent-id>.json`、`recommendation-persistence-intent-v1` |
| 推奨内容 | `docs/validation/recommendations/YYYY-MM-DD/<recommendation-id>.json`、`recommendation-snapshot-v1` |
| 発走前読戻し | `docs/validation/persistence-receipts/YYYY-MM-DD.md`、従来の `persistence-receipt-v1` に推奨artifactの別レコードを追記 |
| 推奨認証 | `docs/validation/recommendation-gates/YYYY-MM-DD/<race-id>.json`、`recommendation-compliance-v1` |
| 参照したPrediction gateの固定証跡 | `docs/validation/recommendation-prediction-gates/YYYY-MM-DD/<recommendation-id>.json`（SHA-256と照合） |
| 結果 | 公式結果JSONを読み `scripts/recommendation.py --settle` で照合。出力は履歴として別保存し、元snapshotは上書きしない |

snapshotの必須項目は `recommendation_contract`, `recommendation_id`, `prediction_ref`（snapshot ID/path/SHA-256/baseline ID）, `revision`, `supersedes`, `race_id`, `race_date_jst`, `phase`, `status`, `reason`, `data_cutoff`, `fixed_at_jst`, `main_ticket_types`, `tickets`, `unique_ticket_count`, `horse_roles`, `scenarios`, `candidate_decisions`、`dependency_audit`。具体的なフィールド型は [版付きJSON Schema](schema-v1.json) に定義する。

状態:
- `RECOMMENDED`: 構成あり。成績照合はFINAL・前向き・認証済みのみ適格
- `NO_RECOMMENDATION`: 非価格根拠不足など理由付きで提示なし
- `EXPLICIT_MARKS_ONLY`: ユーザーの印のみ指定による省略。理由を記録
- `PENDING`: 未完了。推奨済みとは扱わず、後から補完して適格にしない

`EXPLICIT_MARKS_ONLY`・`NO_RECOMMENDATION`・`PENDING` は明示状態として優先し、`ticket_formations` に `selected=true` が残っていた場合は暗黙に `RECOMMENDED` へ昇格せず、**矛盾した入力として生成を拒否**する。選択しない候補（`selected=false`）は意思決定履歴として保存可能で、推奨点数は0とする。

同じレースの改訂は `recommendation_id` と `revision` を変え、`supersedes` と `supersedes_sha256` で旧版を固定する。`--seal` 実行時、以前の推奨gateを `recommendation-gates/history/YYYY-MM-DD/<recommendation-id>.json` へ保存したうえで、現行の単一日・レースgateを新しい最終版に切り替える。旧版はその時点のPrediction gateを固定した証跡で検証し、失効保管して的中KPIへ二重計上しない。現行Prediction gateの `review` は結果後に正式に `COMPLETE` へ更新でき、推奨gateの `--verify`、`--audit`、`--report` は継続可能。発走前固定対象（PredictionのProduction、mode、cutoff、manual、固定時点のProduction KPI等）の変更は認証を拒否する。旧固定証跡ファイルのSHA-256照合は継続する。元Predictionが更新されても旧版を新しいPrediction gateと突き合わせない。新しい推奨は変更後の現行Prediction gateと照合してから認証する。発走後の改訂を前向きKPIへ付け替えない。

## 操作例

先に `prediction-snapshot-v2` とそれを参照する正式Prediction gateを固定・保存する。その後、次の順で作業する。必要箇所は自分のレースID/日付へ置換する。

0. **予想開始前のscope宣言（必須）**: Prediction作成前に `python3 scripts/verify_prediction_persistence.py --prepare --date YYYY-MM-DD --intent-id prediction-final --snapshot-id P001 --artifact-path docs/validation/snapshots/YYYY-MM-DD/P001.json --deadline-jst YYYY-MM-DDT10:10:00+09:00 --race-id RACE_ID --recommendation-id R001 --recommendation-artifact-path docs/validation/recommendations/YYYY-MM-DD/R001.json` を実行。Prediction artifactと推奨対象ID/pathを同時に宣言して日次ブランチへ保存・読戻しする。既存の購入前宣言・v1.6.1の旧形式はオプションなしでそのまま有効。
1. **推奨生成前の独立宣言**: Prediction snapshotを固定した後、`python3 scripts/recommendation.py --prepare docs/validation/snapshots/YYYY-MM-DD/P001.json --recommendation-id R001 --prediction-intent-id prediction-final --intent-id final --output docs/validation/recommendations/YYYY-MM-DD/R001.json` を実行。先行するPrediction scope宣言、固定snapshot ID/pathと出力先が一致しなければ拒否する。作成された推奨宣言も日次作業ブランチへコミットし、読戻す。
2. **判断材料を用意**: JSONで `recommendation_id`、`race_date_jst`、`fixed_at_jst`、`reason`、`horse_roles`（各馬の `finish_role`/ `source_ref`/ `observed_at_jst`/ `scenario_id`/ `reason`）、`scenarios`、`lower_bound_review`、`anchor_failure_scenario` を指定。例えば `joint_top3_scenario` にシナリオIDを指定すれば◎-○のワイド候補、`joint_top2_scenario` なら馬連候補、`anchor_place_scenario` なら◎複勝、`anchor_win_scenario` なら◎単勝を検討。無理に券種を増やさず判断材料不足なら `NO_RECOMMENDATION`。シナリオは根拠付きで予想担当が評価し、自動で独立確率を作らない。
**7券種のフォーメーション構築**: 判断JSONに`ticket_formations`を指定すると、明示した券種候補を列の直積から展開する。例（入出力の馬番は実レースに合わせて差し替え）:

```json
{
  "ticket_formations": [
    {
      "type": "TRIO",
      "columns": [[5], [2, 6], [2, 6, 4]],
      "scenario_id": "joint",
      "reason": "◎中心の上位3頭内シナリオ",
      "selected": true
    },
    {
      "type": "TRIFECTA",
      "columns": [[5], [2], [6, 4]],
      "scenario_id": "joint",
      "reason": "2着以下の指定根拠が不十分なので今回は不採用",
      "selected": false
    }
  ]
}
```

上記は判断JSONの一部で、`horse_roles`・`scenarios`・出所時刻など他の必須項目は省略している。選択は根拠に基づき`selected`で明示し、選択券種は最大2種類。全7券種（単勝・複勝・馬連・ワイド・馬単・三連複・三連単）を入力できる。**自動的に7券種を同時推奨する仕組みではない**。三連複/馬連/ワイドは順序違いを統合し、馬単/三連単は順序を保持する。重複馬や不在・取消馬、根拠のない券種役割は拒否する。複勝は○などの非◎も認める。三連単は◎1着を基本とし、○/▲1着・◎2着の説明可能な逆転構成を許容する。単勝・馬連・ワイド・馬単・三連複での無根拠な非◎別軸化は許可しない。

3. **生成**: `python3 scripts/recommendation.py --generate docs/validation/snapshots/YYYY-MM-DD/P001.json --assessment judgement.json --intent-id final --output docs/validation/recommendations/YYYY-MM-DD/R001.json`。既存artifactは上書き拒否。
4. **保存証跡**: 推奨JSONを保存・読戻し、`persistence-receipt-v1` を同一artifactの `artifact_id=R001`, `artifact_path`, `receipt_id`, `timing_eligibility=PRE_RACE_ELIGIBLE`, `artifact_persist_status=PERSIST_VERIFIED`, `receipt_persist_status=RECEIPT_VERIFIED`, `persist_verified_at_jst`, `receipt_verified_at_jst`, `scheduled_post_time_jst` で追記・読戻す。推奨JSON全体のSHA-256を `content_sha256` に格納し、`fixed_at_jst <= persist_verified_at_jst <= receipt_verified_at_jst < scheduled_post_time_jst` を必須とする。旧receiptからの流用・改変後のハッシュ差異は認証不可。推奨専用receiptにのみ新規ハッシュ必須を適用し、旧v1.6.1の保存契約は変更しない。
5. **認証**: `python3 scripts/recommendation.py --seal docs/validation/recommendations/YYYY-MM-DD/R001.json --intent-id final --receipt-id R001-RECEIPT`。検証成功時だけ推奨gateを作成。続けて `--verify docs/validation/recommendation-gates/YYYY-MM-DD/<race-id>.json` と `--audit` を実行する。
6. **提示**: `python3 scripts/recommendation.py --display docs/validation/recommendations/YYYY-MM-DD/R001.json`。保存済みJSONだけから券種・具体的馬番・点数・順位・理由を日本語表示する。ユーザーへ表示する内容を保存済み推奨と照合する。
7. **結果照合**: `python3 scripts/recommendation.py --settle docs/validation/recommendations/YYYY-MM-DD/R001.json --result official-result.json`。公式結果JSONは `{"race_id":"RACE_ID","race_date_jst":"YYYY-MM-DD","status":"OFFICIAL","source_url":"https://example.org/result","retrieved_at_jst":"YYYY-MM-DDT12:00:00+09:00","finish_groups":[[5],[2],[6]],"scratched_horses":[],"place_places":3}` のように出所と取得時刻を持ち、同着は同一配列にまとめる。複勝対象数は出走頭数・公式規則を確認して2または3で指定する。未確定なら `{"race_id":"RACE_ID","race_date_jst":"YYYY-MM-DD","status":"PENDING"}` として保留する。結果レースID・開催日が推奨対象と一致しない場合は、着順が同じでも照合・集計を拒否する。
8. **集計**: `docs/validation/results/` に公式結果と、`{"items":[{"gate_path":"docs/validation/recommendation-gates/YYYY-MM-DD/<race-id>.json","result_path":"docs/validation/results/YYYY-MM-DD/<race-id>.json"}]}` 形式の集計manifestを用意し、`python3 scripts/recommendation.py --report docs/validation/results/report.json` で券種別の有効券・的中券・有効レース・的中レースの件数と率を出力する。失効gateは受け付けない。

※ 入力例の判断JSONはユーザーからの購入意思ではなく、非価格の着順・展開評価を人間が確定した記録。仮定を勝手にYESへ補完しない。固定Productionの評価根拠に無い馬（△含む）は採用できない。

## 監査・発効境界

`scripts/recommendation.py --audit` は全開催日を走査し、Prediction側の `recommendation_scope` だけが存在し、推奨intent・snapshot・gateが全欠落する場合も含め、宣言のみ・artifactのみ・gateのみ・固定Prediction証跡不足・hash不一致・保存順序違反・認証済みPrediction不在を検出する。GitHub Actionsで既存予想/Persistence監査と別に実施する。

`contract-state.json` の `recommendation_effective_race_date` がnullの間、旧v2の推奨欠落は失敗にしない。Stage 2でmanual release・次期契約の有効日と同時に日付を明示してACTIVEとした場合、その日以降のv2 Prediction gateには対応する推奨gateを要求する。推奨なしや明示印のみも**独立した推奨状態**として保存・認証する。推奨の前向き的中KPI適格は `FORWARD + Production ELIGIBLE + FINAL RECOMMENDED` をすべて満たす場合のみ認め、`REPLAY` や Production 不適格からの昇格を認めない。初回暫定、旧revision、Replayは正式的中KPIに含めない。

単体テスト: `python3 -m unittest discover -s scripts -p 'test_*.py'`。当日提出する買い目の表示と保存内容を運用側でも必ず照合する。

## 現段階で未実装の接続

- Stage 2: `docs/manual/` Owner正式変更・上位ADR切替・運用テンプレートの適用開始・有効日固定。
- Phase 3/4/6/8: JRA-VANデータからの全券種自動最適化、UI実画面、結果取得連携、過去実績の前向き統計的分析。現段階はシナリオ評価入力による保守的な1種類の自動候補選択と、根拠付き`ticket_formations`入力による全7券種の展開・構造検証・的中判定ライブラリ。券種の最適選択を根拠から完全自動判断するエンジンではない。価格API連動、実購入情報保存は将来も標準対象外。
- WIN5は専用契約であり現実装から除外。

個別券種の点数上限・不確実性閾値・100%軸依存許容の数値化はPR68 §22/25.3の未決事項。恣意的な数値設定はしない。

PR68 §25.7 の12受入ケースとの対応は [受入状況一覧](acceptance.md) に記録する。
