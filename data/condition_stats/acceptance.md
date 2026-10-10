# R08の受入再照合（2026-10-11）

国内159レース・2,182登録行・2,177実出走について、選定39条件（指定祖先21、父直系6、母父直系6、クロス6）を6期間の固定集計へ保存。全期間COMPLETE、血統UNKNOWN/CONFLICTは0。取消1・除外4・中止6、同着を含む整数着順の計数を原結果と照合した。既存4snapshotとその定義は保持する。

海外4レース42登録行・4取消について、公式結果確認済み3レース30実出走を成績分母とする43条件の集計を保存。York8頭はBHA公式原票未取得につきPENDINGとし分母に入れない。追加調教国20頭中17頭を確認した前回記録を保存し、今回Commissioner（2011）のIFHA公式原票Trained列USAを照合して18頭確認・残2頭へ更新した。Sakhee（1997、GB/AE）とStarspangledbanner（2006、AU/IE）は最新所属日が未確定。国欠測はUNKNOWNへ分離し、新時点の海外2snapshotの欠測は延べ6から4へ減少した。BHA API再取得は403、応答hashと停止状態を保存。

新規snapshotは前回作成8＋今回更新2の10件。全14snapshotを再計算監査する。すべてREPLAY研究用・Production採用前。正式なSHADOW前向き評価や全未選定条件の完了を主張しない。

現在の証跡・残件は [R08受入記録](../pedigree/reconciliations/2026-10-11-r08-acceptance/README.md) と同ディレクトリのprogress.json。以下は各実施時点の履歴。

# 最新の受入再照合（2026-10-10）

JRA159レース・2,182登録行・2,177実出走に対する父/母父EU・USと指定祖先21条件、計25条件をREPLAYで保存/readback。結果はCOMPLETE。欧州対象国は利用者指定の英・愛・仏・独・伊。 固定入力の取消1・除外4・中止6と母数を保持し、未確認・競合は独立群に残す。新snapshotは `data/condition_stats/snapshots/prediction-period-jra-training-regions-20261010/c37467eef8f237e25f504cbd725c90158e1c65e468c66a7cf283fab393b86e9c.json`。外部所属とUSER_PROVIDEDを理由・revision・hashで追跡できる。

父/母父613頭と追加指定祖先12頭の未確定は0。旧535候補は昇格せず、残482記述の分類と原文hash照合は別記録。海外42行の5代登録は完了したが、YorkのBHA結果原票と海外集計は未完了。Stage切替・DB/アプリ・前向き評価・Production採用は独立した後続工程。WebUIは対象外。

[対象集合・出所・残件の再照合manifest](../pedigree/reconciliations/2026-10-10-training-priority/acceptance-recheck.json)を現在の状態とする。以下は各実施時点の受入履歴。

# PR68 §11.7 血統確認・成績集計の受入対応

確認基準: PR69 `aa3872eaddf7d2c0f8ccbdb71fafea1aee7b0e6c`からのR03〜R06原文照合・Writer保存。実データの正本は[範囲summary](../pedigree/reconciliations/2026-10-10-alternative/scope_summary.json)と同summaryから参照する固定snapshot。調教国は[最新実施記録](../pedigree/reconciliations/2026-10-10-training-priority/README.md)を参照。

**区別する完了段階**: 過去候補の整理・Git血統調査基盤・合成fixtureによる集計処理の検証は、実データの原出所確認/公式全出走母数の取得/正式統計採用とは異なる。PR69の既存manualとPrediction KPIは変更しない。

