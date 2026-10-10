# 血統別・条件別成績集計（次期Shadow準備）

正本計画: [PR68 血統調査・成績集計11節](../../docs/proposals/2026-10-09_pedigree_research_registry_implementation_plan.md)。実装: [scripts/pedigree_stats.py](../../scripts/pedigree_stats.py)。現在の運用は**Git JSONの集計ライブラリと、保存済み対象期間に限定した実データREPLAY研究**であり、現行manual・Production評価・実購入・推奨買い目には接続しない。

## 最新の実施範囲（2026-10-10）

確認基準はPR69 `aa3872eaddf7d2c0f8ccbdb71fafea1aee7b0e6c`からのR03〜R06原文照合・Writer保存。[実データsummary](../pedigree/reconciliations/2026-10-10-alternative/scope_summary.json)から固定定義・入力・snapshotを辿れる。

- 2026-08-16〜2026-10-04のJRA159レース・2,182登録行・2,177実出走・2,089頭を保存・照合。父キズナと母父ディープインパクトの2条件の固定REPLAY集計はCOMPLETE、血統UNKNOWN/CONFLICTは0。
- 調教国の資料確認30頭について、30頭すべて原資料照合・Registry登録済み。R03〜R06は新規5頭・既存15頭の冪等確認。全体の未検索数は旧説明583と全件台帳521が不一致で再照合待ち。調教地域・他系統・海外を含む全条件の集計完了とはしない。
- 初期のPARTIAL入力・snapshotと、旧調教国方式の固定結果は履歴として保持。今回の新規調教国調査で過去の集計値を上書きしない。
- DB/取得adapter・非UIアプリ接続・FORWARD運用と効果評価は未実施。WebUIは実施対象外。現在の受入範囲は[受入表](acceptance.md)を参照。

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
- 調教地域は対象馬**自身**の確認済み調教所属情報と指定した地域分類表から判断する。新方式は`attribute:training_country_matches`（検索不一致の場合のみ`attribute:training_country_user`）、旧方式は既存の`attribute:training_country`を参照する。生産国・父系・親の属性を対象馬本人へ流用しない。判定不能・未指定国・競合は保留。地域定義は確認後に固定し、例示値を現実の分類へ流用しない。
- Race filter: `period_start/end`、`venue`、`surface`、`distance_min/max`、`class`、`going`、`race_type`。要求されたグループだけ算出する。出走IDは`race_id × horse_key`で重複排除。異なるレースの同じ馬は別出走。実頭数とレース数も保持。複数血統グループの重なりは合算しない。
- 公式`finish_position`は同着を同じ着順整数として受領する。確定`FINISHED`は1着=勝、2着以内=連対、3着以内=3着内。出走済みの`DNF`（中止）と`DQ`（失格）は分母に含め0勝。`SCRATCHED`（取消）/`EXCLUDED`（除外）は記録するが実出走分母から除外。`PENDING`または結果未確定は率の分母から外し不完全理由に残す。
- 各グループに`MATCH`、`NON_MATCH`、`UNKNOWN`、`CONFLICT`を別々に出力。欠測/未同定/祖先範囲不完全を非該当へ混入しない。`comparison=NON_MATCH`は同条件かつ判定済みの非該当群だけ比較し、`ALL`は全体の結果有効母数（血統不明を含む）を参照。
- 勝率/連対率/3着以内率は**確定した有効実出走数**が分母。分母0なら`null`。結果coverageと血統coverageを別に出す。小標本・同馬の反復出走・条件探索の差を適性の確定とは解釈しない。
- `FORWARD`: 結果・出走情報・確認済み血統revision・同定・分類（資料の初回観測だけでなく、実際の取得・検証時刻も照合）が`data_cutoff`時点で利用できた場合に限定。過去の結果を**予測対象レースの結果**として混入させない責任は呼出し側（Phase 3）が持つ。`REPLAY`: 後日確認・公式訂正を使用可能だが、両modeとも`production_eligible=false`・`usage=RESEARCH_SHADOW_ONLY`固定。重賞固有集計をProductionへ逆流しない。

**留保**: 公式提供元ごとの同着・降着・除外・失格に固有の規則は原出所仕様の確定を要する。現版は入力に記録した「公式確定着順」の整数による集計であり、未解決のproviderルールを推測補正しない。元入力が全レース・全馬を含むか、`official_source`が真正かは外部原票との突合が必要。

## 完了境界

`--audit`は保存済みsnapshotの改ざん等を確認するが、**snapshotが0件でも成功し得る**。これは実集計・出走データ収集・原出所確認の完了を意味しない。既存の過去記述535件は未確認の候補であり、統計用の出走母数ではない。対象期間のJRA公式入力・ID照合と限定2条件のGit実集計は実施済み。対象外データの整備、Phase 2のDB/取得連携、Phase 3の非UIアプリ接続、Phase 8の検証/正式採用は独立した未完了項目として維持する。WebUIは実施対象外。

## 調教国の確定優先順位（2026-10-10 改訂）

