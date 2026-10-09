# 血統調査リスト（Git正本・初期実装）

PR #69の[血統調査リスト計画](https://github.com/eda-hub/horse-man/blob/feature/next-cycle-prediction-contract/docs/proposals/2026-10-09_pedigree_research_registry_implementation_plan.md)に基づく、JRA-VANランタイム非依存の調査保存基盤。

## 利用手順

1. 対象馬を既存horse_key、外部馬ID、名称で照合する。同名馬が複数あればIDENTITY_UNRESOLVEDで止め、馬ID・生年・国・親情報を確認する。
2. queryで必要項目だけ指定し、VERIFIEDを再利用する。UNVERIFIED、CONFLICT、PARTIAL、UNKNOWNは不足として返す。
3. 不足項目だけ外部調査する。自動取得adapterと認証情報はこのスクリプトに含まれない。legacy-searchで過去ノートも調べられるが未確認候補としてのみ扱う。
4. 原資料を照合し、出所・record SHA-256・観測時刻・検証責任者を付けてadd-factする。
5. PERSIST_VERIFIEDのreceiptとgit_blob_shaを確認し、同じ作業ブランチへGitコミットして読戻す。スクリプトが返すreceiptはGit保存完了を保証しない。
6. 再度queryし、残存不足を確認する。予想snapshotのintent/receiptは独立して検証する。

## データ契約

- horses/<horse_key>.json: 1馬1レコード、追記型revisions。horse_keyは安全な小文字キー。名前をファイル名として使わない。
- identity: external_ids、names、birth_year、country、status、同定根拠。祖先にも独立したhorse_keyを割り当てる。同名や別の外部IDは自動統合しない。
- revision: field（parent.sire / parent.dam / attribute.training_country / attribute.breeding_country）、value、verification、verification_evidence、source、first_observed_at、captured_at、saved_at、revision_id、content_sha256、previous_revision_id（訂正時）、correction_reason。
- source: URLまたはprovider_record_keyの片方、source_class、origin_group、acquisition_method、record_sha256。同じ上流の転載を独立票にしない。
- aliases.json: 再生成できる派生索引。索引だけを同定根拠にしない。
- taxonomies/v1.json: 未確認の系統定義を登録しない初期分類台帳。祖先キーの根拠をレビューしてから拡張する。
- research/<request_id>.json: 要求・充足/不足・試行・receipt。backfillは旧ノートの未確認候補で、馬の検証済み事実とは別。
- migration_manifest.json: 移行元と抽出数、未確認、重複、アクセス不能範囲。旧ノートは削除しない。

## 操作例

呼び出し側で入力JSONを用意する。実際に照合していないデータをVERIFIEDとして登録しない。

~~~bash
python3 scripts/pedigree_registry.py register --input /tmp/horse-identity.json --expected-blob ABSENT
python3 scripts/pedigree_registry.py add-fact --input /tmp/verified-parent.json --expected-blob XXXXX
python3 scripts/pedigree_registry.py query --input /tmp/pedigree-request.json
python3 scripts/pedigree_registry.py plan --input /tmp/pedigree-request.json
python3 scripts/pedigree_registry.py legacy-search --term ディープ
python3 scripts/pedigree_registry.py attempt --input /tmp/source-error.json
python3 scripts/pedigree_registry.py reindex
~~~

XXXXXは読取済みのGit blob SHA。追加で共通オプション --expected-head HEAD_SHA を指定すると、編集前にHEAD変更を検出する。更新競合時は最新版を読み直して項目単位で再統合し、force pushしない。単一Writerロックと原子的置換だけではGitサーバーの保存完了を保証しない。

### query / plan要求JSON例

~~~json
{
  "request_id": "example001",
  "horse": {"provider": "JRA_VAN", "external_id": "公式馬ID"},
  "fields": ["sire", "dam_sire", "training_country@DS"],
  "contains": [{"ancestor_key": "roberto-id", "depth": 5}],
  "lines": [],
  "taxonomy_version": "v1",
  "data_cutoff": "2026-10-10T12:00:00+09:00",
  "mode": "FORWARD"
}
~~~

Sは父、Dは母。DSは母父。属性要求training_country@DSは母父の独立祖先レコードを参照する。containsは指定世代までの確認範囲が完全な場合だけABSENT_WITHIN_SCOPEとなり、未確認範囲はUNKNOWN。系統分類は版を持ち、元血統revisionから都度再計算する。

### verified fact入力例

~~~json
{
  "horse_key": "myhorse01",
  "field": "parent.sire",
  "value": "sirehorse01",
  "verification": "VERIFIED",
  "first_observed_at": "2026-10-09T10:00:00+09:00",
  "captured_at": "2026-10-09T10:00:00+09:00",
  "source": {
    "provider_record_key": "JRA-VAN/元レコードキー",
    "source_class": "OFFICIAL_JRA_VAN",
    "origin_group": "JRA_VAN_BLDN",
    "acquisition_method": "MANUAL_REVIEW",
    "record_sha256": "元レコード内容のSHA256を64桁小文字16進数で指定"
  },
  "verification_evidence": {
    "checked_by": "検証者",
    "method": "公式レコードと馬ID照合",
    "checked_at": "2026-10-09T10:00:00+09:00"
  }
}
~~~

SHAはプレースホルダー。スクリプトは構造・出所・時刻・親馬の同定・hashを検査するが、外部サイトの真偽は自動検証しない。確認不能の場合はUNVERIFIEDで登録する。

## 失敗・訂正・時間

- NOT_FOUNDはその調査先で未取得、SOURCE_ERRORは障害。いずれも祖先不存在の証拠ではない。
- NOT_FOUND再試行は既定24時間、SOURCE_ERRORは5分待ち・同一項目/調査先の最大2回。例外的な明示再調査は別要求として記録する。
- 不一致はCONFLICTとして両候補を残す。多数決をしない。訂正にはprevious_revision_idとcorrection_reasonが必要。
- FORWARDは観測・取得・検証・台帳保存時刻がcutoff以内の情報だけ。後日取得資料の再現はREPLAYと明記し、過去の発走前証跡に置換しない。
- 血統スコア、レース固有好走集計、Betting、manual release、Production順位はこの基盤では変更しない。新featureはPhase 2→3→4→8、Shadow、別PR承認が前提。
- 将来DBに移行するまではJSONだけがWriter。二重書込みは禁止。移行時にrevision/hash/cutoff/provenanceを照合する。

## 検証

~~~bash
python3 -m unittest discover -s scripts -p 'test_*.py'
~~~

過去ノート抽出は次のコマンドで実施する。

~~~bash
python3 scripts/migrate_pedigree_notes.py --source-commit SOURCE_SHA
~~~

今後のproviderの取得世代、調教国、訂正通知、Web自動取得の利用条件は未確認。一次情報が確認できない状態で自動的にVERIFIEDに昇格しない。
