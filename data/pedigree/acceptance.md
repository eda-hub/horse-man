# PR68追加計画の受入結果

## R07再開の追加結果（2026-10-11）

対象期間の22PRから、HEAD・全PR commit履歴・閉鎖21PRのmerge commit、計253commit（前回の実ツリー探索外192）と220種類の完全docs tree、宣言/receipt59種類のblobを照合。28対象にreceipt候補があったが、38件は対応宣言なし、1件は形式不足、1件は有効宣言に対応receiptなし。適格性回復0、全40件不適格・保留。新規の事前宣言/receiptは作らず、当時の予想・正式KPIを変更しない。

[探索範囲・保存証跡・取得できない残件](reconciliations/2026-10-10-training-priority/persistence-pr-ref-review/README.md)を参照。利用可能なGitHub参照を通じた追加調査は実施済みであり、40件の不足解消は未完了。PRのない削除branch・参照不能commit・ローカルreflog・Git外の真正証跡は取得できていない。以下は各実施時点の受入履歴。

## R06再開の追加結果（2026-10-10）

原文で個体・親子経路・祖先側・代数が明記された35記述の70事実成分を追加照合し、70一致。前回54照合を保持し、累計124照合・56記述、123一致・1不一致。オールナットとシランケドはJBIS本人原HTML・生年・父の独立IDを確認し、唯一Writerで本人2頭と父revision2件を保存/readback。母や5代全体を新規確認済みとはしていない。

全482記述の残件キューを保存し、56記述は事実成分のみ部分照合、426記述は追加照合なし。記述全体の昇格0。適性・優位性・派生解釈は未検証を維持する。[今回の照合と再開位置](reconciliations/2026-10-10-training-priority/legacy-fact-followup/batch-02/README.md)を参照。以下は各実施時点の受入履歴。

対象計画: PR68 `docs/proposals/2026-10-09_pedigree_research_registry_implementation_plan.md`。この文書は実装・検証結果であり、別の計画書ではない。

## 最新の受入状態（2026-10-10 継続実行後）

正本は[受入再照合manifest](reconciliations/2026-10-10-training-priority/acceptance-recheck.json)。現行v1.6.1・旧予想・既存3統計snapshotは保持し、PR69はDraft。WebUIは対象外。

| 対象 | 最新状態 | 残件・完了境界 |
|---|---|---|
| Git保存・検索・不足判定・訂正・時点制約 | 準備実装と回帰検証済み。JSON Schemaを調教国の検索・利用者回答属性とUSER_PROVIDEDへ整合 | DB移行・自動source adapter・アプリ接続は未実施 |
| JRA対象期間の血統確認 | 159レース・2,182登録行・2,089頭、必要5代確認済み | 対象外期間・全属性の完了を意味しない |
| 父・母父の調教国 | 613頭＝外部518＋利用者指定95、確認待ち0 | 利用者提供値と外部原票を区別。旧cutoffへ逆流させない |
| 指定祖先 | 28表記を21個体へ対象化。追加調査12頭は外部11＋ノーザンダンサーの利用者指定US 1、未確定0 | 生産国・子孫の所属を本人調教国に流用しない |
| 海外4レースの血統 | 42登録行＝38出走＋4取消の同定・必要5代2,604位置を保存/readback | York結果のBHA原票照合と海外条件集計は未完了 |
| 旧535記述・626成分 | 既存父・母父106成分を保持。残482記述を分類し、固定commitの32ファイルと原文hash照合 | 未確認219成分・派生218成分・仮説83成分の追加検証。新規記述全体の昇格0 |
| 歴史的保存不足40件 | 当日Git履歴と本文を再照合。38件は対応宣言なし、1件は真正宣言の形式不足、1件はreceipt不在 | 全40件は不適格・保留。全branch/中間commitの探索完了や遡及適格化を主張しない |
| 血統・地域条件集計 | JRA159レース・2,182登録行・2,177実出走に対する父/母父EU・USと指定祖先21条件、計25条件をREPLAYで保存/readback。結果はCOMPLETE。欧州対象国は利用者指定の英・愛・仏・独・伊。 | 条件の直積・未定義系統/クロス・海外全体は対象外。新しい前向きKPI・Production採用ではない |
| 正式切替とアプリ | 未実施 | 10/12開催までの第3サイクル終了審査後、Stage切替と非UIアプリPhaseを各独立PRで扱う |

下記は各実施時点の履歴。現在の完了件数はこの表とmanifestを参照する。

## 初期基盤の受入履歴（追加照合前）

以下の表・件数・不足件数は初期基盤の検証時点の履歴であり、現在の残件判定には上の最新状態を使用する。特に「確認済みhorseレコード0件」「実データ母数未取得」は追加照合前の状態である。