新しく確認する父・母父・指定祖先（必要時は本人）の国・地域判定には
`training_classification.country_selection=SEARCH_MATCH_PRIORITY_V1`を指定する。
調査と記録は既存のGit台帳で行い、WebUI/DB/自動source adapterは今回実装しない。

1. **検索結果に一致した調教国が1カ国**：その国で確定し後続の国調査は不要。同じ国の複数資料も1国として扱う。
2. **複数国が一致**：実際の調教所属時点が最も新しい国を確定する。出走回数が最多の国ではない。最終所属日の証拠がない、または異なる国で同日となる場合は推測せず保留。
3. **調教国が一致しない**：`TRAINING_COUNTRY_USER_INPUT_REQUIRED`を返し、他の調査は継続。タスク終了後に対象馬名・識別情報・父/母父/祖先の別・不足内容を**まとめてチャットでユーザーに提示**する。回答を受けたら元の回答・受領時刻・出所を記録し、ユーザー提供の国としてセットする。未回答なら未確認のまま。

既存の予想・集計で利用する対象馬のみに調査範囲を限定する。全5代祖先の生涯調教履歴は今回の必須条件ではない。
生産国、開催国、遠征先、種牡馬供用国、父系名称などを国の代用品にしない。
地域分類に使用する国→地域対応は版付き定義で固定し、米国型を北米全体へ拡張しない。
後日取得した結果は過去のFORWARD時点へ遡及流用せず、REPLAYを区別する。

### Git台帳の保存形式

検索結果は対象馬自身の`attribute:training_country_matches`に以下の形式で保存する。
`search_completed=true`は必要な検索を実施したことを示し、全生涯調教履歴の網羅宣言ではない。
同一馬の親・子孫には自動転用しない。

~~~json
{
  "schema_version": "training-country-matches-v1",
  "search_completed": true,
  "matches": [
    {
      "country": "US",
      "last_trained_on": "2020-06-01",
      "source": {
        "url": "https://example.org/source",
        "record_hash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        "captured_at": "2026-10-10T10:00:00+09:00"
      }
    }
  ]
}
~~~

これは**架空の構造例**であり、実際の馬の検証済み事実として登録してはならない。
`matches=[]`は実際に検索して一致がなかった場合だけ保存する。未検索と区別する。
各候補には出所と確認時刻を付け、複数国の場合は`last_trained_on`で直近を特定する。
出所不明・同定不明・日付不明・cutoff後取得・同率最終日はUNKNOWN/CONFLICTとして残す。

検索不一致後のチャット回答だけは、専用の`attribute:training_country_user`に
`source_class=USER_PROVIDED`、`acquisition_method=user-chat`で保存できる。
回答の原文を出所キーで一意に識別し、原文SHA-256を`source.record_hash`へ設定し、
返信受領時刻を`first_observed_at`と`captured_at`へ残す。本人同定を確認し
`verification`に確認者を記録してから唯一Writerの`save`を使う。
ユーザー提供値は独立した外部原票と混同せず、提供元を必ず表示する。
この値は検索不一致の場合だけ参照され、一致した検索結果を上書きしない。
ユーザーが未回答・不明回答の場合は、値を捏造したり通常の`training_country`属性を代用しない。

### 過去の固定結果との互換性

旧`VERIFIED_COUNTRY`および`MOST_STARTS_BY_TRAINING_COUNTRY`は、
既に作成したdefinition/snapshotの読戻し・監査のために**互換モードとしてのみ保持**する。
新規の調教国選択に最多出走国を使用しない。既存の履歴やREPLAY snapshotは
新方式の結果に書き換えず、独立した定義・新しいsnapshotを作る。


## 手順4の追加受入（2026-10-10）

[対象確定結果](../pedigree/reconciliations/2026-10-10-training-priority/designated-ancestor-target-review.json)で28表記を21個体へ対応付け。父/母父613個体との重複8、追加13、合計626個体。旧候補・同定済みRegistryを保持し、個体ID・生年・役割・代表親子経路を5表記ごとの6区切りで固定した。

本人の既存単一国属性4件を固定時点で再利用し、国未調査17件は父/母父キュー共通5と追加祖先12へ分けた。新規検索・国事実・別名・条件定義・集計snapshotの追加は0。未検索を検索ゼロ・ユーザー回答待ちにしない。系統分類、5代内包、母父本人、本人の調教国を独立して扱う。Nasrullahの子孫条件、Danehill Dancerの部分一致、曖昧な枝・代数・旧傾向の優位性は自動昇格しない。

`check_designated_ancestor_scope.py`で原文hash・28表記・21ID・親子関係・cutoff・既存国属性・重複排除を確認、7件の拒否回帰を追加。全613頭の登録/検索状態の再照合、17頭の国調査、全馬該否と追加条件集計は後続。WebUIは実施対象外、REPLAY専用・Draftを維持する。


## 手順5の最初の実施単位（完了、全体は継続）

