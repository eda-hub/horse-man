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
| 8. cutoff後更新の混入防止 | 観測時刻照合、訂正/分類のcutoff回帰テスト | Git事実/派生情報は完了。統計更新はPhase 3 |
| 9. 再実行・再開・並行更新 | source/hash冪等、record hash CAS、単一Writer、原子的置換、Git HEAD照合 | 完了 |
| 10. 調査→検証→保存→読戻し→検索 | 手動候補入力のroundtrip、git_commit_readbackテスト | 手動経路完了。自動source adapterは未実装 |
| 11. 不足・障害・未保存と有限再試行 | source別に初回＋2回の3回目で上限確定、planとforceでも停止。時間予算と状態を分離 | 完了（自動照会なし、再調査可否を返す） |
| 12. 出所不明旧記述の自動昇格禁止 | LEGACY_REPOSITORYはVERIFIED拒否、manifest監査 | 完了 |
| 13. 重賞固有集計・新スコアの隔離 | 事実fieldの許可リスト、移行傾向候補分離、Production request拒否 | Git APIは完了。統計featureはPhase 3/8 |
| 14. 予想snapshot保存と混同しない | LOCAL/Git/remote保存を分離、snapshot_persistence=NOT_EVALUATED | 完了 |
| 15. DB移行後もID等一致 | 移行契約とJSON Writer停止を設計・テスト | 実DB移行/読取adapter/照合はPhase 2で未実施 |
| 16. 既存監査・固定予想の維持 | 全141 unittest（追加6件）、Git履歴取得後の血統audit、既存の固定予想は不変更 | 完了（既存の不足は残存） |

追加機能のテスト32件を含む全141件が通過。血統auditは535候補のhash/件数/未確認状態を検証してPASS。確認済みhorseレコードは0件であり、既存記述を事実へ自動変換したとは主張しない。

移行: PR69取得時点commit `439faa54a524ce9d242f100788f2a80fa2b0b698` の55ファイルから535記述・626成分・明示的父/母父候補106件。元外部出所の再照合と馬ID同定は未完了として候補内に保持。過去チャット・他ブランチは未アクセス。REPLAY資料をFORWARD証跡へ変換していない。

既存の予想compliance監査は3件のゲート照合不足、persistence監査は40件の歴史的不足を報告。変更前のコード/データから実行した監査と出力が一致し、今回増加していない。監査通過・過去証跡復元とは報告しない。第3サイクルcheckerはCONSISTENT（未作成日4・KPI保留10が残存）。

Phase 2以降の実DB・取得adapter、Phase 3のfeature/snapshot接続、Phase 4のUI、Phase 8の評価・昇格は既存Phase順で引継ぎ。次期manual/AGENTS/調査テンプレートへの必須運用接続は、PR68どおり第3サイクル終了審査後のStage 2。現行manual、v1/v2 gateの意味を変更していない。

## PR69レビュー指摘の改修と検証（2026-10-09）

- P1 直接 `parent:SS` / `parent:SSS` にVERIFIEDがあっても、独立した共通祖先の該当経路に競合があればCONFLICTを返す。planの不足、deriveのUNKNOWNへの伝播とcutoff前の再現を回帰テストで確認。
- P1 `update-identity` は現レコードhashのCAS、理由・確認者・同定根拠、以前と以後のidentity・イベントhashを追記。通常saveでの暗黙更新、IDの付替え、確認済み状態の後退を拒否。auditは同定履歴改ざんを検知。
- P2 同一要求・同一sourceは初回＋2回で `retry_exhausted=true`。待機期限後やforce指定でもplanは `RETRY_EXHAUSTED` を維持。別sourceを分離し、従来の時間予算切れ記録との互換性を維持。
- P2 移行は `git ls-tree` と `git show` で指定commitの実内容から作成し、未コミット変更・未追跡資料を除外。同commitでの再実行は再生成結果の完全一致時だけ冪等扱い。不一致時は既存manifestを保全し、audit --repoで元commitとの対応を再検査。
- CIはGitの移行元commitを監査できるよう `checkout fetch-depth: 0` とした。GitHub Actionsでunittest全141件および血統auditを含むworkflow成功を確認。既存の歴史的証跡不足は未解消のまま扱い、修復完了を主張しない。
