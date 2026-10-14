# P1：初回から最終へのShadow状態管理の修正実施計画

## 目的・対象・状態

- 作成日：2026-10-14（JST）
- 作業branch：`fix/p1-final-shadow-state`
- 調査基準main：`b288bc1f39f61d68c6cf536608c11689575315e8`
- 状態：計画作成済み／実装未着手
- 目的：初回Shadowの履歴を保全し、最終時点の比較状態を正しいgateへ結び付け、Shadow状態の持越しで正常な最終Prediction/推奨登録が失敗しないようにする。
- 対象外：Shadow仮説の削除/昇格、Production再予想、推奨ロジック変更、実測性能の受入。

## 再現・原因・影響

`cycle04_workflow.record_prediction` は最新のPrediction gateへrowを更新するが、Shadow項目が非空の場合だけ日別Shadow KPIを更新する。初回ShadowがELIGIBLE、最終gateのShadow項目が空なら、日別の古いELIGIBLE状態が残る。一方、`check_cycle04.validate_day` は最新Prediction gateのShadow状態と突合するため不一致になる。

一時fixtureで初回の独立保存済み適格Shadowを登録し、別pathの正常な最終gate（Shadowなし）と正常な固定推奨を渡したところ、`KPI gate not eligible` で最終登録が拒否され、final_scopeは空のまま残った。初回履歴を消さず、Production/推奨を比較状態から独立させる必要がある。

## 修正方針

1. Shadowを単一の「最新row状態」だけに押し込まず、INITIAL/FINAL・固定Prediction gate hash・baseline・Shadow項目に結び付けた履歴として保持する。
2. 本計画の集計単位は既存のレース単位を維持する。日別Shadow KPIは「最新Predictionに対応する明示的な適用状態」を表し、初回の比較成績は独立履歴から追跡する。項目/phase別の追加追跡で同一レースを重複計上しない。
3. 新規履歴にはphase、固定gate path/hash、基準参照、項目IDと各状態/証跡を保存する。既存prediction_historyの固定gate参照を再利用し、同じgateの重複登録は冪等にする。
4. 最終が明示的に適用なしなら、最新KPIのtarget/eligible/ineligible/pending/reasonsを一貫して更新する。単に空配列だったことだけで、既に該当していた比較の未実施を適用なしに見せない。entryには適用判定と理由を明示し、該当判定は既存仮説の条件に従う。未確認は保留とする。
5. 初回適格→最終対象外、初回適格→最終保留/不適格、初回対象外→最終該当を区別する。最終の不足はその時点のShadowへ局所化し、独立保存済みProduction/推奨を失敗へ置換しない。
6. 初回比較が最終で実施されなくても、保存済み初回原本・receipt・固定gate・当時状態を削除しない。初回と最終の比較ペアを混ぜず、基準/cutoffが違うペアを同一比較として合算しない。
7. 既存記録の新履歴化が必要なら、保存済み固定gate/historyから確認できる事実のみを読取で構成する。未保存の適用判定やreceiptを後から作らず、不足は明示する。

## 実装対象・境界

| ファイル | 変更内容 |
|---|---|
| scripts/cycle04_workflow.py | phase別Shadow履歴と最新KPI状態を一貫更新。FINAL登録の局所性・冪等性を維持 |
| scripts/check_cycle04.py | 履歴の固定hash・最新状態・適用理由・KPI集合を共通検査。初回を最新gateで認証しない |
| scripts/chat_entry_assembly.py | previewとwriterで同じ適用判定・履歴更新を使う |
| scripts/chat_review_package.py | 初回/最終の履歴・不足を分けて出力 |
| scripts/chat_forward_coverage.py、chat_calibration_review.py、class_transition_shadow.py | 対象phaseの固定gate参照が同じ比較基準を指すか確認。必要箇所だけ修正 |
| scripts/test_cycle04_workflow.py、test_cycle04_acceptance.py、test_chat_entry_assembly.py、test_chat_review_package.py | phase遷移・不正履歴・原子的保存の回帰 |
| docs/validation/contracts/cycle04_operations.md、templates/chatgpt_prediction_task.md | 適用判定、履歴、最新KPIと比較履歴の区別を記載 |

先行するShadow証跡修正の強いvalidatorを再利用する。参照を残すだけで証跡検査を省略しない。共通moduleの変更・日別契約の追加項目は先行結果修正とも整合させる。

## 小項目別の実装・コミット計画