| §11.7 | 要件 | PR69の実装・検証 | 状態 |
|---|---|---|---|
| 1 | 血統候補の状態・出所・未確認件数 | `pedigree_stats.py --inventory`：既存migrationの元ファイル・commit・成分分類・未確認数、現行Registryの同定・事実確認数を出力。未確認を自動昇格させない | 棚卸し実装済み。旧53記述の父・母父106成分は原票照合済み、残る482記述は保留 |
| 2 | 全出走母数・勝/連対/3着数と率 | 結果確定済み全出走からrace×horseを計数。`test_01`の同着例で分母・率を検証 | 合成入力とJRA159レースの父キズナ・母父ディープインパクト限定REPLAYで完了 |
| 3 | 入力重複・同馬別レース・共通祖先重複 | 重複行は同一内容のみ除去、矛盾重複拒否、出走IDで計数。`test_02/03/13/15` | 合成入力で検証済み。限定JRA実データは原票・集計監査でも検証済み |
| 4 | UNKNOWN/CONFLICTを非該当に混ぜない | MATCH/NON_MATCH/UNKNOWN/CONFLICTと理由別不足/coverage。`test_04` | 合成入力で欠測分離を検証済み。限定2条件の実データはUNKNOWN/CONFLICT=0 |
| 5 | 米国型/欧州型と調教履歴確認・ユーザー照会 | 対象HORSE/SIRE/DAM_SIRE/ANCESTORの本人の確認済み調教国だけ使用。`test_05/06/18/20`。未確認・多地域の理由を表示 | 判定・ユーザー回答原文/hash/受領時刻の保存は実装・回帰検証済み。資料確認済み30頭はすべて原資料照合・Registry登録済み。R03〜R06は新規5頭・既存15頭の冪等確認。全体の未検索数は旧説明583と全件台帳521が不一致で再照合待ち。実際の照会/回答取得は別工程 |
| 6 | 同着・取消・中止・失格・未確定・訂正・分母0 | 版付き整数着順ルールを明示し`test_01/09/11/12`で確認 | テスト実装済。provider固有の降着/除外規則の正式対応は未確定 |
| 7 | cutoffとFORWARD/REPLAY | 結果観測/出走観測/Registry同定・血統・分類時点を検査。`test_07/08/16/21/24`。後日取得のバックデート事実もcutoffではUNKNOWNとする。全出力は研究Shadow限定 | テスト実装済。実運用FORWARD接続は未実装 |
| 8 | 同一入力冪等・旧snapshot保持 | input/definition原本archive・digest識別・原子保存・読戻し・改変監査。`test_09/14/21` | テスト実装済 |
| 9 | 差分再計算・不要な外部再取得禁止 | `--previous`で前snapshotの登録済みrevision依存hashが同じ馬の派生を再利用。`test_19/20`。外部API照会なし | Git JSON機構実装済。DB/大規模ジョブ連携は後続 |
| 10 | 保存失敗・不足・再開 | 原子保存・入力archive・読戻し、partial+missing/coverage、verify/audit。実行前定義だけ存在する場合・公式結果manifestが更新され未集計の場合も不足検出（`test_23`）。Snapshot 0件でも集計完了と誤認しない | Git JSON準備実装。実DB障害/再開ジョブは後続 |
| 11 | 公式実データ母数の照合 | 全出走宣言と出所hash必須。スコープ未完了はPARTIAL | 対象期間のJRA159レース・2,182登録行・2,177実出走の照合済み。公式入力と原票対応を保存。海外・他期間・JRA-VANランタイムの取得連携は未完了 |
| 12 | 重賞固有Shadow隔離・Prediction非干渉 | `production_eligible=false` と `usage=RESEARCH_SHADOW_ONLY` 固定。既存manual/checker/既存記録を不変更 | 構造上隔離。Phase 8での性能評価・Production昇格は未実装 |

## 最新の段階判定（2026-10-10）

- **候補整理・血統確認**: JRA対象2,089頭を照合。旧535記述のうち53記述に対応する父・母父106成分は公式原票確認済み、その他482記述は保留。候補の自動昇格は行わない。
- **集計処理**: Git JSONの計算・固定snapshot・監査・差分再計算を実装し、合成fixtureと選定済み実データで検証。DB/アプリ連携は未実施。
- **実データ照合**: 2026-08-16〜2026-10-04のJRA159レース・2,182登録行・2,177実出走・2,089頭について、父キズナ・母父ディープインパクトの固定集計がCOMPLETE。両条件の血統UNKNOWN/CONFLICTは0。父キズナは72登録・71実出走、母父ディープインパクトは156登録・156実出走。取消1・除外4・中止6を区別。全期間・全血統条件の完成を意味しない。
- **調教地域集計**: 調教国選択・回答保存の機能は実装済み。指定祖先は28表記・21個体の役割と代表経路を確認済み。父・母父613頭の国調査と新方式の地域集計は未完了。全体の未検索件数は台帳間不一致の再照合待ち。古い最多出走国方式のsnapshotは履歴として保持し、新方式の集計と混同しない。
- **WebUI**: 利用者指定で実施対象外。画面表示の未実装を残件・完了条件に含めない。
- **予想採用**: 実データ集計はREPLAY研究専用。FORWARDアプリ接続・前向き性能評価・Production昇格は未実施。

変更前の検証根拠: [Actions #710](https://github.com/eda-hub/horse-man/actions/runs/38029365215)の回帰233件、原票・集計・R01〜R06監査。手順4では対象台帳・専用checkerと7回帰を追加。既存条件定義・snapshotは変更しない。

残る仕様・実装: provider固有の結果規則対応、追加集計ごとの期間/条件/分類版/標本数・比較方法、Phase 2のDB移行・取得adapter、非UIアプリ連携、Phase 8の効果検証。既存2条件の固定定義で決まっている期間・結果規則と、新規条件の未決仕様を区別する。

## 2026-10-10 調教国確定規則の改訂受入（追加）

以前の最多出走国方式は当時の検証履歴として記録を残すが、今回の利用者指定で新規適用を終了した。
今後の新規調査は`SEARCH_MATCH_PRIORITY_V1`を指定する。

- 一致国1カ国なら追加の国調査を必要とせず採用する。
- 複数国なら国別最多出走数を無視し、最終調教所属時期が直近の国を採用する。
- 所属時期不明・同日別国・未同定は推測せず保留する。
- 一致ゼロはユーザー確認を要する状態を記録し、タスク完了後にチャットで一覧照会する。
- ユーザー回答は原文・SHA-256・受領時刻・確認者を保持し`USER_PROVIDED`と明示して設定し、検索結果を上書きしない。
- 既存の`VERIFIED_COUNTRY`/`MOST_STARTS_BY_TRAINING_COUNTRY`の固定記録・snapshotの監査互換は維持する。

対応: `scripts/pedigree_registry.py`、`scripts/pedigree_stats.py`、`scripts/test_pedigree_stats.py`。
WebUI/DB/自動source adapterは変更せず、未来情報を新規FORWARD入力に流用しない。
実在する馬の未調査所属国までこのプログラム変更だけで確認済みとしない。


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
