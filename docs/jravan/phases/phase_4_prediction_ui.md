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
- FINAL data readiness panel
- 馬体重・馬場・変更eventの取得時刻/source表示
- 馬体重の発表検知時刻・最終取得時刻・acquisition method・coverage表示

## 受入条件
- MacからWindows VMへローカル接続できる。
- Internetへ公開されない。
- ProductionとShadowが視覚的・操作的に明確に分離される。
- FINAL確定前後の状態が明確。
- オッズ更新だけでProduction baselineを作り直す操作にならない。
- manual release不整合がUI上で警告され、予想実行を停止できる。
- Web UIから任意SQL/OSコマンドやルール本文編集を実行できない。
- T-20では、保存済み当日馬体重のcoverage、最新馬場、取消/変更eventについて、取得済み/部分取得/欠損/旧データ/取得障害をレース単位で確認できる。
- 馬体重について `PENDING / READY / PARTIAL / MISSING / STALE / SOURCE_ERROR` を表示でき、`READY` が「T-20以降に取得した」という意味にならない。
- 馬体重の `first_observed_at`, `captured_at`, source, `EVENT/POLL/CATCH_UP/FALLBACK` の取得経路、取得済み頭数/対象頭数を確認できる。
- `PARTIAL` の場合は欠損馬番を表示できる。
- `data_readiness=DEGRADED` の場合は欠損項目と最終成功時刻・最終試行時刻を明示し、READYと同じ見た目でFINAL確定しない。
- `SOURCE_ERROR` の判定自体はingest/readiness層で行い、UIはその状態・根拠・最終試行時刻を表示する。UIが外部サイトを独自に照合して障害判定しない。
