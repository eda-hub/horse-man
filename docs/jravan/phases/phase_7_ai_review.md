# Phase 7 — AI review

## 目的
全FINAL予想をAIと回顧し、ルール改善候補を構造化して蓄積する。

## 対象
- Review Package Builder
- AI Adapter
- 回顧チャットUI
- review_session / review_message
- token/cost記録
- Rule Proposal schema
- ADD/MODIFY/MERGE/DEPRECATE

## 受入条件
- AIなしでもPhase 0-6が完全動作する。
- AIはReview Package以外を直接読めない。
- AIはDB/rulesへ直接書込めない。
- 見送り/的中レースも回顧できる。
- AI呼出は初期版ではユーザー操作で開始できる。
