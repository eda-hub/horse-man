# Phase 4 — Prediction Web UI

## 適用状態：対象外/N/A（2026-10-10 利用者指定）

WebUIの新規作成・改修・画面連携・ホスティングは行わない。本Phaseは後続Phaseの依存条件・未完了残件に含めない。以下は参考設計であり、画面の実施・合格を要求しない。

チャット出力・保存/読戻し・監査・Prediction/Shadow分離・結果照合・改訂前履歴の失効は非UI処理で検証し、省略しない。

## 参考：旧目的
MacのブラウザからProduction予想、条件別補正、Shadow比較を混同せず確認・操作できるようにする。

## 参考：旧対象（実施しない）
- レース一覧 / race detail
- `manual_release` / module整合性表示
- `baseline_forecast_id`
- Production順位・印・確率・予想確信度・構造化根拠
- 初回→最終の順位・確率・根拠差分
- 条件別補正
- PRE/DAY/FINAL snapshot切替
- FINAL snapshot確定
- Shadow比較専用表示
- 任意市場検証sidecar表示（実装時のみ）
- User Note
- data freshness/status
- FINAL data readiness panel
- 馬体重・馬場・変更eventの取得時刻/source表示
- 馬体重の発表検知時刻・最終取得時刻・acquisition method・coverage表示

## 参考：旧次期推奨買い目（PR68 §25、Stage 2発効後）

- 固定済みPredictionに紐づく推奨買い目の券種・馬番組合せ・点数・優先順位・構成理由を表示し、推奨なし/明示印のみ/未完了も識別する。
- 改訂前の推奨は失効を表示し、取消・Prediction変更後の古い構成を有効な最終推奨として扱わない。
- 予算入力・実購入確認・払戻入力がない状態で推奨を確認できる。PR69の日本語CLI表示は準備実装でありWebUI実画面の代用としない。

## 参考：旧画面受入条件（対象外/N/A）
- MacからWindows VMへローカル接続できる。
- Internetへ公開されない。
- ProductionとShadowが視覚的・操作的に明確に分離される。
- 実購入・BET/SKIP・予算入力がなくてもPredictionの全操作を完了できる。
- 4位以下の勝利可能性を印だけで否定せず、確率・レンジ・根拠を確認できる。
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

