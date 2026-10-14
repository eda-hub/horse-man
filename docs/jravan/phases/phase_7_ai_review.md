# Phase 7 — 非UIのAI review

## 目的・依存

固定Prediction・独立Recommendation・該当Shadowの公式結果/回顧から、`docs/manual/50_review.md` に沿う説明・誤差分類・改善候補を構造化する。正式版はmanual READMEのv1.7.0を参照し、Phase4の画面や専用サーバーを前提にしない。初回scope全件の回顧を対象とし、未最終・推奨なし・低確信も除外しない。

チャット/Git/非UI CLIの運用と、Windows/JRA-VAN/DB・AI Adapterの実接続は別受入。以下のruntime設計を現行チャットの必須依存へ追加せず、未接続を稼働済みと呼ばない。

## 対象

- 固定原本・公式全頭結果・独立KPIのReview Package Builder
- 非UIのAI Adapterと利用者による明示的な呼出し
- review_session / review_message、token/cost記録（runtime接続時）
- 誤差分類・良好部分保護・次の検証の候補
- Rule Proposal schemaとADD/MODIFY/MERGE/DEPRECATE候補
- 昇格 / 継続検証 / 棄却 / 判断保留ステータス

## 受入条件

- AIなしでも非UIのPrediction→価格不要推奨→保存→公式結果/回顧が成立する。Phase4はN/Aとし、画面完成を待たない。
- AIの入力は必要最小限のReview Packageとし、固定原本のbaseline ID・release・cutoff・hash・race/date・公式結果を対応付ける。
- AIはDB/OS/`docs/manual/`へ直接書き込まず、同一レースの固定Prediction・推奨を変更しない。
- Prediction / Recommendation / Shadow / 任意市場のKPIと母数を独立に説明し、価格・実購入・払戻をPrediction/推奨評価の必須条件にしない。旧実購入・Bettingは当時のrelease/schemaによる読取診断に限定する。
- 初回scope全件の回顧と、入力・保存・比較の不足を保持する。未測定はnull、未実施を効果なしへ変換しない。
- 公式結果のrace/date・全出走集合・取消/同着・訂正履歴を照合し、推奨の的中は固定券から再計算する。回顧済み原本を結果に合わせて書き換えない。
- AI提案は `50_review` の非劣化・人間承認・別PRによる正式変更を迂回できない。合成検査成功を性能昇格へ代用しない。
- AI呼出しは利用者の明示操作で開始し、WebUI・ホスティングを実装しない。

旧回顧チャットUI・実購入必須の設計はGit履歴で参照する。取得・engine・結果接続の不足は後続の引継ぎで棚卸しし、本書の整合をruntime実装完了とは扱わない。
