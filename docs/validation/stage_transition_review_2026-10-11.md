# R09 Stage 1→Stage 2切替の事前審査

- 観測日時: 2026-10-11 02:19:25 JST
- 対象: `eda-hub/horse-man`
- 判定: **保留 / WAIT_CYCLE_END**。Stage 1終了審査は未完了、Stage 2正式切替は未実施。
- 現行Production: `v1.6.1` を維持。
- 第3サイクル: 2026-09-26・27、10-03・04・10・11・12（JST）。
- 最早切替境界: 2026-10-13。審査合格・原子切替なしにこの日付だけで発効しない。
- このPRは事前審査とWebUI対象外の文書整合。正式変更のPRとは分離する。

## 1. 基準を固定した参照

| 参照 | 固定commit | 確認内容 |
|---|---|---|
| main | `4bf199799898fa5e48845bbe1c97ca1e35868c59` | manual入口、7日計画、日別4台帳、サイクル集計、運用受入、Phase文書 |
| PR68計画 | `a01dbb1bd805c1cd07a9c63e34767b4b6997c5d9` | 上位計画§17.3/17.4/19/21/25、血統詳細計画§8/11.6。WebUIの本文依存を同PRで訂正 |
| PR69準備実装 | `3da52035235a2c20b854b89499df695745b5403c` | 新旧Prediction dispatch、推奨の独立保存・監査、条件集計の準備。正式運用への切替とは区別 |

