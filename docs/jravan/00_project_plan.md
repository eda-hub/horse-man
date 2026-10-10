# 競馬予想システム開発計画書 v0.2

## 1. 目的
JRA-VAN Data Labから取得したデータをローカルPCに蓄積し、チャットと非UI処理でProduction基準予想、Shadow比較、最終オッズ予測、結果記録、回顧、検証を一貫して行う。次期契約では、実際の購入馬券・購入額・購入有無はユーザー領域とし、システム中核から分離する。

## 2. 基本原則
- 競馬判断は `docs/manual/` の現行モジュールを正本とし、システム設計で独自ルールを再定義しない。
- 現行releaseはmanifestから読み、必須モジュールの `manual_release` 一致を検証する。
- ProductionとShadowを完全分離し、Shadowの結果を同一レースのProductionへ逆流させない。
- `baseline_forecast_id` を基準予想の同一性キーとして保持する。
- AIは予想本体ではなく、回顧・仮説・ルール改善支援に使用する。
- FINAL予想は確定後に結果に合わせて上書きしない。
- 低確信レースも予想記録・回顧から除外しない。
- 仮想収益検証を行う場合は任意sidecarとし、Prediction KPIと分離する。
- バックテストで未来情報を使わない。
- 外部公開、自動投票、PAT/銀行情報の保存は行わない。

## 3. 現在のGit領域
```text
docs/manual/                 競馬予想ルール正本
docs/yosou/jra_racing/       JRA重賞の長期記録
docs/yosou/kaigai/           海外競馬記録
docs/validation/             現行Shadow検証サイクル
docs/jravan/                 システム設計
.agents/                     Codex設定・スキル
.devcontainer/               Codex開発環境
```

これらはPhase実装で勝手に再配置しない。

## 4. 利用環境
- 操作端末: 個人Mac
- JRA-VAN実行: Parallels上のWindows 11 VM
- JV-Link層: Python 3.14 + pywin32を第一候補
- API: FastAPI
- DB: DuckDB
- Archive: Parquet
- Web UI: 対象外/N/A（2026-10-10 利用者指定）
- AI: 外部APIをAdapter経由で必要時のみ使用
- Codex: `.agents/` と `.devcontainer/` を利用

## 5. スコープ
### 対象
- JRA-VANデータ自動取得
- レース/馬/血統/近走/騎手/調教師/調教/馬場/馬体重/オッズ
- PRE / DAY / FINALのデータ時点snapshot
- Production基準予想・条件別補正
- Shadow比較
- ルール適用・特徴量・統計・将来のML
- 最終オッズ予測
- 市場評価・最終オッズ予測
- 任意の固定ルール仮想収益検証sidecar
- 結果・払戻の取得とPredictionへの結合
- AI回顧
- 検証サイクル・バックテスト・人間承認
- 自動バックアップ

### 非対象
- 自動投票
- PAT連携
- 公開Webサービス
- 多人数利用
- クラウドDB常時運用

## 6. 成功条件
- チャットと非UI処理で予想提示・保存・監査・結果照合を完結できる。画面実装は成功条件にしない。
- Windows VMのJV-Link更新が中断しても再開できる。
- 過去Predictionを `manual_release`、module hash、data cutoffとともに再現・説明できる。
- ProductionとShadowを同一 `baseline_forecast_id` で比較でき、逆流しない。
- 低確信レースを含む全FINAL予想が自動で結果/回顧へつながる。
- AIを停止しても予想・Shadow・結果記録が動く。
- DB障害時にバックアップから復元できる。

## 7. 主要フェーズ
0. Foundation
1. JV-Link ingest
2. Data expansion
3. Feature / Rule engine
4. Prediction Web UI（対象外/N/A・参考設計）
5. Odds forecast / Market validation
6. Result / Review preparation / Automation
7. AI review
8. Backtest / Rule lifecycle

## 8. 暫定事項
- Web UIフレームワークは選定しない（対象外/N/A）
- Python依存管理ツールの最終選定
- MLモデルの採用有無/種類
- オッズ詳細保存頻度
- AIモデルの使い分け
- DBからGit上のJRA重賞Markdownへ自動同期する時期と方式

## 9. 実装ルール
Codexには1フェーズずつ実装させる。各フェーズでmigration、テスト、受入条件、rollback方法を確認してから次へ進む。`docs/manual/` の意味変更はJRA-VAN実装PRへ混在させない。

