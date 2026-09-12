# Phase 7 — AI review

## 目的
全Production FINALをAIと回顧し、必要に応じShadow比較も参照しながら、`docs/manual/50_review.md` に沿った検証・改善候補を構造化する。

## 対象
- Review Package Builder
- AI Adapter
- 回顧チャットUI
- review_session / review_message
- token/cost記録
- error classification候補
- Rule Proposal schema
- ADD/MODIFY/MERGE/DEPRECATE候補
- 昇格 / 継続検証 / 棄却 / 判断保留ステータス

## 受入条件
- AIなしでもPhase 0-6が完全動作する。
- AIはReview Package以外を直接読めない。
- AIはDB/OS/`docs/manual/`へ直接書込めない。
- Production/Shadow/実購入を混同せず回顧できる。
- 見送り/的中レースも回顧できる。
- AI提案は `50_review` の正式変更手順を迂回できない。
- AI呼出は初期版ではユーザー操作で開始できる。
