# PR68追加計画の受入結果

対象計画: PR68 `docs/proposals/2026-10-09_pedigree_research_registry_implementation_plan.md`。この文書は実装・検証結果であり、別の計画書ではない。

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

Phase 2以降の実DB・取得adapter、Phase 3のfeature/snapshot接続、Phase 4のUI、Phase 8の評価・昇格は既存Phase順で引継ぎ。次期manual/AGENTS/調査テンプレートへの必須運用接続は、PR68どおり第3サイクル終了審査後のStage 2。現行manual、v1/v2 gateの意味を変更していない。

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
