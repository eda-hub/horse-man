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
- 主要根拠（事実・出所・時点・方向・強度）
- 初回→最終の順位・確率変更履歴
- observed odds、predicted final odds、予測レンジ（利用可能な場合）
- 任意の市場評価sidecar状態

操作:
- データ再取得
- Production再計算（ルール契約上許される更新条件のみ）
- FINAL snapshot確定
- 根拠・順位・確率の差分確認
- User Note追加
- 任意の市場検証sidecar実行（実装済みの場合）

オッズ更新だけでProduction順位を再作成しない。

## Shadow表示
Productionと混同しない別タブ/別枠で表示する。
- 対応 `baseline_forecast_id`
- 検証ルールID
- Productionとの差分
- Shadow順位/確率/根拠差分
- 現行validation cycle

ShadowをProductionとして誤操作・上書きできないUIにする。

## 回顧・AI研究室
左: Production、Shadow、結果、市場、初回→最終差分、根拠
中央: AIとの会話
右: Rule Proposal、検証状態、採用/継続検証/棄却/保留

任意の市場検証sidecarがある場合のみ、その結果をPrediction成績と分離して表示する。実購入の有無・金額・実損益は正式UIの必須機能にしない。

AIはReview Packageのみを受け取り、DBへ直接アクセスしない。

## 成績ページ
- 予想数
- 基準予想の勝/連対/複勝等
- 上位3頭勝ち馬捕捉率
- 確率精度 / Brier Score
- 順位変更の改善・悪化
- オッズ予測誤差
- 任意市場検証sidecar成績（実行時のみ）
- Shadow比較KPI
- manual release別 / 競馬場別 / 距離別等

## ルール状態
`docs/manual/README.md` のrelease、各moduleのrelease/hash、整合性チェック結果をread-only表示する。Web UIからルール本文を直接編集しない。

## システム状態
JRA-VAN、DuckDB、job、backup、AI月額利用量、disk使用量、manual contract整合性を一覧表示する。


## 印と根拠の表示契約

- 印はProduction順位に従って表示する。
- 4位以下は△として順位を併記する。
- 4位以下にも勝利可能性があるため、印だけで「勝てない」と表現しない。
- 上位馬は主要根拠を確認できる。
- 根拠には事実、出所/参照、観測時刻、評価方向、強度を表示できる。
- 初回→最終で順位が変わった場合、変更を生じさせた新情報を差分表示する。
- オッズや人気の変化だけをProduction順位変更理由として表示しない。
