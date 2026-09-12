# Phase 4 — Prediction Web UI

## 目的
MacのブラウザからProduction予想、条件別補正、Shadow比較を混同せず確認・操作できるようにする。

## 対象
- レース一覧 / race detail
- `manual_release` / module整合性表示
- `baseline_forecast_id`
- Production順位・印・確率・予想確信度・根拠
- 条件別補正
- PRE/DAY/FINAL snapshot切替
- FINAL snapshot確定
- Shadow比較専用表示
- User Note
- data freshness/status

## 受入条件
- MacからWindows VMへローカル接続できる。
- Internetへ公開されない。
- ProductionとShadowが視覚的・操作的に明確に分離される。
- FINAL確定前後の状態が明確。
- オッズ更新だけでProduction baselineを作り直す操作にならない。
- manual release不整合がUI上で警告され、予想実行を停止できる。
- Web UIから任意SQL/OSコマンドやルール本文編集を実行できない。
