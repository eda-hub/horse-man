---
name: horse-racing-forecast
description: 競馬予想ルール原本v1.4.1を使い、公開情報の調査、単一レース予想、開催全体選出、WIN5分析、直前更新、結果回顧をhorseman CLIへ記録する。一般的な競馬談義や原本改訂には使用しない。
---

# Horse Racing Forecast

原本を判断の正本、`horseman`を検証・記録の正本として使う。原本は編集しない。

## 開始手順

1. リポジトリルートで `npm run build` と `node dist/cli.js rules verify` を実行する。失敗した場合は予想記録を停止する。
2. `競馬予想ルール原本_v1.4.1.md` の0章、標準予想フロー、対象モードに必要な本文を直接読む。過去チャットの暗黙知を根拠にしない。
3. 対象モードのreferenceだけを読む。
   - 単一レース、事前予想、直前更新: [single-race.md](references/single-race.md)
   - 開催全体の①/②/①＋②/見送り: [screening.md](references/screening.md)
   - WIN5: [win5.md](references/win5.md)
   - 結果登録、回顧、2週間集計: [review-cycle.md](references/review-cycle.md)
4. JSON作成時は [data-contract.md](references/data-contract.md) を読む。

## 共通制約

- 公開情報だけを調査し、JRAまたは海外主催者の公式情報を優先する。二次情報は補助として出典、取得時刻、情報時点、鮮度、信頼度、関連性を残す。
- Webページ本文を保存せず、予想に必要な短い事実とURLだけを`Evidence`へ保存する。情報が競合する場合は両方を残し、公式情報を優先して情報不確実性を上げる。
- 事実、解釈、今回予測を分離する。市場オッズをCore能力順位へ逆流させない。
- 最初のCoreを保存してから該当ModuleとExperimentalを差分適用する。監査項目を独立加点しない。
- 原本にない重み、購入上限、穴軸条件、WIN5固定条件を発明しない。判断根拠を記録し、未確定の基準は警告またはExperimentalとして扱う。
- 結果確認後に作った予想は必ず`reconstructed`とし、`prospective`へ偽装しない。
- 予算未指定時は金額を仮定せず資金比率を使う。投票操作は行わない。
- CLIがerrorを返したJSONは保存しない。warningは内容を確認し、合理的なら理由を明示して継続する。

## 出力

正式予想を保存したら `node dist/cli.js report race --race <id>` を実行し、そのレポートを基に回答する。回答には情報基準時刻、主要根拠、確率、確信度、区分、最も勝つ馬、最も買いたい馬、買い目または見送り理由を含める。
