# Phase 8 — Backtest / Rule lifecycle

## 目的
AIや人間が作ったルール改善候補を定量検証し、安全にversion管理する。

## 対象
- backtest runner
- discovery / validation / holdout
- proposal comparison
- sample size / hit rate / return / drawdown
- rule approval/reject UI
- new rule version生成
- rule deprecation/merge

## 受入条件
- data_cutoff違反が検出される。
- 旧/新ルールの同一期間比較ができる。
- AI提案を自動承認しない。
- 採用時にrule versionとhashが更新される。
- 過去FINAL予想のrule versionは変更されない。