[実施手順](https://github.com/eda-hub/horse-man/pull/69#issuecomment-6094088273)のR09と、[計画正本PR68](https://github.com/eda-hub/horse-man/pull/68)に基づく。PR69の未マージ成果物をmainの運用規則として使わない。

参照したmainのGit blob SHA：

| ファイル | Git blob SHA |
|---|---|
| `docs/manual/README.md` | `848b25f425d98849aad94dd01d424aee8a39dcf6` |
| `docs/validation/cycle_03.md` | `6c9db4dd8b5856ec8843ff7e7d9fc5ca7323b4c6` |
| `docs/validation/records/2026-09-26.md` | `9caeaf512a4d3f852521e16d669cc43e240a28bb` |
| `docs/validation/records/2026-10-03.md` | `5033877c4687bf191a8ed0eb0c70e2f65b0439aa` |
| `docs/validation/records/2026-10-04.md` | `66b69183935897eb286c90445334c6bc428d4658` |
| `docs/validation/records/2026-10-10.md` | `a01e2f0cddd0adb6b9445248e20c033dd28b1a85` |
| `docs/validation/operation_acceptance_cycle03.md` | `70ea443ffb5ef9388641f663d9d978707ea6fb42` |

## 2. 第3サイクルを閉じられるか

取得したmainの機械台帳で確認した数。候補は検証用と購入用を重複除去して最終対象とする。初回数と最終数の一致を要求しない。

| 日付（JST） | 初回 | 検証候補 | 購入候補 | 最終完了 | 回顧 | 観測状態 |
|---|---:|---:|---:|---:|---:|---|
| 09-26 | 24 | 6 | 5 | 8 | 24 | 台帳あり |
| 09-27 | — | — | — | — | — | 固定したmainに日別台帳なし。元日次branchの確認・統合は終了時に別判定 |
| 10-03 | 24 | 6 | 5 | 5 | 24 | 台帳あり |
| 10-04 | 24 | 15 | 12 | 5 | 24 | 台帳あり |
| 10-10 | 24 | 7 | 0 | 7 | 24 | 台帳あり |
| 10-11 | — | — | — | — | — | 観測時点は開催前。固定したmainに台帳なし |
| 10-12 | — | — | — | — | — | 将来開催。終了後の結果・回顧・集計を未観測 |

4台帳の集合・集計整合は成功した。これは保存証跡の真正性、通常依頼だけでの一巡成功、性能合格を証明しない。未観測欄を0実績や空集合の正常終了に補完しない。

mainから取得した台帳を対象に、mainと同じGit blobの `scripts/check_cycle03.py`（`d01c74285b77122dd32851887a219f27fe5d883e`）で実行：

```text
--require-data
exit 0
CONSISTENT: 4 day ledgers, 3 scheduled dates absent, 10 KPI decisions pending; evidence authenticity is not checked

--require-data --require-complete
exit 1
INVALID: cycle closure requires a ledger for every scheduled day, including no-race days
```

終了時の全日照合は未成立。予定日後であっても、日次branch/mainの最新状態、無開催日の理由付き空台帳、scope/日別/サイクル集計を再確認してから閉じる。

## 3. Stage 1の終了審査対応

`cycle_03.md` §6〜8.1の受入・提出物に対応する。以下は今回の事前確認であり、10/12終了後の最終判定ではない。

| 審査対象 | 今回の確認 | 終了審査で必要なもの |
|---|---|---|
| 7開催日のscope・日別・集計 | 4日分整合、全日完了は未成立 | 全日台帳と一巡対象、最終未実施/回顧未実施、重複・漏れの照合 |
| 運用受入・介入・保存所要時間 | 既存受入には模擬/部分I/O/未実施の区分がある | LIVE実測、通常依頼と追加介入の区別、運用ゲートの実証範囲 |
| Betting処理量と最終/保存完了率 | 終了後評価待ち | 実測の処理量・遅延・最終未完了との関係 |
| 実購入記録の追加価値 | 終了後評価待ち | Prediction改善に必要だった情報と不要だった工程の比較 |
| 固定仮想精算の標準必須化 | 終了後評価待ち | 追加価値と処理コスト、任意sidecarとしての扱い |
| ☆印と順位・市場独立性 | 終了後評価待ち | 該当例・順位との整合、良好部分の保全 |
| 重賞過去傾向Shadow | 終了後評価待ち | 同一対象の追加価値・悪化例、Productionへの非逆流 |
| 弱い根拠による順位変更 | 終了後評価待ち | 変更前後・出所/観測時刻/強度・成否 |
| 相手レベル確認と低確信レース | 終了後評価待ち | 誤評価例・評価可能範囲・適格母数と不足 |
| 監査負荷と新旧契約互換 | PR69の準備回帰302件成功 | 実測の保存阻害と、正式切替一式での互換/end-to-end確認 |

新規案は「採用 / 継続検証 / 棄却 / 判断保留」に分類する。検証未実施を効果ありへ置換せず、単日の的中・収益で昇格しない。未達は理由と次サイクルの再試験を残す。

## 4. Stage 2へ進めるか

| 条件 | 今回の判定 |
|---|---|
| 10/12開催分まで終了審査済み | 未成立。将来の開催・結果を補完しない |
| Stage 1終了審査の合格記録 | 未成立。今回の判定は保留 |
| WebUI不要の計画整合 | PR68本文のPhase依存・受入ケース・推奨履歴を非UIへ訂正。独立PRでPhase 4 N/Aを明記 |
| 新releaseを同じ切替単位で整合 | 今回は切替しない。終了審査合格後の別PRで確認 |
| 有効日・有効化時刻 | 未確定。PR69の状態はPENDING、有効日/推奨有効日/有効化時刻はnull |
| v1.6.1と準備済みv2の履歴互換 | 準備回帰は成功。正式切替差分に対して再検証が必要 |
| Productionへの新feature昇格 | 行わない。集計は研究用、効果検証と正式採用を分離 |

原子的な切替対象は `docs/manual/` 全Owner、`AGENTS.md`、`DECISIONS.md`、validationテンプレート/入口、Prediction・Recommendationの宣言/receipt/gate/schema/contract-state、compliance/persistence/recommendation/cycle checkerとテスト、JRA-VAN Phase文書。manualやACTIVEだけを先に変えない。

旧価格付きBetting監査・旧☆・旧snapshotを保持する。新Recommendationの有効日・versionを明示し、準備済みv2や過去v1.6.1へ遡及必須化しない。

## 5. 今回の変更・検証と再開位置

- 現行manual/Prediction/既存KPI/サイクル原記録は変更しない。審査状態はこの文書へ記録する。
- AGENTSとJRA-VAN計画/Phase入口/Phase 4に、WebUI対象外/N/Aを反映。旧画面設計は参考として保持する。
- チャット提示、保存/読戻し、監査、結果照合、履歴失効を画面完成へ依存させない。画面以外の受入は維持する。
- PR68の上位・血統詳細計画を整合し、計画の正本はPR68に保つ。
- PR69準備実装の回帰302件が成功。今回の文書変更でchecker/schemaは変更しない。
- セルフレビューで、有効release変更・原台帳編集・仮の開催結果・WebUI実装・一時ファイル混入がないことを確認。

再開は10/12開催分の結果・回顧が確定した後に、最新mainと7日分の日次branchを照合するところから。Stage 1の提出物・各案の採否をこの終了審査PRで確定し、合格後にStage 2の原子切替PRを別途作成する。日付到来だけの自動切替は行わない。

rollbackはこの文書整合差分をrevertする。release/DB/Prediction履歴にmigrationはない。審査未完了のサイクルデータは削除しない。

