# PR #93 レビュー指摘の修正・未完了証拠監査（2026年10月17日）

この文書は**当日レース終了後の修正記録**。発走前に存在しなかった証跡を補造せず、Production・推奨・Shadowの正式前向きKPIを後付けで昇格しない。

## 1. 推奨の初回・確認後receipt重複検知

- 対象コード：`scripts/task_completion.py` の `recommendation_completion()`。
- 旧判定：`artifact_id + artifact_path` が一致するreceiptを1件に限定し、同一原本について初回R01と読戻し済みR02を重複エラーとした。
- 修正：ゲートの `evidence_ref.receipt_id` と `artifact_id / artifact_path / persist_verified_at_jst` に一致するR02だけを個別の完了検査で照合。R01が `previous_receipt_ref` で指定されている場合は、前段の原本・SHA・保存時刻・保存状態が一致することを追加検証。
- **過去のR01とR02の双方を保持**。同一 `receipt_id` の重複、読戻し時刻不備、前段不一致は引き続き失敗させる。
- 回帰テスト：`python3 scripts/test_task_completion_receipt.py`。本ブランチ上で追加。実行環境における結果を確認してからマージ審査する。

## 2. 新潟11R・京都11R・東京11RのPrediction保存順序証拠

- 各レースの`intent`、独立`fix-manifest`、全頭Prediction JSON、および**Prediction本体については発走前のGitHub保存・R02読戻し**が残る。
- ただし現行の第4日次工程が要求する、`intent保存→intent読戻し→FIX保存→FIX読戻し→Prediction保存` の**3段階の独立した保存証跡（共通日次receipt）と順序照合が未完了**。
- 既存FIX/予想内容・commit・chat時刻を消去も変更もせず、欠損した当時の独立receiptを新たに発行しない。`docs/validation/reconciliations/2026-10-17-day-index.json` のレース行に不足理由を保持する。
- 予想本体の個別保存合格と、`check_cycle04.py` の日次Production適格は別判断。**日次Production KPIへ計上不可**。

## 3. 京都8R・新潟11Rの推奨

- **京都8R**：予想原本は保存済みで、ワイド3－6を提示した事実を`docs/validation/preservation/2026-10-17-kyoto-08-final-recommendation.md`に保持。ただし開始時のPrediction intentに独立推奨scopeがなく、正式Recommendation JSON・receipt・gateが欠損。遡及追加は行わない。
- **新潟11R**：見送り判断は`docs/validation/recommendations/2026-10-17/20261017-NIIGATA-11-REC-S01.json`に保存済み。ただし旧独自schemaの参考ファイルで、正式`recommendation-snapshot-v1`の原本・事前独立intent・receipt・gateの代用不可。参考ワイド6－17は正式採用ではない。
- 両レースとも推奨本文を消去せず、索引で`UNSEALED`として独立した**正式未完了**に分類。正規の推奨記録としての前向きKPIは不適格。これらを形式だけ整えて発走前FIXを作ったことにしない。

## 4. 全36R・公式scope・初回予想・日別台帳

- 朝の36レース事前宣言：`docs/validation/persistence-intents/2026-10-17/morning.json`。
- 初回全頭の独立Prediction保存・第4サイクル`cycle04-official-scope-v1`の事前登録は実施されていない。レース後に`cycle04-day-v1`を正式な事前台帳として作らない。
- 現存4レースの最終Prediction、東京9R・京都10Rの事後保全、残り30レースの未提出、京都8R・新潟11R・京都11R・東京11Rの推奨状態を、**36レース全数**で`docs/validation/reconciliations/2026-10-17-day-index.json`にリンクした。
- 読取専用の橋渡し監査：`python3 scripts/check_cycle04_unfinished.py --root . --manifest docs/validation/reconciliations/2026-10-17-day-index.json`。原本パスとFIXハッシュ・対象レースID・欠落と非適格状態を検査し、通常回顧で何が未取得か追跡できる。ただし**正式な当日scope登録、日別台帳、集計・回顧完了を代行しない**。
- 回帰テスト：`python3 scripts/test_cycle04_unfinished.py`。

## 作業後の残課題と完了境界

1. 回帰テストと、京都・東京11Rの`task_completion.py`個別推奨照合をGit checkout後に実行する。
2. 既存の第4サイクル正式日次登録・回顧は当日の事前証跡欠落により遡及完成不可。公式結果は事後照合資料として別途追記できるが、前向きKPIとは分ける。
3. 次開催日は、`cycle04_workflow.py --register-scope`で発走前に公式scopeを登録し、初回全頭予想と選定/推奨の独立intent・FIX・receiptを共通日次証跡に残してから最終化する。実際に揃った日のみ通常の結果・回顧へ接続する。

このPRを**Draftのまま**維持し、未実施のCLI検査やCIを「通過」と表示しない。

## 追加レビュー：京都10Rの参考候補と転記照合（P2×2）

- 京都10R「清滝特別」の発走前チャット参考購入候補は、既存の発走後保全文`docs/validation/preservation/2026-10-17-kyoto-10-final-late.md`に記された **ワイド6－7・1点**。全36R日次索引の推奨状態を`NOT_PERSISTED`から`UNSEALED_LATE_PRESERVATION_CANDIDATE`へ変更し、未封印判断索引にも登録した。**発走前の正式推奨原本・FIX・receipt・gateは新規生成しない**。
- 未封印判断の京都8R・京都10R・新潟11Rの各レコードには、出所ファイルの元の全バイトのSHA-256を保持し、監査`scripts/check_cycle04_unfinished.py`で本文の一致を確認する。
- 京都8Rは保全本文の`ワイド 3 アンムート－6 カレンハウ、1点`、京都10Rは`チャットでの参考購入候補: ワイド 6－7、1点`を、各々指定の原文行から一意に抽出する。JSONへの転記値（券種・馬番の順序・点数）と完全一致しない場合は監査を不合格にする。
- 新潟11Rの`NO_RECOMMENDATION`も原本JSONの`candidates_for_study`、`reason`、`status`、`official_recommendation: false`を照合して、**研究候補を正式買い目として取り扱わない**。
- テスト`scripts/test_cycle04_unfinished.py`に京都8R 3－6→1－2改変、京都10R 6－7→1－2改変、京都10R券種・点数改変、保全本文改変、未封印リンク欠落、新潟11R候補改変、京都10R正常参照を追加。
- 以上は**事後の回顧用索引と読取専用監査の修正**。正式日次台帳や過去の前向きKPI認証への昇格は行わない。
