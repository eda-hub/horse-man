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
- JRA-VAN/JRA一次データとfallbackの不一致を上書き多数決せずconflictとして保持できる。
- `JVWatchEvent` の `JVEvtWeight` を受信し、返却keyから `JVRTOpen(0B11, key)` を実行して当日馬体重・増減を保存できる。
- Eventを取り逃した状態、またはCore Service再起動後でも、`0B11` のrace-key / day-key catch-upで既発表の馬体重を復旧できる。
- 馬体重snapshotに `first_observed_at`, `captured_at`, nullableなprovider timestamp, source, acquisition methodを保存できる。
- T-20では新規取得時刻ではなく、現在の出走対象馬に対する当日WHのcoverageをrace単位で再検証できる。
- T-20より前に取得済みの完全な当日公式WHを、取得時刻だけを理由にSTALE扱いしない。
- 馬体重readinessを `PENDING / READY / PARTIAL / MISSING / STALE / SOURCE_ERROR` で区別できる。
- 取消・競走除外をcoverage母数から正しく除外できる。
- 馬体重のfallback polling cadence・停止条件・障害切り分けは `docs/jravan/10_operations.md` を唯一のOwnerとして実装し、本Phaseに時刻列を重複定義しない。
- `JVEvtWeight` 受信済み、JRA-VAN公式動作確認で取得可能、またはJRA公式一次情報で公開済みと確認できるのに内部Adapter/Parserで取得できないケースを `SOURCE_ERROR` として検知できる。
- JRA-VAN公式動作確認ツールで同一 `0B11` が取得できる場合、provider未発表ではなく内部Adapter/Parser側障害として切り分けられる。
- 前走馬体重や静的HTMLの空欄を当日馬体重として代用しない。

## 血統Git基盤のDB移行契約

PR68の追加計画に基づくPR69の `data/pedigree/` を入力契約とする。Git基盤はPhase順を飛ばすランタイムではなく、手動調査を再利用する独立データ基盤。

- core.horseの外部ID・ローカルID・別名・同定根拠を保持し、同名異馬を統合しない。
- core.pedigreeへrevision、前revision、訂正理由、親子path/世代、provenance参照、観測・取得・保存確認時刻を接続する。
- 調査要求・不足・失敗・再試行期限はops、系統・内包等の派生情報はfeatureへ置く。
- JSON→DB移行前後でID・revision・hash・時刻・出所・cutoff時点の検索結果を照合する。既存JSON読取adapterを用意する。
- DBを唯一のWriterへ切り替える際、`data/pedigree/writer.json` をJSON以外へ変更し、旧スクリプトの直接更新を停止する。JSONは読取用exportだけとする。
- 取得可能世代・ID・訂正通知・調教国・source利用条件を実接続で確認する。生産国を調教国へ代用しない。
- Gitの未確認移行候補をVERIFIEDとして取り込まず、原出所を再照合する。

具体DDL・JRA-VAN/Web adapter・実移行はPhase 2の実装PRで確定する。PR69の現在の完成範囲はGit JSONの検索・検証・保存・過去候補抽出であり、本節の実DB受入完了を意味しない。


## 血統成績集計の公式出走母数（PR68 §11）

PR69で`scripts/pedigree_stats.py`と版付き`official-runners-manifest-v1`入力契約、Git固定集計snapshotを準備した。Phase 2の実データ引継ぎでは、レースID×馬IDの全出走馬・公式着順/結果状態・訂正revision・出走時点・公式出所hashを確保し、既存の確認済み血統IDと一致させる。勝ち馬だけの抽出や不明馬の推測補完を禁止する。保存JSONの`all_runners_included`はプロバイダ原票と突合し、未確認ならfalseにする。現時点では実在のJRA-VAN/JRAアダプタ・DB移行・公式原票との突合は未実装。後続実装で必要な接続とDB Writer切替はこのPhaseの受入条件として残す。詳細は[入力契約](../../../data/condition_stats/README.md)。
