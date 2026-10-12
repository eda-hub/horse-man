---
module: market_sidecar
manual_release: v1.7.0
manifest: docs/manual/README.md
depends_on:
  - core
produces:
  - market_acquisition_status
  - optional_market_validation
must_not_modify:
  - market_based_reranking
  - shadow_to_production_backflow
---

# 60_market — 任意市場sidecar

旧30_bettingの31〜34、35.3、45.1、49の価格/資金条件の移管先。市場はProduction/Recommendationの下流でのみ実行し、標準予想の必須Ownerではない。観測・予測最終・実最終価格を分け、未試行/失敗/締切/取得済未評価/取得済期待値不足を区分する。

実購入意思・購入確認・財布情報は入力にしない。仮想収益検証は、発走前に固定した価格・組合せ・仮想額・出所時刻がある場合だけ、独立KPIとして評価する。未取得を期待値不足へ変換せず、結果後に違反券だけ外してROIを書き換えない。市場・価格予測Shadowは正式能力順位・標準推奨へ逆流しない。
