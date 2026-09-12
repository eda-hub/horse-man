# Testing and quality

## Manual contract
- `docs/manual/README.md` の現行releaseを取得できること
- 必須moduleの `manual_release` 不一致をfail closedできること
- module hash / manifest hashをPredictionへ固定保存できること
- Owner境界を跨ぐ実装マッピングを静的/単体テストで検出できること

## Production / Shadow分離
- Shadowは固定済Productionなしでは生成できない
- ShadowからProduction順位・確率・正式買い目を更新できない
- 同一 `baseline_forecast_id` で比較できる
- オッズ更新だけではProduction baseline IDを更新しない

## DB/Parser
- JV Record -> internal DTOのfixture test
- 欠損/異常値Validation
- duplicate ingest idempotency
- migration forward test

## 時点再現
固定レースfixtureで `data_cutoff` 後の馬体重、結果、actual final odds等が予想featureへ混入しないことをテストする。

## Prediction regression
`docs/yosou/jra_racing/` の代表重賞をfixture元として、rule ID適用、主要feature、Production/Shadow生成過程が意図せず変わらないか確認する。予想結果そのものを永遠に固定するのではなく、manual release / engine version変更を明示する。

## Betting
価格情報でProduction基準能力順位が変わらないこと、ユーザー指定馬/券種/予算が購入設計だけに作用することをテストする。

## Settlement
的中、不的中、返還、同着、取消等をテストする。理論推奨、Shadow比較、実購入を混同しない。

## Validation cycle
`docs/manual/50_review.md` のサイクル状態とDBのvalidation cycleを対応させる。サイクル終了後に過去Productionを書き換えない。

## Backup
Export -> fresh DuckDB import -> row count / key history / baseline ID / manual hash確認を自動化する。

## AI
AI出力schema validation、無効proposal拒否、DB/ルール直接書込不可をテストする。AI応答内容そのものは厳密固定しない。

## バックテスト品質
- data cutoffを強制
- sample sizeを表示
- 回収率だけでなく的中率、分散、ドローダウン等も確認
- 複数候補から都合の良いものだけ選ぶselection biasを記録
- manualの正式検証KPIと統計研究用KPIを混同しない

## CI
Phase 0でPython lint/type/testを構築する。JV-Link実機依存テストは一般CIから分離し、Windows VM上のintegration testとして実行する。Web UI追加後はそのlint/type/testを追加する。
