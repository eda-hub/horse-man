# AI review and rule lifecycle

## 正本との関係
回顧・検証・正式変更の手順は `docs/manual/50_review.md` を正とする。AIはこのプロセスの補助であり、独自の昇格ルートを持たない。

## AIの役割
- Production予想理由の整合性確認
- Shadowとの差分説明
- 外れ/的中の偶然性分析
- オッズ予測評価
- Prediction順位・確率・根拠変更の整合性評価
- エラー分類候補
- 検証仮説・ルール改善候補の提案
- 重複/陳腐化したルールの整理候補

AIはProductionのmarks・確率・順位を決定する必須本体ではない。

## Review Package
Python側で必要最小限を構造化してAIへ渡す。
- `manual_release` / module hashes / Git commit SHA（取得可能なら）
- `baseline_forecast_id`
- レース条件とdata cutoff
- Production基準予想と根拠/rule IDs
- 条件別補正
- Shadow比較（存在時）
- observed / predicted final / actual final odds
- 初回→最終の順位・確率・根拠差分
- 結果/払戻
- 任意市場検証sidecar（存在時のみ）
- validation cycle context

## 全FINALを回顧対象
予想確信度や的中/外れに関係なく、全FINAL PredictionについてReview Packageを生成できるようにする。AI API呼出は初期版ではWeb UIの「AI回顧開始」で実行し、不要な費用を避ける。

## Rule Proposal
AI提案は少なくとも `ADD / MODIFY / MERGE / DEPRECATE` を扱う。ただし状態は `50_review` の検証ライフサイクルへ合わせ、**昇格 / 継続検証 / 棄却 / 判断保留**を表現できるようにする。

AI出力はPydantic schemaでValidationし、提案DBへ保存するだけ。`docs/manual/` のOwnerモジュールへ反映する場合は、人間承認後の別PRとする。

## 検証サイクル
`docs/manual/50_review.md` の現行サイクル定義と主Prediction KPIを実装時の正とする。任意市場sidecarのKPIもmanual側の契約に従い、数値をJRA-VAN設計書側へ重複定義しない。

## 過学習防止
時系列holdout等の統計検証を追加してよいが、manualの正式検証プロトコルを置換しない。AIが多数候補を生成した場合のselection biasも記録する。

## コスト管理
`review.review_message` にmodel、input/output tokens、estimated costを記録し、月額上限通知を設定可能にする。
