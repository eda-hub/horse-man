# PR68 §25.7 推奨買い目の受入状況（PR69 準備実装）

**適用境界**: 第3検証サイクル2026-10-12まで現行 `v1.6.1` を変更しない。本表の「実装済み」は準備コード・ユニット検証を意味し、Production正式有効化・LIVE競馬予想での受入完了を意味しない。2026-10-13は最短開始可能日で、自動切替日ではない。

WebUIは2026-10-10の利用者指定により実施対象外。表のチャット・保存・監査・結果照合は引き続き必要とし、画面未実装を残件・受入阻害理由にしない。

| §25.7 | 対象 | PR69の実装・検証範囲 | 検証参照 | 残作業・条件 |
|---|---|---|---|---|
| 1 | オッズ・市場・購入情報なしの提示/保存/結果照合 | 準備コード実装済 / 統合テスト済 | test_01_end_to_end_odds_free, test_15_report_uses_official_results_not_payout | 正式Stage 2適用とJRA結果自動連携は未実施 |
| 2 | オッズ・人気だけが変わっても構成不変 | 実装済 / テスト済 | test_02_odds_change_does_not_change_recommendation | Production側の既存契約と連携 |
| 3 | ◎-○の馬連/ワイド・3着限定馬・非◎縦目禁止 | 構造監査実装済 / テスト済 | test_03_pair_requires_anchor_and_main_pair, test_04_third_only_horse_cannot_enter_quinella | 馬連/ワイドの幅広いシナリオに対する全自動組み立てはPhase 3 |
| 4 | 勝ち切り/上位2頭/混戦/3着相手/高不確実性/軸依存 | 代表シナリオ生成と依存監査実装済 | recommendation.py build/validate_snapshot, test_01 | 全状況・全券種の自動構成比較と品質検証はPhase 3/8 |
| 5 | 正規化・重複排除・馬単等の順序・取消/未出走/点数 | 構造検証実装済 / テスト済 | test_05_trio_normalization_and_exacta_order, test_06_duplicate_count_missing_horse_cancelled | 非UIの自動構成・展開処理はPhase 3。画面は実施対象外 |
| 6 | 推奨なし・未完了・明示印のみ | 実装済 / テスト済 | test_08_no_recommendation_and_pending_do_not_become_eligible, test_17_explicit_marks_only_and_pending | 手動判断理由を必須 |
| 7 | △を含む全推奨馬の適性/時点/出所・未来根拠/確率捏造禁止 | 構造監査実装済 / テスト済 | test_07_future_evidence_or_missing_scenario_is_rejected | Shadow経由でない真の根拠はPrediction側の証跡で確認 |
| 8 | snapshot/点数/理由/Prediction hash改変・欠測・未登録検出 | 独立hash/事前宣言/receipt/gate/audit実装済 / テスト済 | test_09_hash_and_tamper_or_missing_gate_detected, test_10_receipt_late_or_wrong_prediction_ref_fails | 発走前運用のLIVE検証は未実施 |
| 9 | 取消等の更新・改訂と失効・結果後操作禁止 | revision/旧版hash/gate履歴・集計対象除外実装済 | test_18_seal_revision_archives_previous_gate_without_double_count | 非UIの取消自動検知/当日差分連動はPhase 3/6 |
| 10 | 日別推奨のscope/KPI分割・結果との照合 | 状態/KPI partitionと券種別率の算出実装済 | test_check_prediction_cycle追加3件 / test_15 | 正式日別LIVE台帳の集計はStage 2/Phase 6/8。画面は実施対象外 |
| 11 | 旧v1.6.1の監査不変・v2既存prediction履歴互換 | 維持 / 回帰テスト済 | 既存test_check_prediction_compliance / test_12_old_v2_prediction_stays_valid_without_recommendation | 新しい必須化は有効日以降のみ |
| 12 | チャット/保存/読戻しの同内容表示（WebUI部分は対象外） | 保存済JSONから日本語表示実装済 | test_14_display_matches_saved_ticket | チャット実運用はStage 2で未実施。WebUI実画面は受入対象外 |

## 意図的に含めない内容

