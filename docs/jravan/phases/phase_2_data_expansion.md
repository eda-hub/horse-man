# Phase 2 — Data expansion

## 目的
予想に必要なデータ領域を拡張する。

## 対象
- 5代血統/系統
- 騎手/調教師/馬主/生産者snapshot
- 調教
- コース/開催
- 馬体重
- 天候/馬場
- 取消/変更event
- 確定オッズ
- 速報オッズの最小取得
- FINAL用data freshness / readiness
- source registry / data provenance

## 受入条件
- 予想対象レースの主要データが1つのrace_idで結合できる。
- 過去名称snapshotが保持される。
- 取消/変更前の値が消えない。
- 5代血統から指定系統内包を検索できる。
- storage使用量をsystem statusで確認できる。
- `docs/jravan/11_source_provenance.md` に従い、critical dataで `source_class`, `origin_group`, acquisition method, observed/captured時刻を追跡できる。
- 同じ上流データを転載する複数Webサイトを独立証拠として数えない。
- 血統系統・インブリード等のderived featureをraw pedigreeから内部再計算でき、元provenanceへ遡れる。
- Web aggregatorの予想印・独自総合指数・AI予想をProduction基準能力featureへ混入させない。
- JRA-VAN/JRA一次データとWeb fallbackの不一致を上書き多数決せずconflictとして保持できる。
- `JVWatchEvent` の `JVEvtWeight` を受信し、返却keyから `JVRTOpen(0B11, key)` を実行して当日馬体重・増減を保存できる。
- Eventを取り逃した状態、またはCore Service再起動後でも、`0B11` のrace-key / day-key catch-upで既発表の馬体重を復旧できる。
- 馬体重snapshotに `first_observed_at`, `captured_at`, nullableなprovider timestamp, source, acquisition methodを保存できる。
- T-20では新規取得時刻ではなく、現在の出走対象馬に対する当日WHのcoverageをrace単位で再検証できる。
- T-20より前に取得済みの完全な当日公式WHを、取得時刻だけを理由にSTALE扱いしない。
- 馬体重readinessを `PENDING / READY / PARTIAL / MISSING / STALE / SOURCE_ERROR` で区別できる。
- 取消・競走除外をcoverage母数から正しく除外できる。
- 通常時の約1時間前発表だけをハードコードせず、夏季等の発表タイミング差でもEvent監視とT-75〜T-20のfallback pollingで取得できる。
- 外部GUIまたはJRA一次情報に値が表示されている、あるいは `JVEvtWeight` 受信済みなのにAdapter/Parserで取得できないケースを `SOURCE_ERROR` として検知できる。
- JRA-VAN公式動作確認ツールで同一 `0B11` が取得できる場合、provider未発表ではなく内部Adapter/Parser側障害として切り分けられる。
- 前走馬体重や静的HTMLの空欄を当日馬体重として代用しない。
