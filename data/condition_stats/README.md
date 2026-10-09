# 血統別・条件別成績集計（次期Shadow準備）

正本計画: [PR68 血統調査・成績集計11節](../../docs/proposals/2026-10-09_pedigree_research_registry_implementation_plan.md)。実装: [scripts/pedigree_stats.py](../../scripts/pedigree_stats.py)。現在の運用は**確認済み血統・正式出走結果を整備する前段の集計ライブラリ**であり、現行manual・Production評価・実購入・推奨買い目には接続しない。

## まず何をするか

1. `python3 scripts/pedigree_stats.py --inventory` で過去の血統記述の未確認状態、元ファイル、出所commit、レコード状況を棚卸しする。旧候補を「確認済み」に自動昇格しない。
2. 対象期間・競馬場・芝/ダート等の条件・比較母数・血統軸・分類版・cutoff・`FORWARD`/`REPLAY`を**実行前に**`data/condition_stats/definitions/<ID>.json`へ定義する。
3. Phase 2等で別途取得・同定した対象レースの**全出走馬**と公式結果を`data/condition_stats/inputs/<ID>.json`へ保存する。馬名だけではなくRegistryの`horse_key`で参照。実際のプロバイダ照合はこの準備スクリプトの外で行い、未取得の出走表を仮の馬で埋めない。
4. `python3 scripts/pedigree_stats.py --run data/condition_stats/definitions/<ID>.json --input data/condition_stats/inputs/<ID>.json` で集計し、`completeness`・`missing`・`coverage`とsnapshotのパスを読む。
5. `python3 scripts/pedigree_stats.py --verify data/condition_stats/snapshots/<ID>/<SHA256>.json` / `python3 scripts/pedigree_stats.py --audit` でhash・入力原本を検証する。

前回snapshotの同定・血統依存revisionが時点適合している場合、
`python3 scripts/pedigree_stats.py --run data/condition_stats/definitions/<ID>.json --input data/condition_stats/inputs/<ID>.json --previous data/condition_stats/snapshots/<ID>/<旧SHA256>.json`
で変更されていない馬の分類を再利用し、訂正の影響範囲だけ再分類する。`--audit` は未実行の集計定義や未集計の最新版出走manifestも不足検出する。`--inventory` は既存未確認候補の数を表示するが、実データを確定した証明にはしない。

集計定義/入力の内容アドレス原本をそれぞれ`definitions/archive/`・`inputs/archive/`へ固定し、`condition_stat_snapshot`の**Git JSON準備形式**を`snapshots/`へ保存する。結果訂正・分類変更の新規snapshotは新しいSHA-256名となり、旧snapshotは上書きしない。外部情報の再取得なしに、保存済み入力から再集計可能。DBへの唯一Writer切替・差分ジョブはPhase 2/3の後続工程。

## 契約例（架空データ。公式取得済みとは扱わない）

以下は実データを装わない構造例。実行時にはファイルを用意する。

`data/condition_stats/definitions/example.json`

~~~json
{
  "schema_version": "pedigree-condition-stat-definition-v1",
  "definition_id": "example", "mode": "REPLAY",
  "period_start": "2026-01-01", "period_end": "2026-09-30",
  "data_cutoff": "2026-10-09T09:00:00+09:00",
  "result_rule": "official-finish-position-v1",
  "comparison": "NON_MATCH",
  "scope": {"venue": "TOK", "surface": "TURF", "distance_min": 1600, "distance_max": 2000},
  "groups": [
    {"group_id": "sire-example", "axis": "SIRE", "value": "verified-sire-id"},
    {"group_id": "damsire-example", "axis": "DAM_SIRE", "value": "verified-damsire-id"},
    {"group_id": "ancestor-example", "axis": "ANCESTOR", "value": "verified-ancestor-id", "depth": 5},
    {"group_id": "training-eu", "axis": "TRAINING_REGION", "subject": "SIRE", "value": "EU"}
  ],
  "training_classification": {
    "version": "example-v1", "source": "reviewed training-history classification",
    "first_observed_at": "2026-10-01T00:00:00+09:00",
    "regions": {"EU": ["FR", "GB"], "US": ["US"]}
  }
}
~~~

`data/condition_stats/inputs/example.json`