- 発効前に`docs/manual/`の現行Ownerまたは現行オッズ・購入必須契約を変更すること。
- 過去の推奨・旧Prediction・旧購入台帳の遡及補完やKPI昇格。
- 全券種自動最適化・WIN5・JRA-VAN Phase 3〜8を前倒しする新ランタイム。
- 未検証の点数上限、高不確実性閾値、軸依存許容割合の数値を推測で固定すること。
- 購入申込・予算・賭け金・実収支・払い戻しを正式推薦の入力にすること。

## 検証

`python3 -m unittest discover -s scripts -p 'test_*.py'` で、現行/次期Prediction・persistence・pedigreeも含む回帰を実行。GitHub Actions `予想実行と検証台帳の機械監査` は推奨の独立全件auditを追加。最新実行結果はPR69のChecksを正とし、実施済み範囲・残Phaseを混同しない。

正本: [PR68の次期実装計画 §25](../../proposals/2026-10-06_next_cycle_prediction_architecture_implementation_plan.md)、[推奨買い目の操作手順](README.md)。

## 2026-10-09 指摘6件の修正・回帰受入

| 指摘 | 対応 | 回帰テスト |
|---|---|---|
| P1 改訂不能 | 推奨revisionごとに認証当時のPrediction gateとSHA-256を固定保存。seal時には旧版を固定証跡で検証し、新版は現行gateへ照合する | `test_24_updated_prediction_allows_revision_with_archived_original_proof` |
| P1 REPLAYの昇格 | 原Predictionのmode/Production KPIを認証し、推奨gateのmode一致とELIGIBLE条件を検証する | `test_25_replay_or_ineligible_prediction_must_not_certify_forward_recommendation` |
| P1 別レース結果 | 結果JSONの`race_id`/`race_date_jst`を必須にし、直接照合と日別率集計の両方で照合する | `test_26_result_race_and_date_must_match_even_with_same_finish` |
| P1 古いreceipt | 推奨JSON bytesのSHA-256と固定・保存・receipt読戻し・発走時刻の順序を機械検証する | `test_27_recommendation_receipt_must_bind_bytes_and_follow_fixation` |
| P2 推奨の全欠落 | Prediction開始前の`recommendation_scope`をaudit起点にし、独立宣言/snapshot/gateがゼロでも不足扱いとする | `test_28_prediction_scope_without_any_recommendation_fails_audit` |
| P2 券種一律◎制約 | 複勝の非◎対象と、○/▲1着・◎2着の根拠付き三連単を許可。馬連/ワイド等の非◎縦目制約は維持する | `test_29_place_on_second_choice_and_trifecta_reverse_first_row` |

**受入範囲**: CIのPython回帰テストで検証する範囲に限定。正式運用への切替や、JRA-VAN/WebUIへの接続を完了した意味ではない。

## 2026-10-09 再指摘2件：結果後の回顧更新と明示状態の厳守

| 再指摘 | 修正内容 | テスト |
|---|---|---|
| P1 回顧追記で推奨認証・監査・集計が失敗 | 固定Prediction gateのSHA-256付き原本は維持しつつ、現行gateとの同一性比較を発走前固定対象（Production内容とevidence、契約・mode・cutoff・timing_route・Production KPI）に限定。結果後の`review.status=COMPLETE`更新は、Prediction checkerで適法な場合に許可する。固定予想の改変は引き続き拒否 | `test_31_review_completion_keeps_fixed_recommendation_verifiable`：回顧更新→verify/audit/report成功、timing_route変更拒否 |
| P2 明示的な推奨省略が買い目で上書き | `EXPLICIT_MARKS_ONLY`・`NO_RECOMMENDATION`・`PENDING` と選択済み`ticket_formations`の併存をエラーにする。未選択の候補だけなら明示状態を保持して点数0のまま検証 | `test_32_explicit_status_cannot_be_overwritten_by_ticket_formations`：3状態それぞれの矛盾拒否と無券保存 |

結果後に新規推奨を正式KPIへ昇格させる変更ではない。既存PR69のDraft・切替未実施・第3サイクル契約不変の条件を保持する。
