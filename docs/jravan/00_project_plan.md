# 競馬予想システム開発計画書 v0.1

## 1. 目的
JRA-VAN Data Labから取得したデータをローカルPCに蓄積し、Macの専用Web UIからレース予想、最終オッズ予測、買い目候補、購入/見送り判断、結果記録、回顧、ルール改善を一貫して行う。

## 2. 基本原則
- 競馬予想ルール原本を判断の正本とする。
- AIは予想本体ではなく、回顧・仮説・ルール改善支援に使用する。
- FINAL予想は確定後に上書きしない。
- 購入しなかったレースも予想記録、仮想損益、回顧を必ず残す。
- 実購入成績とシステム推奨の理論成績を分離する。
- バックテストで未来情報を使わない。
- 外部公開、自動投票、PAT/銀行情報の保存は行わない。

## 3. 利用環境
- 操作端末: 個人Mac
- JRA-VAN実行: Parallels上のWindows 11 VM
- JV-Link層: Python 3.14 + pywin32を第一候補
- API: FastAPI
- DB: DuckDB
- Archive: Parquet
- Web UI: TypeScript系を第一候補。既存Node.js資産を考慮してPhase 4で確定する。
- AI: 外部APIをAdapter経由で必要時のみ使用

## 4. スコープ
### 対象
- JRA-VANデータ自動取得
- レース/馬/血統/近走/騎手/調教師/調教/馬場/馬体重/オッズ
- PRE / DAY / FINAL予想
- ルール評価、統計特徴量、将来のML
- 最終オッズ予測
- 馬連・ワイドを中心とした買い目生成
- BET / SKIP判断
- 結果・払戻・仮想/実績精算
- AI回顧
- ルール提案・バックテスト・人間承認
- 自動バックアップ

### 非対象
- 自動投票
- PAT連携
- 公開Webサービス
- 多人数利用
- クラウドDB常時運用

## 5. 成功条件
- Macのブラウザだけで日常操作できる。
- Windows VMのJV-Link更新が中断しても再開できる。
- 過去FINAL予想を当時のデータで説明できる。
- 見送りを含む全FINAL予想が自動で結果/回顧へつながる。
- AIを停止しても予想・買い目・結果記録が動く。
- DB障害時にバックアップから復元できる。

## 6. 主要フェーズ
0. Foundation
1. JV-Link ingest
2. Data expansion
3. Feature / Rule engine
4. Prediction Web UI
5. Odds forecast / Betting decision
6. Result / Settlement / Automation
7. AI review
8. Backtest / Rule lifecycle

## 7. 確定事項
`DECISIONS.md` を参照。

## 8. 暫定事項
- Web UIフレームワーク
- Python依存管理ツールの最終選定
- MLモデルの採用有無/種類
- オッズ詳細保存頻度
- AIモデルの使い分け

## 9. 実装ルール
Codexには1フェーズずつ実装させる。各フェーズで受入条件、migration、テスト、rollback方法を確認してから次へ進む。
