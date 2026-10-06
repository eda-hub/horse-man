# Phase 8 — Backtest / Validation / Rule lifecycle

## 目的
AIや人間が作った改善候補を、Productionを汚さずShadow/バックテストで検証し、`docs/manual/50_review.md` の正式手順へ接続する。

## 対象
- backtest runner
- data cutoff enforcement
- validation cycle管理
- Production vs Shadow comparison
- sample size / ranking metrics / probability calibration / hit rate
- optional market validation return / drawdown
- manualで定義されたPrediction主KPIの集計
- feature単位の追加価値・非劣化比較
- proposal status管理
- Owner moduleへの変更候補diff生成
- release/hash更新支援

## 受入条件
- data_cutoff違反が検出される。
- 同一 `baseline_forecast_id` でProduction/Shadow比較ができる。
- manual release別の比較ができる。
- 旧releaseの実購入・Betting KPIを次期Prediction KPIへ自動混入しない。
- 近5走相手レベル、開催傾向、新馬等のfeatureを1つずつProduction対Shadowで比較できる。
- AI提案を自動承認しない。
- 正式採用は人間承認後の別PRとしてのみ行える。
- 採用時はOwner moduleとmanifestのrelease整合性を検査する。
- 過去Productionのmanual release/hash/baseline IDは変更されない。
- `docs/validation/` の現行サイクル運用と矛盾しない。
