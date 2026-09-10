# Web UI design

## ナビゲーション
- レース予想
- 回顧・AI研究室
- ルール管理
- バックテスト
- 成績
- システム状態
- 設定

## レース予想ページ
表示項目:
- レース情報、発走時刻、馬場
- データ取得状態と最終更新時刻
- ◎○▲☆△
- 総合/能力/血統/展開/傾向/EV
- 評価理由、適用ルール、近走、血統
- observed odds、predicted final odds、予測レンジ
- 推奨買い目と予算配分

操作:
- データ再取得
- 予想再計算
- FINAL確定
- BET
- SKIP（理由コード + 自由記述）
- User Note追加

FINAL確定後は当該revisionを上書きしない。

## 回顧・AI研究室
左: レース結果、FINAL予想、買い目、判断、仮想/実損益
中央: AIとの会話
右: Rule Proposal、Backtest結果、採用/保留/却下

AIはReview Packageのみを受け取り、DBへ直接アクセスしない。

## 成績ページ
- 予想数
- ◎勝/連対/複勝率
- 馬連/ワイド的中率・回収率
- 理論回収率 / 実購入回収率
- 見送り件数 / 見送りレース仮想回収率
- GOOD SKIP / MISSED OPPORTUNITY
- 競馬場/距離/人気/ルールversion別
- 最大連敗、最大ドローダウン

## システム状態
JRA-VAN、DuckDB、job、backup、AI月額利用量、disk使用量を一覧表示する。
