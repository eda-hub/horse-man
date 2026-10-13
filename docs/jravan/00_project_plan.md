> v1.7.0 / PR79のmainマージ後の正式境界：標準はPrediction→価格不要Recommendation→公式結果/回顧。実購入・予算・購入確認・実購入ROIは中核対象外。市場は60_marketの任意sidecar、WebUIは対象外/N/A。以下の旧BET/SKIP/実購入設計は履歴であり新規runtimeへ移植しない。正式Ownerはdocs/manual、関連Phase3/5/6を参照。Windows/JRA-VAN実接続の受入をチャット/Git運用成功で代用しない。

# 競馬予想システム開発計画書 v0.2

## 1. 目的
JRA-VAN Data Labから取得したデータをローカルPCに蓄積し、Macの専用Web UIからProduction基準予想、Shadow比較、最終オッズ予測、買い目候補、購入/見送り判断、結果記録、回顧、検証を一貫して行う。

## 2. 基本原則
- 競馬判断は `docs/manual/` の現行モジュールを正本とし、システム設計で独自ルールを再定義しない。
- 現行releaseはmanifestから読み、必須モジュールの `manual_release` 一致を検証する。
- ProductionとShadowを完全分離し、Shadowの結果を同一レースのProductionへ逆流させない。
- `baseline_forecast_id` を基準予想の同一性キーとして保持する。
- AIは予想本体ではなく、回顧・仮説・ルール改善支援に使用する。
- FINAL予想は確定後に結果に合わせて上書きしない。
- 購入しなかったレースも予想記録、仮想損益、回顧を必ず残す。
- 実購入成績とシステム推奨の理論成績を分離する。
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
- Web UI: Phase 4で技術選定
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
- `docs/manual/30_betting.md` に従う市場評価・買い目生成
- ユーザーBET / SKIP判断
- 結果・払戻・仮想/実績精算
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
- Macのブラウザだけで日常操作できる。
- Windows VMのJV-Link更新が中断しても再開できる。
- 過去Predictionを `manual_release`、module hash、data cutoffとともに再現・説明できる。
- ProductionとShadowを同一 `baseline_forecast_id` で比較でき、逆流しない。
- 見送りを含む全FINAL予想が自動で結果/回顧へつながる。
- AIを停止しても予想・買い目・結果記録が動く。
- DB障害時にバックアップから復元できる。

## 7. 主要フェーズ
0. Foundation
1. JV-Link ingest
2. Data expansion
3. Feature / Rule engine
4. Prediction Web UI
5. Odds forecast / Betting decision
6. Result / Settlement / Automation
7. AI review
8. Backtest / Rule lifecycle

## 8. 暫定事項
- Web UIフレームワーク
- Python依存管理ツールの最終選定
- MLモデルの採用有無/種類
- オッズ詳細保存頻度
- AIモデルの使い分け
- DBからGit上のJRA重賞Markdownへ自動同期する時期と方式

## 9. 実装ルール
Codexには1フェーズずつ実装させる。各フェーズでmigration、テスト、受入条件、rollback方法を確認してから次へ進む。`docs/manual/` の意味変更はJRA-VAN実装PRへ混在させない。
