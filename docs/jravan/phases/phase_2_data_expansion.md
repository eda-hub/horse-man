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

## 受入条件
- 予想対象レースの主要データが1つのrace_idで結合できる。
- 過去名称snapshotが保持される。
- 取消/変更前の値が消えない。
- 5代血統から指定系統内包を検索できる。
- storage使用量をsystem statusで確認できる。
- 速報WHから当日馬体重・増減・source timestampを保存できる。
- 発走20分前以降の馬体重snapshotが取得できたかをrace単位で判定できる。
- 馬体重、馬場、取消/変更eventの欠損を `READY / STALE / MISSING / SOURCE_ERROR` で区別できる。
- 外部GUIに値が表示されているのにAdapter/Parserで取得できないケースを `SOURCE_ERROR` として検知できる。
- 前走馬体重や静的HTMLの空欄を当日馬体重として代用しない。
