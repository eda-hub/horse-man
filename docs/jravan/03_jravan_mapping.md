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
| 速報 WH / 0B11 | `market.weight_snapshot` | 当日馬体重 |
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
7. 当日馬体重は「T-20で初めて取りに行くデータ」と扱わない。JV-Dataでは通常レース発走約1時間前から速報馬体重 `0B11` が提供されるため、開催日は `JVWatchEvent` を開始し、`JVEvtWeight` 受信時に返却keyを `JVRTOpen("0B11", key)` へ渡して即時取得する。
8. Eventを取り逃した場合、Core Service再起動時、またはEvent通知が利用できない場合に備え、`0B11` のレース単位取得を優先したcatch-up / pollingを持つ。必要に応じて開催日単位取得でも補完する。発表時刻を固定値と仮定せず、通常時・夏季等の運用差をEvent + 広めのfallback windowで吸収する。
9. FINAL対象レースでは、T-20は**取得開始時刻ではなく検証時刻**とする。T-20より前に取得済みの当日公式WHが現出走馬について完全なら、そのsnapshotをFINALで再利用してよい。T-20以降に新しい馬体重snapshotを作ること自体をREADY条件にしない。
10. `market.weight_snapshot` は少なくとも `race_id`, `horse_id`, `body_weight`, `body_weight_diff`, `first_observed_at`, `captured_at`, `provider_timestamp(nullable)`, `source`, `acquisition_method(EVENT/POLL/CATCH_UP/FALLBACK)`, `record_hash` を保持する。provider側時刻が空・0等でも取得可否を判定できるよう、システム側の観測時刻を必須とする。
11. 前走馬体重、検索index、静的HTMLの空欄を当日馬体重として代用しない。
12. 馬体重・馬場・変更eventごとに freshness / coverage / missing reason / last_attempt_at を保存し、取得元障害と未発表を分離できるようにする。

## 馬体重取得フロー
```text
service start / race-day start
 -> JVWatchEvent開始
 -> JVEvtWeight受信
 -> JVRTOpen(0B11, event key)
 -> WH parse / validation
 -> active runnersとのcoverage照合
 -> market.weight_snapshotへ保存

Event未受信・再起動・欠損時
 -> 0B11 race-key catch-up
 -> 必要ならday-key catch-up
 -> 完全取得まで低頻度polling
 -> T-20でtargeted verification
```

pollingは全レースを常時高頻度で回さない。予想対象レースについて概ねT-75からT-20までの範囲で未取得時だけ再試行し、完全取得後は停止する。具体的なcadenceは `10_operations.md` をOwnerとする。

## FINAL用馬体重データ品質
馬体重は「何分前に取得したか」だけで鮮度判定しない。同一レースの当日公式値は、発表後に取得した時刻がT-20より前でも、現出走馬との整合が取れていればFINALで有効とする。

- `PENDING`: 発表前と判断でき、当日WHがまだ無い。FINAL確定前の正常待機状態。
- `READY`: 現在の出走対象馬すべてについて当日公式WH・増減を取得済み。取得時刻がT-20より前でもよい。
- `PARTIAL`: 当日WHは取得できたが、現出走対象馬の一部が欠ける。
- `MISSING`: 発表想定windowまたはT-20検証を過ぎても当日WHを取得できず、取得元障害とも断定できない。
- `STALE`: 前日・別レース・旧出走構成など、現在レースへ適用できないsnapshotしかない。単に「T-20より前に取得した」という理由ではSTALEにしない。
- `SOURCE_ERROR`: `JVEvtWeight`受信済み、JRA-VAN検証ツールで取得可能、JRA公式一次情報に表示済み等、公開済みと判断できるのにAdapter/Parser/通信で取得できない。

coverage判定では取消・競走除外済みの馬を必須母数から除外し、現在の `core.runner.entry_status` とWHを照合する。`PARTIAL / MISSING / SOURCE_ERROR / STALE` のままFINALへ進む場合は `data_readiness=DEGRADED` とし、欠損馬番・最終成功時刻・最終試行時刻・取得method・errorを保存する。

ブラウザGUIと静的HTMLで表示差がある外部サイトは一次取得経路にしない。補助Webソースは、JRA-VAN/JRA一次データとの不一致検知や障害調査にのみ使う。

## Phase 1最小対象
RA、SE、UM、結果/払戻に必要な最小Recordから始める。血統、調教、オッズ等はPhase 2へ分離する。