| 計画の受入条件 | 実装・検証 | 結果 |
|---|---|---|
| 1. 登録済み要求は外部調査0件 | planの再利用判定、registered_requestテスト | 完了 |
| 2. 父登録済みなら不足母父だけ | only_missing_dam_sireテスト | 完了 |
| 3. 共通祖先を重複取得/加点しない | 独立祖先レコード再利用。直接経路と独立祖先の競合を不足へ伝播 | 完了 |
| 4. 同名・曖昧別名を誤統合しない | 名前は候補検索、外部ID重複拒否。明示的update-identityのCAS/証跡/追記履歴を検証 | 完了 |
| 5. 不完全なら内包なしにしない | PRESENT/ABSENT_WITHIN_SCOPE/UNKNOWN、complete_scopeテスト | 完了 |
| 6. 分類変更は原血統再取得なし | taxonomy版/hashとderive、taxonomy_changeテスト | 完了 |
| 7. 競合保持・訂正前再現 | append-only revision、supersedes/理由、conflict_correctionテスト | 完了 |
| 8. cutoff後更新の混入防止 | 初回のidentity_observed_at/identity_confirmed_atと初期状態を保存。初回観測前の検索・属性・祖先は未確認、後日の同定更新は時点履歴で復元。日時欠落・不整合をaudit拒否 | Git事実/派生/同定情報は完了。統計更新はPhase 3 |
| 9. 再実行・再開・並行更新 | source/hash冪等、record hash CAS、単一Writer、原子的置換、Git HEAD照合 | 完了 |
| 10. 調査→検証→保存→読戻し→検索 | 手動候補入力のroundtrip、git_commit_readbackテスト | 手動経路完了。自動source adapterは未実装 |
| 11. 不足・障害・未保存と有限再試行 | source別に初回＋2回で上限確定。forceでも回数上限・時間予算は解除しない。plan/failure双方で期限切れを拒否 | 完了（自動照会なし、再調査可否を返す） |
| 12. 出所不明旧記述の自動昇格禁止 | LEGACY_REPOSITORYはVERIFIED拒否、manifest監査 | 完了 |
| 13. 重賞固有集計・新スコアの隔離 | 事実fieldの許可リスト、移行傾向候補分離、Production request拒否 | Git APIは完了。統計featureはPhase 3/8 |
| 14. 予想snapshot保存と混同しない | LOCAL/Git/remote保存を分離、snapshot_persistence=NOT_EVALUATED | 完了 |
| 15. DB移行後もID等一致 | 移行契約とJSON Writer停止を設計・テスト | 実DB移行/読取adapter/照合はPhase 2で未実施 |
| 16. 既存監査・固定予想の維持 | 全150 unittest（今回さらに4件追加）、Git履歴取得後の血統audit、既存の固定予想は不変更 | 完了（既存の不足は残存） |

追加機能のテスト41件を含む全150件が通過。血統auditは535候補のhash/件数/未確認状態を検証してPASS。確認済みhorseレコードは0件であり、既存記述を事実へ自動変換したとは主張しない。

移行: PR69取得時点commit `439faa54a524ce9d242f100788f2a80fa2b0b698` の55ファイルから535記述・626成分・明示的父/母父候補106件。元外部出所の再照合と馬ID同定は未完了として候補内に保持。過去チャット・他ブランチは未アクセス。REPLAY資料をFORWARD証跡へ変換していない。

既存の予想compliance監査は3件のゲート照合不足、persistence監査は40件の歴史的不足を報告。変更前のコード/データから実行した監査と出力が一致し、今回増加していない。監査通過・過去証跡復元とは報告しない。第3サイクルcheckerはCONSISTENT（未作成日4・KPI保留10が残存）。

非UI後続工程はPhase 2の実DB・取得adapter、Phase 3のアプリfeature/snapshot接続、Phase 8の評価・昇格へ引継ぐ。Git JSONで実施済みの限定集計は上の最新状態を参照する。WebUIは利用者指定で実施対象外。次期manual/AGENTS/調査テンプレートへの必須運用接続は、PR68どおり第3サイクル終了審査後のStage 2。現行manual、v1/v2 gateの意味を変更していない。

## PR69レビュー指摘の改修と検証（2026-10-09）

- P1 直接 `parent:SS` / `parent:SSS` にVERIFIEDがあっても、独立した共通祖先の該当経路に競合があればCONFLICTを返す。planの不足、deriveのUNKNOWNへの伝播とcutoff前の再現を回帰テストで確認。
- P1 `update-identity` は現レコードhashのCAS、理由・確認者・同定根拠、以前と以後のidentity・イベントhashを追記。通常saveでの暗黙更新、IDの付替え、確認済み状態の後退を拒否。auditは同定履歴改ざんを検知。
- P2 同一要求・同一sourceは初回＋2回で `retry_exhausted=true`。待機期限後やforce指定でもplanは `RETRY_EXHAUSTED` を維持。別sourceを分離し、従来の時間予算切れ記録との互換性を維持。
- P2 移行は `git ls-tree` と `git show` で指定commitの実内容から作成し、未コミット変更・未追跡資料を除外。同commitでの再実行は再生成結果の完全一致時だけ冪等扱い。不一致時は既存manifestを保全し、audit --repoで元commitとの対応を再検査。
- CIはGitの移行元commitを監査できるよう `checkout fetch-depth: 0` とした。GitHub Actionsでunittest全141件および血統auditを含むworkflow成功を確認。既存の歴史的証跡不足は未解消のまま扱い、修復完了を主張しない。

