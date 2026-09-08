# Testing and quality

## DB/Parser
- JV Record -> internal DTOのfixture test
- 欠損/異常値Validation
- duplicate ingest idempotency
- migration forward test

## 時点再現
固定レースfixtureで `data_cutoff` 後の馬体重、結果、最終オッズ等がfeatureへ混入しないことをテストする。

## Prediction regression
過去に実際に扱った重賞をfixture化し、ルール適用件数、feature、marks生成過程が意図せず変わらないか確認する。予想結果そのものを永遠に固定するのではなく、version変更を明示的にする。

## Settlement
的中、不的中、返還、同着、取消等をテストする。理論購入と実購入を混同しない。

## Backup
Export -> fresh DuckDB import -> row count / key history確認を自動化する。

## AI
AI出力schema validation、無効proposal拒否、DB直接書込不可をテストする。AI応答内容そのものは厳密固定しない。

## バックテスト品質
- Discovery / Validation / Holdoutを時系列分割
- sample sizeを表示
- 回収率だけでなく勝/連対/複勝、分散、ドローダウンも確認
- 複数候補から都合の良いものだけ選ぶselection biasを記録

## CI
Phase 0でPython lint/type/testを構築する。JV-Link実機依存テストは一般CIから分離し、Windows VM上のintegration testとして実行する。Web UI追加後はそのlint/type/testを追加する。