~~~json
{
  "schema_version": "official-runners-manifest-v1",
  "source_scope": "JRA TOK 2026-01-01..2026-09-30 filtered racing programme",
  "all_runners_included": false,
  "races": [{
    "race_id": "EXAMPLE-RACE", "race_date_jst": "2026-09-01",
    "venue": "TOK", "surface": "TURF", "distance_m": 1800,
    "class": "NEW", "going": "GOOD", "race_type": "DEBUT",
    "result_status": "OFFICIAL",
    "result_observed_at": "2026-09-02T10:00:00+09:00",
    "official_source": {
      "record_key": "example-source-race-key",
      "record_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    },
    "runners": [{
      "horse_key": "existing-verified-horse-key",
      "entry_observed_at": "2026-08-31T10:00:00+09:00",
      "status": "FINISHED", "finish_position": 1
    }]
  }]
}
~~~

上の入力例は**馬1頭だけの抜粋**なので`all_runners_included=false`。成績集計を完成として扱うには、レース条件に該当する全レースの全出走馬を出所付きで登録し、この宣言を真正に検証して`true`とする必要がある。`source_scope`は自己申告の範囲ラベルであり、スクリプトだけでJRA公式データの網羅性を保証できない。

## 集計と結果の規則

- 血統軸: `SIRE`（父）、`DAM_SIRE`（母父）、`SIRE_LINE`、`DAM_SIRE_LINE`（`taxonomy_version`と要求`depth`を指定）、`ANCESTOR`（`depth`を指定）、`CROSS`（`depth`と`min_paths >= 2`を指定）、`TRAINING_REGION`（対象`HORSE/SIRE/DAM_SIRE/ANCESTOR`を明示）。
- 調教地域は対象馬**自身**の確認済み`attribute:training_country`と指定した分類表から判断する。生産国・父系・親の属性を対象馬本人へ流用しない。複数地域・未指定国・競合は保留。地域定義は実データの調査・確認後に固定し、例示値を現実の分類へ流用しない。
- Race filter: `period_start/end`、`venue`、`surface`、`distance_min/max`、`class`、`going`、`race_type`。要求されたグループだけ算出する。出走IDは`race_id × horse_key`で重複排除。異なるレースの同じ馬は別出走。実頭数とレース数も保持。複数血統グループの重なりは合算しない。
- 公式`finish_position`は同着を同じ着順整数として受領する。確定`FINISHED`は1着=勝、2着以内=連対、3着以内=3着内。出走済みの`DNF`（中止）と`DQ`（失格）は分母に含め0勝。`SCRATCHED`（取消）/`EXCLUDED`（除外）は記録するが実出走分母から除外。`PENDING`または結果未確定は率の分母から外し不完全理由に残す。
- 各グループに`MATCH`、`NON_MATCH`、`UNKNOWN`、`CONFLICT`を別々に出力。欠測/未同定/祖先範囲不完全を非該当へ混入しない。`comparison=NON_MATCH`は同条件かつ判定済みの非該当群だけ比較し、`ALL`は全体の結果有効母数（血統不明を含む）を参照。
- 勝率/連対率/3着以内率は**確定した有効実出走数**が分母。分母0なら`null`。結果coverageと血統coverageを別に出す。小標本・同馬の反復出走・条件探索の差を適性の確定とは解釈しない。
- `FORWARD`: 結果・出走情報・確認済み血統revision・同定・分類（資料の初回観測だけでなく、実際の取得・検証時刻も照合）が`data_cutoff`時点で利用できた場合に限定。過去の結果を**予測対象レースの結果**として混入させない責任は呼出し側（Phase 3）が持つ。`REPLAY`: 後日確認・公式訂正を使用可能だが、両modeとも`production_eligible=false`・`usage=RESEARCH_SHADOW_ONLY`固定。重賞固有集計をProductionへ逆流しない。

**留保**: 公式提供元ごとの同着・降着・除外・失格に固有の規則は原出所仕様の確定を要する。現版は入力に記録した「公式確定着順」の整数による集計であり、未解決のproviderルールを推測補正しない。元入力が全レース・全馬を含むか、`official_source`が真正かは外部原票との突合が必要。

## 完了境界

`--audit`は保存済みsnapshotの改ざん等を確認するが、**snapshotが0件でも成功し得る**。これは実集計・出走データ収集・原出所確認の完了を意味しない。既存の過去記述535件は未確認の候補であり、統計用の出走母数ではない。Phase 2の公式出走/結果・実データID整備、Phase 3の実データ照合・DB連携、Phase 4表示、Phase 8検証/正式採用は独立した完了判定を維持する。

## 実データの主な調教国（2026-10-10 利用者指定）

`training_classification.country_selection=MOST_STARTS_BY_TRAINING_COUNTRY`を指定し、対象馬の競走馬としての各出走時の**調教所属国**を数え、最多出走国を採用する。開催国・遠征先・生産国・種牡馬供用国を代用しない。最多出走が同率の場合は利用者へ国名の指定を求め、指定を受けるまでUNKNOWNにする。

入力は唯一Writerで保存した`attribute:training_start_history`。値は`complete=true`、全出走母数`total_starts`、`starts`配列を持つ。各行に`race_id`、`race_date`、`training_country`（ISO二文字）、`source.url/record_hash/captured_at`を保存する。全出走一覧・各出走時の所属の照合前にcompleteを宣言しない。重複レース、母数不一致、所属国不明、出所欠落、cutoff後の出走・取得は分類を保留する。未照合の所属時点はその事実として報告する。

過去の固定snapshotの互換性のため、既存の`VERIFIED_COUNTRY`方式は維持する。今回確認した3祖先の単一調教エピソードは全出走履歴ではなく、新方式の入力に自動昇格しない。欧州に含める国の一覧も版付き定義に明記し、未指定国を欧州へ推定しない。
