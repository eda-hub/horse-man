# Data contract

入力契約の正本は`src/schemas.ts`、動作する最小例は`test/fixtures.ts`にある。記憶でフィールドを作らず、対象schemaとfixtureを確認してJSONを作る。

## 保存順序

一時JSONはリポジトリ外の一時ディレクトリへ作成し、次の順で検証・保存する。

```text
node dist/cli.js race import <dossier.json>
node dist/cli.js forecast save --race <id> --stage core --input <core.json>
node dist/cli.js forecast save --race <id> --stage final --input <final.json>
node dist/cli.js strategy save --race <id> --input <strategy.json> [--budget-yen N]
```

既存raceIdがある場合はdossierを再importしない。最新記録は`records/races/<id>/`で確認する。スナップショットは上書き不可なので、修正時はrevisionを増やす。

## 必須の整合性

- レースIDは`YYYY-MM-DD_<主催者>_<場コード>_<R>`を基本とし、英数字・`_`・`-`だけを使う。
- ISO 8601時刻にはUTC offsetを含める。日本競馬は`+09:00`。
- 勝率合計1、連対率合計2、3着内率合計3（少頭数は頭数まで）。各馬は勝率 ≤ 連対率 ≤ 3着内率。
- シナリオ確率合計1。各シナリオの全馬勝率合計も1。
- `keyFactors`は3件。◎は1頭。勝率1位と◎が違う場合は、価格以外の理由を`subjectiveConcern`へ書く。
- Finalにも全馬、全シナリオを含める。差分だけのJSONにはしない。
- 戦略の`mostLikelyRunnerNumber`はFinal勝率1位と一致させる。見送りならticketsは空。
- 全買い目で`stakeRatio`または`stakeYen`を統一する。比率合計は1。

CLIのwarningはレポートに残すべき監査事項、errorは修正必須の契約違反である。