| 小項目 | 作業と完了条件 | 日本語コミット案 |
|---|---|---|
| 01 | 初回適格→最終ShadowなしでFINAL登録が拒否される現行挙動を回帰化し、phase遷移表をテストへ固定 | 初回Shadow状態が最終登録を阻む問題を再現 |
| 02 | phase/gateに結び付いた履歴と明示適用判定を実装。古い原本は保持 | 初回と最終のShadow状態を固定履歴で分離 |
| 03 | writer/validator/previewで最新KPIを一貫更新し、Production/推奨の登録独立性を確認 | 最終登録とShadow最新状態の整合を修正 |
| 04 | 回顧・比較読取入口へ履歴を接続し、重複計上と基準混在を防止。運用契約を更新 | Shadow履歴の回顧参照と運用手順を整備 |
| 05 | 全受入・manifest・統合検証・CIを実施し、本書へ対応記録を追記 | Shadow状態修正の統合受入とリリース整合を固定 |

## 受入条件

- 初回適格→最終明示対象外でも、正常な独立Prediction/推奨のFINAL登録が成功し、初回の比較履歴が残る。
- 初回適格→最終保留/不適格では、最新Shadowの不足が正しく表示され、Production/推奨の独立保存成功が維持される。
- 初回なし→最終該当、同じ証跡の再登録、複数項目で適格/不足が混在する場合も、各状態・対象集合・理由が一致する。
- 適用判定なしの空配列、根拠のない対象外化、古いELIGIBLEの持越し、履歴hash差替え・巻戻し・基準混在は拒否または理由付き保留となる。
- 予想・推奨・入力・receiptの既存bytesは不変。プレビューとwriterの判定が一致し、失敗時は旧台帳を保全する。
- 最新レース単位KPIと初回/最終の比較履歴を混同せず、同一レース・同一ペアを二重に集計しない。

## 検証・実装結果の記録

最低限 `test_cycle04_workflow`、`test_cycle04_acceptance`、`test_chat_entry_assembly`、`test_chat_review_package`、`test_chat_helper_market_independence`、`test_chat_forward_coverage`、`test_chat_calibration_review`、`test_class_transition_shadow` を実施する。全回帰・合成受入・release/統合検証は共通規約に従う。

実装時に本書へ「小項目／commit SHA／変更path／実行コマンド／期待結果／実結果／残件」を追記する。現在の全小項目は未着手。

## 共通の作業・統合規約

- 対象は常に `eda-hub/horse-man`。本書は実装計画であり、現行Productionルールの代用にしない。
- 利用者の依頼は計画書作成まで。以下の実装修正・実レース記録作成はまだ実施しない。
- 既存v1.7.0の予想骨格、価格不要推奨、Production/Shadow/任意市場の分離、旧v1.6.1履歴を維持する。実購入・価格・払戻・実測性能を標準完了の必須入力に戻さない。
- 合成fixtureは一時領域で検査し、実日別台帳・未来の事前証跡・実測0を作らない。第4開催の実測、過去研究の網羅、性能昇格を本修正PRのマージ条件にしない。
- コミット・PR説明・作業記録は日本語。各小項目を実装・対応テスト・セルフレビューまで行い、小項目ごとにコミットする。未完了項目を完了と記載しない。
- 実装開始時に本書、AGENTS、最新main、対象branch、関連Ownerと対象コードを読戻す。本書の基準以降に変更があれば差分を確認して計画を更新し、確認した再現・受入条件を維持する。
- 4件の統合順は「結果の適格性 → Shadow証跡 → 初回/最終Shadow状態 → サイクル完了」。各計画は単独の基準から作成するが、後続の実装では先行修正を取り込んだ最新mainを反映してから着手する。共通ファイルの変更は機械的なours/theirsで解消しない。
- 対象コード・テスト・運用契約を変更した最終内容で `python3 scripts/run_cycle04_acceptance.py --write` を成功させ、その後 `python3 scripts/build_v170_manifest.py` でrelease manifestを再生成する。先行PRの受入・manifestを単純にコピーしない。
- 全回帰、通常checker、合成受入、release整合、統合受入と3系統CIを確認する。開始認証の `--require-main` は未マージの候補branchを認証するために改変しない。統合受入は取得済みmainと候補branchの契約一致/未マージ拒否を正しく区別する。
- 必要な過去Git履歴・原票・PDF依存を取得できない検査は実行不能として残す。失敗をコード欠陥と混同せず、未実行を成功にしない。完了報告には実行コマンド・結果・CI対象SHA・残件を対応付ける。
- 修正の切り戻しは対象変更のrevertで行い、保存済み予想・receipt・結果・比較履歴を削除しない。後続PR統合後は依存を確認し、関連契約・受入・manifestを同時に整合させる。
