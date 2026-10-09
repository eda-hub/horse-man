# 次期オッズ非依存・推奨買い目（準備実装）

**状態**: PR68 §25をPR69へ実装する準備契約。第3検証サイクル終了審査・Stage 2の原子的切替前は本機能を現行Productionへ適用しない。現行 `v1.6.1`、旧 `prediction-compliance-v1`、準備済み `prediction-compliance-v2` の意味を変更しない。

## 責任範囲

- 入力: 固定済み `prediction-snapshot-v2`、非市場情報の同時好走シナリオ、着順役割、根拠。
- 出力: `recommendation-snapshot-v1`（契約ID `odds-free-recommendation-v1`）。馬番による券種・具体的組み合わせ・優先順位・ユニーク点数・短い理由と参照根拠。
- 結果: 公式着順（同着を位置配列で表す）を使って各券の HIT/MISS/INVALID、未確定時はPENDING。購入・払戻・資金を扱わない。
- Predictionの認証と推奨の認証は独立。ただし正式な推奨は、認証されたProduction gate・固定Prediction snapshotの内容hash・事前宣言・同一artifactの保存receiptに紐付ける。
- WIN5、非◎の別軸馬連/ワイド/馬単、価格連動の旧例外、印内全頭BOXは対象外。
- 券種ごとの役割: 単勝=◎の勝ち切り、複勝=◎の安定3着内、馬連=◎からの連対、ワイド=◎○同時3着内、馬単=◎1着と根拠ある2着、三連複=◎中心の同時3着内、三連単=1〜3着の順序付きシナリオ。複数の高難度券種を機械的に追加しない。計画内の未確定数値閾値は勝手に実装しない。

## 構造・保存経路

| 用途 | パスと契約 |
|---|---|
| 固定予想 | `docs/validation/snapshots/YYYY-MM-DD/<snapshot-id>.json`、`prediction-snapshot-v2` |
| 推奨作成前の宣言 | `docs/validation/recommendation-intents/YYYY-MM-DD/<intent-id>.json`、`recommendation-persistence-intent-v1` |
| 推奨内容 | `docs/validation/recommendations/YYYY-MM-DD/<recommendation-id>.json`、`recommendation-snapshot-v1` |
| 発走前読戻し | `docs/validation/persistence-receipts/YYYY-MM-DD.md`、従来の `persistence-receipt-v1` に推奨artifactの別レコードを追記 |
| 推奨認証 | `docs/validation/recommendation-gates/YYYY-MM-DD/<race-id>.json`、`recommendation-compliance-v1` |
| 結果 | 公式結果JSONを読み `scripts/recommendation.py --settle` で照合。出力は履歴として別保存し、元snapshotは上書きしない |

snapshotの必須項目は `recommendation_contract`, `recommendation_id`, `prediction_ref`（snapshot ID/path/SHA-256/baseline ID）, `revision`, `supersedes`, `race_id`, `race_date_jst`, `phase`, `status`, `reason`, `data_cutoff`, `fixed_at_jst`, `main_ticket_types`, `tickets`, `unique_ticket_count`, `horse_roles`, `scenarios`, `candidate_decisions`、`dependency_audit`。具体的なフィールド型は [版付きJSON Schema](schema-v1.json) に定義する。

状態:
- `RECOMMENDED`: 構成あり。成績照合はFINAL・前向き・認証済みのみ適格
- `NO_RECOMMENDATION`: 非価格根拠不足など理由付きで提示なし
- `EXPLICIT_MARKS_ONLY`: ユーザーの印のみ指定による省略。理由を記録
- `PENDING`: 未完了。推奨済みとは扱わず、後から補完して適格にしない

同じレースの改訂は `recommendation_id` と `revision` を変え、`supersedes` と `supersedes_sha256` で旧版を固定する。`--seal` 実行時、以前の推奨gateを `recommendation-gates/history/YYYY-MM-DD/<recommendation-id>.json` へ保存したうえで、現行の単一日・レースgateを新しい最終版に切り替える。旧版は失効保管し、的中KPIへ二重計上しない。発走後の改訂を前向きKPIへ付け替えない。

## 操作例

先に `prediction-snapshot-v2` とそれを参照する正式Prediction gateを固定・保存する。その後、次の順で作業する。必要箇所は自分のレースID/日付へ置換する。

