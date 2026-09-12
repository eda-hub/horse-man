# Web UI design

## ナビゲーション
- レース予想
- 回顧・AI研究室
- ルール状態
- Shadow / 検証
- 成績
- システム状態
- 設定

## レース予想ページ
表示項目:
- レース情報、発走時刻、馬場
- データ取得状態と最終更新時刻
- `manual_release` と使用module
- `baseline_forecast_id`
- Production基準順位・印・勝率/連対率/3着内率・予想確信度
- 能力/適性/展開等の根拠と適用rule ID
- 条件別補正の有無
- observed odds、predicted final odds、予測レンジ
- 市場評価、推奨馬、推奨買い目候補、買い条件/見送り条件

操作:
- データ再取得
- Production再計算（ルール契約上許される更新条件のみ）
- FINAL snapshot確定
- ユーザー購入条件入力（馬/券種/予算/リスク）
- BET
- SKIP（理由コード + 自由記述）
- User Note追加

オッズ更新だけでProduction順位を再作成しない。

## Shadow表示
Productionと混同しない別タブ/別枠で表示する。
- 対応 `baseline_forecast_id`
- 検証ルールID
- Productionとの差分
- Shadow順位/確率/比較買い目
- 現行validation cycle

Shadowを正式買い目として誤操作できないUIにする。

## 回顧・AI研究室
左: Production、Shadow、結果、市場、推奨候補、実購入/見送り、仮想/実損益
中央: AIとの会話
右: Rule Proposal、検証状態、採用/継続検証/棄却/保留

AIはReview Packageのみを受け取り、DBへ直接アクセスしない。

## 成績ページ
- 予想数
- 基準予想の勝/連対/複勝等
- 推奨買い目の理論成績
- 実購入成績
- 見送りレース仮想成績
- オッズ予測誤差
- Shadow比較KPI
- manual release別 / 競馬場別 / 距離別等

## ルール状態
`docs/manual/README.md` のrelease、各moduleのrelease/hash、整合性チェック結果をread-only表示する。Web UIからルール本文を直接編集しない。

## システム状態
JRA-VAN、DuckDB、job、backup、AI月額利用量、disk使用量、manual contract整合性を一覧表示する。
