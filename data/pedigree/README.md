# 血統調査リスト

調査前に保存済み情報を検索し、確認済み・時点適合の項目を再利用する。不足だけを調査し、候補を検証して保存・読戻しする。計画の正本は [PR68](https://github.com/eda-hub/horse-man/pull/68) の `2026-10-09_pedigree_research_registry_implementation_plan.md`。ここは実装の利用手順であり、競馬判断のOwnerは `docs/manual/` のまま。

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

祖先の調教国はその祖先馬を対象とした別要求の `attribute:training_country` で照合する。生産国は `attribute:birth_country` であり調教国へ代用しない。要求した範囲を確認し切れていなければ内包は `UNKNOWN`。完全な範囲だけ `ABSENT_WITHIN_SCOPE` を返す。最大深さは10代、既定は5代。欠測を推測補完しない。

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

**同定の時点管理**：検索の `--cutoff`、`plan` の `data_cutoff`、`derive` の `--cutoff` では、`identity_revisions` の各更新時刻からその時点の `status / external_ids / aliases / identity_evidence` を復元する。cutoff後に確定した同定情報は過去のVERIFIED事実・祖先パスへ流用しない。祖先馬の独立レコードも同じ時点で照合する。更新履歴のない初期identityは既存データ互換の基準状態として扱い、初期作成前の同定を実証したものと解釈しない。

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

Phase 2以降のDB/UI/feature評価はまだ設計段階。DBへの移行はID・revision/hash・時刻・出所を保存したexport照合と旧読取adapterを伴い、唯一WriterをDBへ変更する。`writer.json` がJSON以外ならこのスクリプトの直接更新は拒否する。現行v1.6.1と既存予想監査は変更しない。
