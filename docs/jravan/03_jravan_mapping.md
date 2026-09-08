# JV-Data mapping plan

現行JV-Data仕様をParserで内部DTOへ変換し、DBへ保存する。Record構造をPrediction Engineへ直接露出しない。

| DataSpec/Record | 内部格納 | 主用途 |
|---|---|---|
| RACE / RA | `core.race` | レース詳細 |
| RACE / SE | `core.runner`, `core.runner_result` | 出走馬・結果 |
| RACE / HR | payout系 | 払戻 |
| RACE / O1-O6 | `market.odds_snapshot` | 確定オッズ |
| DIFN / UM | `core.horse` | 競走馬マスタ |
| DIFN / KS | jockey master | 騎手 |
| DIFN / CH | trainer master | 調教師 |
| DIFN / BR | breeder master | 生産者 |
| DIFN / BN | owner master | 馬主 |
| BLDN / HN,SK,BT | `core.pedigree` | 血統・系統 |
| SLOP / HC | workout | 坂路調教 |
| WOOD / WC | workout | ウッド調教 |
| COMM / CS | course master | コース |
| YSCH / YS | schedule | 開催日程 |
| 速報 WH | `market.weight_snapshot` | 馬体重 |
| 速報 WE等 | condition/event | 天候・馬場・変更 |
| 速報 O1-O6 | `market.odds_snapshot` | 速報オッズ |
| 速報 RA/SE/HR | result/payout | 結果・払戻 |

## Ingest原則
1. JV-Link呼出は専用Adapterからのみ。
2. 受信RecordはParser -> Pydantic validation -> internal DTO -> writer の順。
3. ingestはidempotentにする。同一データ再取得で二重登録しない。
4. `ops.data_watermark` へ最終成功地点を保存する。
5. 速報データは再取得期限を考慮し、予想対象/重要snapshotを優先保存する。
6. 取消・変更は過去値を消さずevent化する。

## Phase 1最小対象
RA、SE、UM、結果/払戻に必要な最小Recordから始める。血統、調教、オッズ等はPhase 2へ分離する。