1. **事前宣言**: `python3 scripts/recommendation.py --prepare docs/validation/snapshots/YYYY-MM-DD/P001.json --recommendation-id R001 --intent-id final --output docs/validation/recommendations/YYYY-MM-DD/R001.json`。作成された宣言を日次作業ブランチへコミットし、読戻す。
2. **判断材料を用意**: JSONで `recommendation_id`、`race_date_jst`、`fixed_at_jst`、`reason`、`horse_roles`（各馬の `finish_role`/ `source_ref`/ `observed_at_jst`/ `scenario_id`/ `reason`）、`scenarios`、`lower_bound_review`、`anchor_failure_scenario` を指定。例えば `joint_top3_scenario` にシナリオIDを指定すれば◎-○のワイド候補、`joint_top2_scenario` なら馬連候補、`anchor_place_scenario` なら◎複勝、`anchor_win_scenario` なら◎単勝を検討。無理に券種を増やさず判断材料不足なら `NO_RECOMMENDATION`。シナリオは根拠付きで予想担当が評価し、自動で独立確率を作らない。
3. **生成**: `python3 scripts/recommendation.py --generate docs/validation/snapshots/YYYY-MM-DD/P001.json --assessment judgement.json --intent-id final --output docs/validation/recommendations/YYYY-MM-DD/R001.json`。既存artifactは上書き拒否。
4. **保存証跡**: 推奨JSONを保存・読戻し、`persistence-receipt-v1` を同一artifactの `artifact_id=R001`, `artifact_path`, `receipt_id`, `timing_eligibility=PRE_RACE_ELIGIBLE`, `artifact_persist_status=PERSIST_VERIFIED`, `receipt_persist_status=RECEIPT_VERIFIED`, `persist_verified_at_jst`, `receipt_verified_at_jst`, `scheduled_post_time_jst` で追記・読戻す。発走時刻より前に両時刻があること。
5. **認証**: `python3 scripts/recommendation.py --seal docs/validation/recommendations/YYYY-MM-DD/R001.json --intent-id final --receipt-id R001-RECEIPT`。検証成功時だけ推奨gateを作成。続けて `--verify docs/validation/recommendation-gates/YYYY-MM-DD/<race-id>.json` と `--audit` を実行する。
6. **提示**: `python3 scripts/recommendation.py --display docs/validation/recommendations/YYYY-MM-DD/R001.json`。保存済みJSONだけから券種・具体的馬番・点数・順位・理由を日本語表示する。ユーザーへ表示する内容を保存済み推奨と照合する。
7. **結果照合**: `python3 scripts/recommendation.py --settle docs/validation/recommendations/YYYY-MM-DD/R001.json --result official-result.json`。公式結果JSONは `{"status":"OFFICIAL","source_url":"https://example.org/result","retrieved_at_jst":"YYYY-MM-DDT12:00:00+09:00","finish_groups":[[5],[2],[6]],"scratched_horses":[],"place_places":3}` のように出所と取得時刻を持ち、同着は同一配列にまとめる。複勝対象数は出走頭数・公式規則を確認して2または3で指定する。未確定なら `{"status":"PENDING"}` として保留する。
8. **集計**: `docs/validation/results/` に公式結果と、`{"items":[{"gate_path":"docs/validation/recommendation-gates/YYYY-MM-DD/<race-id>.json","result_path":"docs/validation/results/YYYY-MM-DD/<race-id>.json"}]}` 形式の集計manifestを用意し、`python3 scripts/recommendation.py --report docs/validation/results/report.json` で券種別の有効券・的中券・有効レース・的中レースの件数と率を出力する。失効gateは受け付けない。

※ 入力例の判断JSONはユーザーからの購入意思ではなく、非価格の着順・展開評価を人間が確定した記録。仮定を勝手にYESへ補完しない。固定Productionの評価根拠に無い馬（△含む）は採用できない。

## 監査・発効境界

`scripts/recommendation.py --audit` は全開催日を走査し、宣言のみ・artifactのみ・gateのみ・hash不一致・時刻違反・認証済みPrediction不在を検出する。GitHub Actionsで既存予想/Persistence監査と別に実施する。

`contract-state.json` の `recommendation_effective_race_date` がnullの間、旧v2の推奨欠落は失敗にしない。Stage 2でmanual release・次期契約の有効日と同時に日付を明示してACTIVEとした場合、その日以降のv2 Prediction gateには対応する推奨gateを要求する。推奨なしや明示印のみも**独立した推奨状態**として保存・認証する。初回暫定、旧revision、Replayは正式的中KPIに含めない。

単体テスト: `python3 -m unittest discover -s scripts -p 'test_*.py'`。当日提出する買い目の表示と保存内容を運用側でも必ず照合する。

## 現段階で未実装の接続

- Stage 2: `docs/manual/` Owner正式変更・上位ADR切替・運用テンプレートの適用開始・有効日固定。
- Phase 3/4/6/8: JRA-VANデータからの全券種自動最適化、UI実画面、結果取得連携、過去実績の前向き統計的分析。現段階はシナリオ評価入力を使った保守的な1種類の自動候補生成と、7券種の構造検証・的中判定ライブラリ。価格API連動、実購入情報保存は将来も標準対象外。
- WIN5は専用契約であり現実装から除外。

個別券種の点数上限・不確実性閾値・100%軸依存許容の数値化はPR68 §22/25.3の未決事項。恣意的な数値設定はしない。

PR68 §25.7 の12受入ケースとの対応は [受入状況一覧](acceptance.md) に記録する。
