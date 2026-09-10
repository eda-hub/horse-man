# AI review and rule lifecycle

## AIの役割
- 結果回顧
- 予想理由の整合性確認
- 外れ/的中の偶然性分析
- オッズ予測評価
- BET/SKIP判断評価
- ルール改善仮説の提案
- 重複/陳腐化したルールの整理候補

AIはmarksや買い目を決定する本体ではない。

## Review Package
Python側で以下だけを構造化してAIへ渡す。
- レース条件
- 出走馬の必要特徴量
- FINAL予想と根拠
- 適用rule IDs
- 推奨買い目
- decisionと判断時オッズ
- actual final odds
- 結果/払戻
- 過去傾向集計
- 現行ルール

## 全FINALを回顧対象
購入/見送り、的中/外れに関係なくReview Packageを自動生成する。AI API呼出は初期版ではWeb UIの「AI回顧開始」で実行し、不要な費用を避ける。

## Rule Proposal
Proposal type: `ADD / MODIFY / MERGE / DEPRECATE`
Status: `DRAFT -> BACKTESTED -> APPROVED | REJECTED`

AI出力はPydantic schemaでValidationし、提案テーブルへ保存するだけ。本番ruleへの反映は人間承認後。

## 過学習防止
ルール探索期間、validation期間、直近holdoutを時系列分割する。AIが多数候補を生成した場合の選択バイアスも記録する。

## コスト管理
`review.review_message` にmodel、input/output tokens、estimated costを記録し、月額上限通知を設定可能にする。
