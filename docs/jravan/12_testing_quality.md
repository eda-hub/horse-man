# Testing and quality

## Manual contract
- `docs/manual/README.md` の現行releaseを取得できること
- 必須moduleの `manual_release` 不一致をfail closedできること
- module hash / manifest hashをPredictionへ固定保存できること
- Owner境界を跨ぐ実装マッピングを静的/単体テストで検出できること

## Production / Shadow分離
- Shadowは固定済Productionなしでは生成できない
- ShadowからProduction順位・確率・印・根拠を更新できない
- 同一 `baseline_forecast_id` で比較できる
- オッズ更新だけではProduction baseline IDを更新しない

## DB/Parser
- JV Record -> internal DTOのfixture test
- 欠損/異常値Validation
- duplicate ingest idempotency
- migration forward test

## Source provenance / source bias
`docs/jravan/11_source_provenance.md` の契約をテストする。

- JRA-VAN/JRAで取得可能な客観fieldが通常運用で `WEB_AGGREGATOR` の値だけに置換されないこと。
- 同一 `origin_group` に属する複数サイトの一致を「独立した複数証拠」としてカウントしないこと。
- `source_id`, `source_class`, `origin_group`, `first_observed_at/captured_at`, `acquisition_method` をcritical dataで追跡できること。
- derived featureから元raw provenanceへ遡れること。
- provider間で値が不一致の場合、多数決で上書きせずconflictを保持できること。
- 馬体重・オッズ等のWeb fallback利用時にfallbackであることが識別できること。
- netkeiba等の予想印、独自総合順位、AI予想、出所不明指数がProduction `rule_application.evidence_json` に入らないこと。
- 血統系統・インブリード・脚質等を外部サイト固有ラベルだけに依存せずraw dataから再計算できること。
- sourceを1つ停止したfixtureでも、authority順のfallbackが想定どおり動作すること。

回帰テストでは、サイト数の増加そのものを品質向上とみなさず、**Primary coverage / Web fallback率 / UNKNOWN_AGGREGATED率 / conflict件数**を別指標として確認する。

## 時点再現
固定レースfixtureで `data_cutoff` 後の馬体重、結果、actual final odds等が予想featureへ混入しないことをテストする。

特に相手レベルfeatureでは、過去対戦相手の「その後の成績」を使用する場合でもPrediction `data_cutoff` より後の結果が混入しないことを専用fixtureで検証する。開催傾向も当該Prediction時点までに終了・確定したレースだけを集計対象とする。

## Prediction regression
`docs/yosou/jra_racing/` の代表重賞をfixture元として、rule ID適用、主要feature、Production/Shadow生成過程が意図せず変わらないか確認する。予想結果そのものを永遠に固定するのではなく、manual release / engine version変更を明示する。

## Prediction evidence / marks
- Production順位と印が決定的に一致すること。
- 4位以下の勝利可能性が印昇格ではなく確率・レンジ・シナリオとして保持されること。
- 上位馬にfact/source/time/direction/strengthを持つ根拠が存在すること。
- 弱い単発情報だけで大幅順位変更しないこと。
- 根拠のobserved_atがdata_cutoff/発走時刻を越えないこと。

## Execution gate互換
- `v1.6.1 + prediction-compliance-v1` のfixtureが旧契約で継続PASSすること。
- `v1.7.0 + prediction-compliance-v2` はBetting情報なしでPrediction正式性を判定できること。
- release/schemaの未知・不正な組み合わせをfail closedすること。
- 次期release有効化後も旧gateを新schemaへ暗黙変換しないこと。
- REPLAYを前向きKPIへ昇格できないこと。

## Market validation
価格情報でProduction基準能力順位・確率・印が変わらないことをテストする。任意市場sidecarが未実行でもPrediction KPIが完了できることを確認する。

## Result / review preparation
的中、不的中、返還、同着、取消等をテストする。ProductionとShadowを混同せず、任意市場sidecarがPrediction結果結合の必須依存にならないことを確認する。

## Validation cycle
`docs/manual/50_review.md` のサイクル状態とDBのvalidation cycleを対応させる。サイクル終了後に過去Productionを書き換えない。

## Backup
Export -> fresh DuckDB import -> row count / key history / baseline ID / manual hash確認を自動化する。critical provenanceも復元対象に含める。

## AI
AI出力schema validation、無効proposal拒否、DB/ルール直接書込不可をテストする。AI応答内容そのものは厳密固定しない。

## バックテスト品質
- data cutoffを強制
- sample sizeを表示
- Predictionでは順位指標・確率校正・Brier Score等を確認し、任意市場sidecarでは回収率・分散・ドローダウン等を別系列で確認
- 複数候補から都合の良いものだけ選ぶselection biasを記録
- 同じ上流データを複数sourceとして扱うsource-count biasを防ぐ
- manualの正式検証KPIと統計研究用KPIを混同しない

## CI
Phase 0でPython lint/type/testを構築する。JV-Link実機依存テストは一般CIから分離し、Windows VM上のintegration testとして実行する。Web UI追加後はそのlint/type/testを追加する。
