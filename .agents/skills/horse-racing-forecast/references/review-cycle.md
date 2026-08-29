# Review and cycle workflow

原本0.6〜0.16、40〜43、46、48、50.7、Experimental Backlog、更新ルールを読む。

## 結果・購入・回顧

1. 公式確定結果と払戻を`RaceResult`へ保存する。
2. 実購入がある場合は推奨、ユーザー追加、裁量を区別した`PurchaseRecord`を保存する。自動投票は行わない。
3. Core、Module、Experimental、価格、馬券構造を別々に採点する。
4. A〜LまたはWIN5 W-A〜W-Fの主因・副因を選ぶ。事前予測不能な事故を操縦性ミスへ寄せない。
5. 結果を知らない当時の情報だけなら同じ予想をするか反実仮想を記録する。
6. 改善案は`ExperimentalHypothesis`としてReviewに添付し、原本へ書かない。

```text
node dist/cli.js result import <result.json>
node dist/cli.js purchase save --race <id> --input <purchase.json>
node dist/cli.js review save --race <id> --input <review.json>
node dist/cli.js report race --race <id>
```

## 2週間サイクル

```text
node dist/cli.js cycle report --from YYYY-MM-DD --to YYYY-MM-DD --format markdown
node dist/cli.js cycle report --from YYYY-MM-DD --to YYYY-MM-DD --format json
node dist/cli.js cycle report --from YYYY-MM-DD --to YYYY-MM-DD --format csv
```

正式集計は結果前に保存した`prospective`だけを対象とする。回収率だけでCoreを変更せず、予想精度、価格判断、レース選別、馬券構造、時間帯、補正、不確実性へ分解する。サイクル終了は更新時期ではなく改訂必要性の審査時期である。
