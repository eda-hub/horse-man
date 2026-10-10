# 血統調査リスト

調査前に保存済み情報を検索し、確認済み・時点適合の項目を再利用する。不足だけを調査し、候補を検証して保存・読戻しする。計画の正本は [PR68](https://github.com/eda-hub/horse-man/pull/68) の `2026-10-09_pedigree_research_registry_implementation_plan.md`。ここは実装の利用手順であり、競馬判断のOwnerは `docs/manual/` のまま。

## 最新状態と完了境界（2026-10-10）

確認基準はPR69 `180c595c5044faaaa231619caee8674038f2d0ec`の実レコードとR02原文照合。[調査実施記録](reconciliations/2026-10-10-training-priority/README.md)と[実データsummary](reconciliations/2026-10-10-alternative/scope_summary.json)を現在の実施範囲の根拠とする。

- JRA対象期間2026-08-16〜2026-10-04の159レース・2,089頭を照合し、2,182登録行・2,177実出走に対する父キズナ・母父ディープインパクトの固定REPLAY集計はCOMPLETE。全血統条件や海外の完了ではない。
- 調教国対象は父・母父613頭。資料確認30頭の実レコードでは25頭がRegistry登録済み、5頭が未登録。R01/R02の10頭は原HTML照合済み、登録済み15頭は原文再確認待ち。583頭は従来台帳で未検索。指定祖先28表記は必要対象の確定前。
- 旧535記述の父・母父106成分（53記述）は原票照合済み。残る482記述の解釈・傾向は保留。元migrationの未確認候補は書き換えず、別の照合記録から参照する。
- 新しい調教国判定とユーザー回答保存は実装済み。旧最多出走国方式は固定履歴の再現専用。
- 実DB移行、自動取得adapter、非UIアプリ連携、正式契約切替、前向き評価・Production採用は別工程。WebUIは利用者指定で実施対象外。

## 操作

リポジトリのルートで実行する。Python標準ライブラリのみ使用（Mac/Linux、単一Writer）。

```sh
# 登録馬・別名・provider IDで検索。同名の候補は自動統合しない。
python3 scripts/pedigree_registry.py search '対象馬名'
# 過去の時点で確認できた馬名・別名・provider ID・同定根拠のみを検索する。
python3 scripts/pedigree_registry.py search '対象馬名' --cutoff '2026-09-01T00:00:00+09:00'
# 過去調査の未確認候補を検索。結果はProduction入力に使用しない。
python3 scripts/pedigree_registry.py claims '母父'
# 対象・必要項目・cutoffを明示して不足だけを調査要求へ保存。
python3 scripts/pedigree_registry.py plan /tmp/request.json
# 出所と同定を確認した候補を保存。更新時は最新レコードのcanonical hashが必須。
python3 scripts/pedigree_registry.py save /tmp/candidate.json --expected-hash '<最新content_hash>'
# 同定状態・出所IDの更新は通常saveではなく履歴付き専用操作（下記）を利用。
# 追加保存後に同じ要求を再評価する。充足済みなら外部照会・調査要求は0件。
python3 scripts/pedigree_registry.py plan /tmp/request.json
python3 scripts/pedigree_registry.py audit
```

新規レコードは `--expected-hash` なし。既存レコードは `scripts.pedigree_registry.digest` で読取内容のcanonical SHA256を計算する。競合エラー時は最新レコードを読み、候補を項目単位で再統合して再実行する。force pushしない。

要求例（`S` は父、`D` は母。`DS` は母父）:

```json
{
  "schema_version": "pedigree-registry-v1",
  "request_id": "example-request",
  "horse_key": "provider-example-id",
  "fields": ["parent:S", "parent:DS"],
  "ancestors": ["ancestor-roberto-id", "ancestor-danzig-id", "ancestor-caro-id"],
  "depth": 5,
  "data_cutoff": "2026-10-09T10:00:00+09:00"
}
```

新規調査では祖先馬本人を対象に `attribute:training_country_matches` を照合し、検索不一致時だけ `attribute:training_country_user` を参照する。旧 `attribute:training_country` は固定履歴の互換読取専用。生産国は `attribute:birth_country` であり調教国へ代用しない。要求した範囲を確認し切れていなければ内包は `UNKNOWN`。完全な範囲だけ `ABSENT_WITHIN_SCOPE` を返す。最大深さは10代、既定は5代。欠測を推測補完しない。

## 候補入力と確認

初期版は手動取得・候補JSON入力の経路を実装している。JRA-VAN/JRAが利用できる場合は優先し、次にJBIS等の血統DB、Web補助は補助経路と明記する。未確認のAPI・Web parserを自動取得経路として実装していない。スクリプトはネットワークアクセスしないため、`external_queries=0` は本スクリプトの外部照会数であり、利用者のブラウザ調査件数を意味しない。

候補は `schema_version`, `horse_key`, `identity`, `facts` を持つ（`schema.json` 参照）。同定はprovider IDを優先する。ローカルIDには生年・国・親情報と同定根拠が必要。曖昧な同名候補は `IDENTITY_UNRESOLVED` のまま保存する。別名変更・ID統合を暗黙に行わない。

未同定馬の追加調査後は、同じ `horse_key` の完全なidentityを記載した候補JSONを作り、以下の明示操作で更新する。通常の `save` はidentityの変更を拒否する。

```sh
python3 scripts/pedigree_registry.py update-identity /tmp/identity-candidate.json \
  --expected-hash '<現在の馬レコード全体のdigest>' \
  --reason '同定した出所と更新理由' --reviewed-by '<確認者>'
python3 scripts/pedigree_registry.py audit
```

`update-identity` は現行hashをCAS照合し、旧identity・新identity・確認者・理由・更新時刻・イベントhashを `identity_revisions` へ追記する。確認済みにする場合は `identity_evidence.source/record_key` と同定用ID、または生年・国・親情報を必須とする。既存外部IDの付け替えや確認済み状態への逆行（未同定へ戻す操作）は拒否する。更新後も既存の血統revisionは維持し、別名インデックスを再構築する。

**同定の時点管理**：初回登録時にシステムが確定した `identity_observed_at`（初期同定の観測・登録時刻）と、RESOLVEDの場合の `identity_confirmed_at`（同定確定時刻）を保存する。`initial_identity` は初期状態の監査用コピーである。未同定で新規登録した場合は `identity_confirmed_at=null` とし、`update-identity` による初回の明示的な同定確定時刻を記録する。初期の時刻は外部資料の公開日や候補factの古い `first_observed_at` で遡及させず、Writerの実際の保存時刻を使う。

検索の `--cutoff`、`plan` の `data_cutoff`、`derive` の `--cutoff`、属性・祖先参照では、**初回観測時刻より前は一切VERIFIEDにしない**。その時点では検索候補を表示せず、事実・祖先は `IDENTITY_UNRESOLVED` とする。初回観測後は `identity_revisions` で時点の同定状態・外部ID・別名・根拠を復元する。初回観測時点で未同定なら、後日確定するまでVERIFIEDにしない。独立祖先レコードにも同じ制約を適用する。

初回観測時刻がない旧horseレコードは、過去のcutoffへ最新同定を流用せず**未確認扱い**にする。`audit` は初期観測・確定時刻や初期状態が欠けたhorseレコードをFAILとする。旧データに対して根拠不明な日時を自動補完してはならず、原証跡を確認した上で別途明示的な移行を行う（移行済み過去候補は `migration.json` 内に未確認として保管する。2026-10-09の外部原票照合で初めて作成したhorseレコードの根拠・範囲は下記実データ照合記録を参照）。

祖先馬は先に独立レコードを登録する。事実は `parent:<path>` または生産国・調教国・性別の属性のみ受理し、系統・適性評価・レース傾向・スコアは事実へ書き込めない。各事実は次を持つ。

- `field`, `value`, `status`（`VERIFIED / UNVERIFIED / CONFLICT`）
- `first_observed_at`, `captured_at`（タイムゾーン付き。公開日をシステム観測時刻へ流用しない）
- `source`: URLまたはrecord key、source class、origin group、取得方法、元record SHA256、任意provider timestamp
- VERIFIEDなら `verification`: `identity_checked`, `source_checked`, `relationship_checked` がtrue、`reviewed_by`

AIの出力は候補であり、自動的なVERIFIED判定をしない。確認者は原出所と馬ID・親子関係を確認してverificationを記載する。元資料が追跡できない旧記述は `LEGACY_REPOSITORY + UNVERIFIED` として扱う。過去資料を今回初めて見た場合、観測時刻は今回の時刻とし、過去予想時点で既知だったことにしない。

例（架空の入力構造。実データとして登録しない）:

```json
{
  "schema_version": "pedigree-registry-v1",
  "horse_key": "provider-example-id",
  "identity": {
    "name": "対象馬名", "aliases": [], "birth_year": 2023,
    "external_ids": {"provider": "example-id"}, "status": "RESOLVED",
    "identity_evidence": {"source": "provider", "record_key": "example-id"}
  },
  "facts": [{
    "field": "parent:S", "value": "provider-sire-id", "status": "UNVERIFIED",
    "first_observed_at": "2026-10-09T10:00:00+09:00",
    "captured_at": "2026-10-09T10:00:00+09:00",
    "source": {"source_class": "BREEDING_DB", "origin_group": "provider",
      "acquisition_method": "manual", "record_key": "example-id",
      "record_hash": "元レコードの64桁SHA256"}
  }]
}
```

## 再計算・訂正・時点

`derive` は血統revision/hashと祖先位置を返し、内包・クロス・父系/母父系を元血統から再計算する。分類JSONには版・根拠・観測時刻・祖先ID→系統対応を持たせる。実際の分類を未調査のまま初期値として登録しない。

```sh
python3 scripts/pedigree_registry.py derive '<horse_key>' --ancestor '<ancestor_key>' --depth 5 --cutoff '<時刻>' --taxonomy-version '<版>'
```

異なる値は両方を残しCONFLICT。訂正は現行競合revisionすべての `supersedes`、`correction_reason`、権威ある出所と再確認を必須とする。訂正前revisionは消さず、cutoff前の値を再現する。分類版と血統revision/hashは予想根拠側で固定する。リスト保存だけで予想snapshotやreceiptの保存完了を宣言しない。

## 失敗・再開

```sh
python3 scripts/pedigree_registry.py failure '<request_id>' 'parent:DS' SOURCE_ERROR --source-key '<調査先>' --max-retries 2 --budget-seconds 60
python3 scripts/pedigree_registry.py failure '<request_id>' 'parent:DS' NOT_FOUND --source-key '<調査先>' --not-found-hours 24
# --forceが解除するのは次回試行までの待機だけ。回数上限・時間予算切れは解除しない。
python3 scripts/pedigree_registry.py plan /tmp/request.json --force
```

NOT_FOUNDは指定調査先・範囲の未取得、SOURCE_ERRORは通信・認証・parser障害、SAVE_ERRORは未保存。同じ要求・同じsourceの初回＋最大2回の再試行（計3回）で `retry_exhausted=true`、`plan` は `retry_state=RETRY_EXHAUSTED` を返す。期限経過や `--force` でも同じsourceの上限は解除しない。別の出所を確認する場合は `source_key` を変更する。時間予算切れは `BUDGET_EXHAUSTED` として扱い、`plan --force` でも`started_at`と`deadline_at`を変更しない。`failure` も期限切れや過去の予算切れの追記を拒否する。新しい調査期間が必要なら**新規request_idで明示的な別要求**を作成する（同じrequest_idの時間予算はリセットしない）。同じ要求の再試行期限と有限予算を記録する。初期版は自動調査を実行せず、再調査してよいかを不足リストへ返す。保存エラーは成功扱いせず、取得済み候補から再開する。

## Git保存

単独調査は `research/pedigree/<request_id>`、予想中は既存の `prediction/YYYY-MM-DD`。mainへ直接書き込まない。

```sh
python3 scripts/pedigree_registry.py git-save --expected-head '<読み取ったbranch HEAD>'
```

JSONの監査後、血統ディレクトリだけコミットし、同じcommitの内容を読戻してhashを返す。これはローカルGit保存確認であり、remote保存は別。remoteへの反映は読取HEAD/blob SHAを照合するGitHub Writerまたは通常の非force pushで行い、返却commit SHAから同一ファイルを読戻して内容hashを確認する。正式共有はmain向けPR。別ブランチの登録情報を利用する場合は対象ブランチを取得・明示し使用commitを根拠に固定する。

## 過去調査移行

`migration.json` は55ファイルを検索して抽出した535記述、626成分（明示的父/母父候補106件）のmanifestを保持する。各記述に元ファイル・commit・行・原文・hashを付ける。明示的な表の親情報、系統主張、傾向/適性解釈は成分で分離する。馬ID未確認のためすべて未確認候補であり、horsesのVERIFIED事実へ混ぜない。元ファイルは保持する。

過去チャット・他ブランチ・元外部出所は未アクセス範囲として記録済み。全履歴を網羅したという主張はしない。移行は初回観測時刻を固定して実行する。再実行時も元の観測時刻を使用し、公開日時や再実行時刻へ置き換えない。

```sh
python3 scripts/pedigree_registry.py migrate --repo . --commit '<取得済みのcommit SHA>' \
  --observed-at '<初回確認日時（タイムゾーン付き）>'
python3 scripts/pedigree_registry.py audit --repo .
```

移行元は `git ls-tree` / `git show` で**指定commitに含まれるファイルの内容のみ**を読み込む。未コミット変更・未追跡ファイルは抽出しない。再実行時は元manifestとcommit由来の再生成結果が完全一致することを確認し、不一致なら元manifestを保全して失敗する。`audit --repo` はGit側のcommit内容との一致も検査する。移行元commitがローカルに存在しなければ中止し、作業ツリーへフォールバックしない。

## DB引継ぎ

実DB移行・非UIアプリfeature接続と効果評価は未実施。Git JSONの限定実データ集計は実施済み（冒頭参照）。WebUIは実施対象外。DBへの移行はID・revision/hash・時刻・出所を保存したexport照合と旧読取adapterを伴い、唯一WriterをDBへ変更する。`writer.json` がJSON以外ならこのスクリプトの直接更新は拒否する。現行v1.6.1と既存予想監査は変更しない。


## 血統別・条件別成績の集計（独立）

血統調査リストの検索・確認と、実際の出走成績の集計は別工程。PR68の11節に基づくGit JSON準備実装は [条件別成績集計の手順](../condition_stats/README.md) と [12受入条件](../condition_stats/acceptance.md) を参照。現行`pedigree_registry.py`は血統・同定事実の唯一Writerとして維持し、`pedigree_stats.py`はそれらの時点適合するrevisionを読むだけ。未確認候補535件を成績集計の母数や確定血統へ変換しない。条件別統計をProductionへ採用するにはPhase 8と独立PRが必要。


## 2026-10-09 実データ照合（追加取得前の履歴）

以下は当時の状態。現在の取得・集計範囲は冒頭の最新状態を参照する。

予想対象期間2026-08-16〜2026-10-04の記録にある父・母父53頭106項目をJRA原票と照合し、103項目完全一致・3項目表記差一致を確認。参照済みJBIS52血統表の5代3,224位置を照合し、独立した1,430個体・1,774親子関係を唯一Writerで新規保存した。元535候補・旧予想は変更しない。取得日より前のcutoffへの流用は禁止。

[照合結果・出典・未確認範囲](reconciliations/2026-10-09/README.md)。`python3 scripts/check_pedigree_reconciliation.py`で元候補との対応、原票値・個体ID・hash、全祖先位置と保存レコード、過去cutoffを再検証できる。期間全体の公式全出走・結果母数は未取得であり、条件別実成績の集計完了を意味しない。


## 調教国の検索結果登録（新規調査）

最新の調教国決定規則は[条件別統計の調教国優先規則](../condition_stats/README.md#調教国の確定優先順位2026-10-10-改訂)に定義する。
調査対象は予想・集計で使用する父・母父・指定祖先を先行とし、対象外の全祖先へ無制限に広げない。
検索一致が1国ならその国で止め、複数国なら直近の調教所属国を選び、検索一致ゼロならタスク終了後のチャットでユーザー照会する。
検索後は唯一Writerから`attribute:training_country_matches`の構造化事実を保存する。
検索一致が無い場合は`matches=[]`と`search_completed=true`を記録するが、国を推測しない。
ユーザー提供国は検索不一致でのみ`attribute:training_country_user`へ
`source_class=USER_PROVIDED`、`acquisition_method=user-chat`として保存し、
`source.user_reply_text`に回答原文、`record_hash`に原文SHA-256を設定する。
受領時刻・対象馬同定・確認者を併記し、読戻し後に未確認状態を更新する。
検索一致・同率・時点不足は独立管理し、以前の固定REPLAY集計を上書きしない。
