# Phase 6 — Result / Recommendation match / Review

## 目的

初回全scopeの公式結果を取得し、固定Prediction・独立推奨・Shadowを別系列で結果照合する。実購入settlementを必須にしない。

## 受入

推奨なし/印のみ/未最終もPrediction回顧を行う。baseline ID、release、cutoff、snapshot hashと公式結果のrace/dateを照合。Predictionと推奨的中KPIに払戻・実購入は不要。任意市場ROIは別。再試行・失効・取消・結果未確定を履歴化し、未来値を発走前予想へ戻さない。日別→サイクル集計を保存・読戻す。runtime Scheduler/Backupの実接続は独立Phase受入、未接続を稼働済みとしない。