613頭の実レコードを元commitと照合し、開始時点は登録92頭・未検索521頭。資料確認のみ5頭の状態欠落と旧583頭の誤記を訂正。利用頻度順の先頭10頭を既存CAS Writerで登録し、現在は登録102頭・未検索511頭。旧revision・開始cutoff・再保存追加0件を確認した。

詳細と次の10頭は `data/pedigree/reconciliations/2026-10-10-training-priority/README.md` の最新節、固定証跡は `s5-inventory-checkpoint.json` と `s5-batches/batch-01/verification.json` を参照。フレンチデピュティは原PDFの直接取得403のためprovider原文照合後の抽出項目証跡であり、原PDF byte保存を主張しない。その他は取得本文とbyte hashを保存。

`python3 scripts/check_training_country_priority.py --repo .` と8回帰テストで元blob・件数・優先順・個体・所属国/日付・原資料hash・旧履歴・時点・残りキューを照合。CIへ追加。残り511頭と後続工程は未完了。WebUIは実施対象外、現行v1.6.1・Production・旧snapshotは維持。

## 手順5：父・母父の優先調査を全件実施（2026-10-10）

開始時点613頭（登録92・未検索521）のうち、先頭10頭に続く511頭を52個の10頭単位チェックポイント（最後1頭）で原票照合した。新たな唯一Writer追記511件、国確定416頭、資料範囲内の検索一致ゼロ79頭、複数国の実際の最終所属日不足16頭、取得不能・未検索0頭。父・母父全体の現在値は国登録518頭・確認待ち95頭。旧revision・独立ID・同定・開始cutoffを保持し、再保存追加0件。

HTTP原票を圧縮保存し、本人ID・名前・生年・本人調教師欄／明示Trained列／明示調教所属分類を照合した。公式IFHA年次版を追加し、従来保存資料の年途中版と年度ラベル違いを記録した。出生・出走開催・種牡馬供用国や年度を最新所属の根拠にしない。国確定にはSEARCH_MATCH_PRIORITY_V1を使用し、全生涯の全移籍を網羅したとの主張はしない。

再開位置・件数は `data/pedigree/reconciliations/2026-10-10-training-priority/s5-remaining/progress.json`、不足情報は同ディレクトリの `needs-information.md`。手順5の原票調査と保存は完了したが、95頭の国確定は回答・所属日の資料待ち。追加祖先12頭の手順6、海外42行、旧482記述、過去証跡40件、JSON Schema追随・全条件再集計は別工程として残る。WebUIは実施対象外。Draft PR69・現行v1.6.1・Production・旧固定snapshotは維持する。

## 2026-10-10 利用者の末尾国指定

確認待ち95頭中84頭を利用者の明示指定によるUSER_PROVIDED属性へ追記。元の外部検索結果・国・履歴は保持し、原票で確認された国とは区別する。検索一致ゼロと、日付不足/同率により保留された複数国に限り、明示指定USER_CONFIRMED_NAME_SUFFIX_V1を集計参照へ反映する。単一国や確認済み最新国は上書きせず、指定受領前のcutoffや旧snapshotには逆流させない。国表記のない11頭はUNKNOWN。現時点の参照可能数602（外部518＋利用者指定84）。再集計やProduction昇格の完了を意味しない。

## 2026-10-10 本人名・調教国の明示回答11頭

残った11頭へ利用者の原文・受領時刻付き明示回答をUSER_EXPLICIT_COUNTRY_V1で追記。外部国登録518＋末尾指定84＋本人名回答11＝父/母父613頭、確認待ち0。複数国の日付不足も明示回答を参照し、外部検索結果/旧revision/過去cutoffは保持。s5-remaining/user-country-confirmations/explicit-country-reply.jsonを正とする。追加指定祖先12頭は別工程。従来調査はIFHA/血統DBに偏った限定検索であり、統括団体・殿堂・本人の調教師/馬主等の経歴資料を含む検索へ是正する。全条件再集計/正式昇格の完了を意味しない。


## 指定祖先の追加調査（2026-10-10、手順5）

追加指定祖先12頭を本人名・独立ID・生年で照合。本人調教師の所属国原票等で11頭を登録し、ノーザンダンサー1頭は加国/米国の所属最終日比較を保留。検索語・取得失敗を含む参照先・原文応答hash・10頭＋2頭のCAS追記/readback・旧cutoff不変をs6-designated-ancestorsへ保存。父/母父613頭の確認待ち0とは別枠。殿堂/牧場/競馬報道も取得し、本人の所属国明示がない資料を国証拠にしない。全条件の再集計とProduction昇格は未実施。


## 海外4レースの先頭5登録行（手順6、2026-10-10）

本人同定・公式父母母父・5代310位置をRegistryへ保存/readback。36独立個体・58親子revisionを追加。42登録行＝38出走＋4取消は不変、残37行は未照合。原文・対応表・CAS receipt・固定cutoffはdata/pedigree/reconciliations/2026-10-10-foreign-reviewに保存。全海外coverageと全条件再集計は未完了。