## 2026-10-09 再レビュー2件の追補

- **P1 同定状態のcutoff**：`identity_at(record, cutoff)` で同定revisionを時刻に従って復元する。`search --cutoff`、`plan.data_cutoff`、`fact`、`edge`、`derive` へ接続。直接登録された祖先経路でも、中間祖先や参照先の同定が当時未解決ならVERIFIEDを返さない。新しい外部ID・別名・同定根拠を過去時点へ流用しない。履歴更新時刻の逆転を拒否。
- **P2 時間予算の固定**：`plan --force` はDEFERREDの待機期限のみを解除する。既存requestの`started_at`/`deadline_at`を再設定せず、時間予算切れを常に`BUDGET_EXHAUSTED`として通知。`failure` でも期限切れ・既に失効した調査期間の追加失敗を拒否。新しい期間は別request_idを明示して開始。
- 遡及同定、祖先経路、同定根拠の時点変更、時間予算消尽済みのforceとfailureの一致など**5件の新規回帰テスト**を追加。既存141件と合わせて146件を実行。
- 運用詳細は`data/pedigree/README.md`へ反映。既存Predictionのゲート・snapshotの意味や第3サイクルの固定予想は変更していない。

## 2026-10-09 新規登録の初期同定時刻のcutoff制約（再指摘P1）

- `Registry.save` で初回の `initial_identity`、`identity_observed_at`、`identity_confirmed_at` を保存。Writer保存時の観測時刻を使用し、属性の旧 `first_observed_at` で同定時刻を遡及させない。
- `identity_at` は初期観測時刻より古いcutoff、初期記録に観測時刻がない場合は未確認扱い。検索は該当候補を返さず、属性・祖先・derive・planは確認済みとして扱わない。初期未同定→後日確定は同定更新イベント時刻から有効になる。
- `audit` は初期identity欠落、観測時刻欠落、初期同定確定時刻と実履歴の不一致、初期履歴チェーンの不一致を失敗として扱う。
- 新規RESOLVED馬の過去cutoff、未同定から確定した境界、初期時刻の不正、初期登録より前の同定更新拒否の4回帰テストを追加し、全150件の回帰テストと血統auditを検証。
- 既存の移行済み未確認候補（535記述）をVERIFIEDへ昇格させず、過去予想の推測補完を行わない。


## 2026-10-09 実データ照合の追補

当初の未登録状態とは分けて、予想対象期間2026-08-16〜2026-10-04の父・母父106成分をJRA原票で再確認（103完全一致・3表記差一致）。参照JBIS52血統表の全5代3,224位置は基本情報6関係と一致し、共通親子関係に競合なし。唯一Writerで1,430個体・1,774親子関係を保存した。

`check_pedigree_reconciliation.py`による原票/元claim/保存レコード/時点の照合とRegistry監査を実施。既存212件と後日の追加・競合に対する固定時点の回帰テスト1件、計213 unittest成功。取得日より前のcutoffでは今回の登録を確認済みとして扱わない。全535旧候補の自動昇格・旧予想の変更・全出走公式母数に基づく成績集計はしていない。詳細は[照合記録](reconciliations/2026-10-09/README.md)。


## 2026-10-10 調教国調査方式の追加受入

新規調教国調査は予想・集計で使用する父・母父・指定祖先に限定して着手する。
検索1国一致で終了、複数国なら直近所属、検索一致ゼロならタスク完了後にチャット照会し、
回答を原文・hash・受領時刻付きのユーザー提供属性として保存する。
新方式は`training-country-matches-v1`として既存Registryに保存する。
旧最多出走国のスクリプト・記録は過去snapshotの再現専用として残す。
回答不能・同率・取得後cutoffを未確認に保ち、検証済みと報告しない。
アプリ/Web/DBの実装は今回対象外。PR68の血統計画§11.8を正とする。


## 手順4の追加受入（2026-10-10）

[対象確定結果](reconciliations/2026-10-10-training-priority/designated-ancestor-target-review.json)で28表記を21個体へ対応付け。父/母父613個体との重複8、追加13、合計626個体。旧候補・同定済みRegistryを保持し、個体ID・生年・役割・代表親子経路を5表記ごとの6区切りで固定した。

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

