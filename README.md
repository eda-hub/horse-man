# horse-man

`競馬予想ルール原本_v1.4.1.md`を判断の正本として、Codexによる予想、確率・馬券構造の監査、結果回顧、2週間サイクル集計をGit管理可能なJSONへ保存するローカルCLIです。

## セットアップ

```bash
npm install
npm run build
node dist/cli.js rules verify
```

Node.js 22以上を使用します。正式記録は既定で`records/`へ保存され、同一revisionの上書きは拒否されます。保存前には毎回ルール原本のSHA-256を検証します。

## 基本フロー

入力JSONの契約は`src/schemas.ts`、動作する例は`test/fixtures.ts`を参照してください。

```bash
# レース情報、Core、Final、馬券戦略
node dist/cli.js race import /tmp/dossier.json
node dist/cli.js forecast save --race 2026-08-29_JRA_TKY_11 --stage core --input /tmp/core.json
node dist/cli.js forecast save --race 2026-08-29_JRA_TKY_11 --stage final --input /tmp/final.json
node dist/cli.js strategy save --race 2026-08-29_JRA_TKY_11 --input /tmp/strategy.json

# 開催比較と単一レースレポート
node dist/cli.js screen report --date 2026-08-29
node dist/cli.js report race --race 2026-08-29_JRA_TKY_11

# WIN5分析、最終計画、回顧
node dist/cli.js win5 analyze --date 2026-08-29 --max-points 64
node dist/cli.js win5 save --input /tmp/win5-plan.json
node dist/cli.js win5 review --input /tmp/win5-review.json

# 結果、購入、回顧、検証サイクル
node dist/cli.js result import /tmp/result.json
node dist/cli.js purchase save --race 2026-08-29_JRA_TKY_11 --input /tmp/purchase.json
node dist/cli.js review save --race 2026-08-29_JRA_TKY_11 --input /tmp/review.json
node dist/cli.js cycle report --from 2026-08-16 --to 2026-08-29 --format markdown
```

`--records <path>`で記録先、`--rules <path>`で原本パスを変更できます。環境変数`HORSEMAN_DATA_DIR`、`HORSEMAN_RULES_FILE`も利用できます。

## Codexスキル

`.agents/skills/horse-racing-forecast/`に、公開Web情報の調査からCLI記録までを案内するプロジェクトスキルがあります。単一レース、開催全体、WIN5、回顧を必要時だけ読み分け、原本本文は複製せず直接参照します。

公開情報のみを対象とし、主催者公式を優先します。システムは買い目提案と手動購入記録までを扱い、自動投票は行いません。

## 検証

```bash
npm run check
```

format、lint、型検査、単体・統合テスト、ビルドをまとめて実行します。
