---
name: horse-racing-forecast
description: horse-manのJRA-VAN競馬予想システムを、現行のモジュール化競馬予想ルールと設計書に従ってCodexで段階実装・検証する。
---

# Horse Racing Forecast System

競馬判断の正本は `docs/manual/`、システム設計の正本は `DECISIONS.md` と `docs/jravan/` とする。ルールの入口は必ず `docs/manual/README.md`。

## 責務境界

このSkillは**将来のローカルシステムのコード実装・検証専用**とする。ChatGPT上でその場のレース情報をWeb等から取得して予想する処理とは混合しない。

- `docs/manual/` はチャット予想を含む競馬判断・実行要件を定義するが、JV-Link API、イベント監視、DB、polling等の実装方法を定義しない。
- `DECISIONS.md` と `docs/jravan/` はローカルシステムの実装方法を定義するが、ChatGPTが現在利用できる取得経路を表すものではない。
- `JVEvtWeight`, `0B11`, `JVWatchEvent`, DuckDB、catch-up等は**ローカルシステム実装の語彙**であり、チャット予想の取得元として扱わない。
- チャット側のWeb取得障害を理由に、将来システムの設計をその場しのぎで変更しない。逆に、将来システムの設計があることを理由にチャット側で取得済みとみなさない。

## 実装開始時
1. ルートの `AGENTS.md` を読む。
2. `docs/manual/README.md` を読み、現行 `manual_release` とOwner構造を確認する。
3. `DECISIONS.md` と `docs/jravan/00_project_plan.md` を読む。
4. 実装対象Phaseの `docs/jravan/phases/phase_*.md` を読む。
5. 実装対象が予想ロジックに関係する場合だけ、必要なOwnerモジュールを読む。
6. JRA重賞記録に関係する場合は `docs/yosou/jra_racing/README.md`、Shadow検証に関係する場合は `docs/validation/` の現行サイクルを確認する。
7. 当日馬体重取得を実装する場合は、`docs/manual/README.md` は「当日馬体重取得が必要」という機能要件としてのみ参照し、具体実装は ADR-019、`docs/jravan/03_jravan_mapping.md`、`docs/jravan/10_operations.md`、対象Phaseの受入条件に従う。
8. Phaseの受入条件を満たす最小実装を行う。

## ルール境界
- Productionの基本方向は `00_core → 10_prediction → 20_conditional → 30_betting`。
- `40_shadow` はProduction固定後の比較系で、Productionへ逆流させない。
- `50_review` は結果後の回顧・検証・変更管理で、過去Productionを遡及変更しない。
- 必須モジュール間の `manual_release` が一致しなければ処理を停止する。
- `baseline_forecast_id` を予想の同一性キーとして保持する。
- PRE / DAY / FINALはデータ時点のsnapshotであり、上記Owner境界を置き換えない。
- ローカルシステムの馬体重取得・coverage・readinessは `docs/jravan/` の設計契約に従う。

## 共通制約
- Phaseを跨いで先回り実装しない。
- 旧Node/TypeScript CLIを復元しない。
- `.agents/` と `.devcontainer/` を削除しない。
- `docs/manual/` を実装都合で自動改変しない。
- `docs/manual/` と重複するルール正本を `rules/` 等に作らない。
- FINAL予想を結果に合わせて上書き可能にしない。
- 見送りレースを記録・回顧対象から除外しない。
- AIをPrediction Engineの必須依存にしない。
- AIにDB/OS/ルールの直接変更権限を与えない。
- PAT、自動投票、銀行情報保存を実装しない。
- `data_cutoff` より未来の情報をバックテスト/予想へ混入させない。
- 当日馬体重が取得できない場合に前走馬体重・調教後馬体重を当日値として補完しない。


## 保存拒否と発走時計の是正（2026-10-17、実装後の新規試行に適用）

正式レースでの発走前保存は次の順序を必須とする。未マージのPR・計画を既存本番で有効と自己申告しない。

1. 対象開催日とrace ID、公式scope、公式発走変更chain、日次branchと作業対象pathを確認する。実際のChatGPT/GitHub連携の権限と利用経路を確認する。未確認なら成功と表現しない。
2. 書込み直前・本体読戻し直後・receipt読戻し直後に、現在UTCを取得して `prediction_clock.py` / `verify_prediction_persistence.py --clock-status --date YYYY-MM-DD --clock-race-id RACE_ID` で判定する。第4運用入口は `cycle04_workflow.py --clock-status --date YYYY-MM-DD --clock-race-id RACE_ID`。JST表示、残秒、根拠、状態を返す。実時計が取れない環境では読取専用の計算値を用意できても、実測と混同せず時刻未判定とする。時計が5秒超古い、オフセット/秒精度がない、monotonicとの乖離が2秒超、境界不明なら未判定。予定到達は実発走確認済みではない。
3. 正式intentは分析前にGit保存・固定commitから同一bytes読戻しする。FIX独立manifest→本体→receipt→個別検査の順序を守る。自己申告のreadback、ローカル保存、Actions成功だけで正式完了にしない。
4. 固定bytesとSHA-256を保持し、障害を `prediction_persistence_io.py` の拒否分類・操作記録に残す。権限/branch制約、SHA競合、通信/timeout、CI失敗、安全性拒否、理由不明を分ける。拒否された操作を別経路や高権限で迂回しない。通信系のみ、同一原本の遠隔読取り後に最大2回まで許可済みの保存を再試行する。独立した許可済み経路がなければ切替不可と明記する。
5. 実行環境にPythonと承認済みGitHub Contents API認証情報がある場合は、`python3 scripts/prediction_persistence_io.py --date YYYY-MM-DD --race-id RACE_ID --path RELATIVE_PATH --payload-file FIXED_FILE --operation-id UNIQUE_ID --write` を使用できる。既存ファイル更新は事前にSHA競合を確認して `--allow-update` を明示する。トークンや権限の自動取得・branch自動作成はしない。ChatGPTのGitHub連携利用時は同等の書込→返却commit固定読戻しを連携ツールで実行し、Pythonアダプター成功と取り違えない。
6. 失敗時は固定原本と秘匿済み障害記録を実行環境に保全し、GitHub正式保存は未完了と表示する。機密文字列を公開リポジトリに記録しない。事故記録の正式保存先は `docs/validation/persistence-incidents/YYYY-MM-DD/` だが、これは当時のreceiptを代替しない。旧データ・過去の証跡を遡及補完しない。

時計判定・保存成功・読戻し一致・宣言/FIX順序・個別完了・正式KPIは独立した項目として表示する。現在の時計が発走後というだけで、過去の固定commitによる発走前保存を遅延へ書換えない。実チャット/予約/再開の経路試験は合成CIと別に記録する。安全性拒否の内部理由はログ未取得につき未確定のまま扱う。

## 完了時
- テストを追加・実行する。
- Phase受入条件を確認する。
- 設計変更があれば `DECISIONS.md` または対象docsを更新する。
- 次Phaseの機能を混ぜずにPRを完結させる。
