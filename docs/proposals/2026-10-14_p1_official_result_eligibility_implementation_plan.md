# P1：公式結果の適格性と標準回顧接続の修正実施計画

## 目的・対象・状態

- 作成日：2026-10-14（JST）
- 作業branch：`fix/p1-official-result-eligibility`
- 調査基準main：`b288bc1f39f61d68c6cf536608c11689575315e8`
- 状態：計画作成済み／実装未着手
- 目的：通常の回顧・日別検査・サイクル集計が、固定された公式本文と対応する結果だけを新規の前向き成績へ算入するようにする。
- 完了対象：結果の出所・本文・変換・本体・時点・実測区分の接続欠陥。結果取得サイトの自動収集や新しい性能評価モデルは対象外。

## 再現・原因・影響

`cycle04_operations.validate_official_result` は結果のstatus、race/date、HTTPS URL、発走以降の取得時刻、全頭集合を検査するが、保存本文との一致、FORWARD/REPLAY/SYNTHETICの出所区分、現在時刻より未来でないことを標準入口で要求していない。

一時fixtureで、正常な独立保存済みProductionを日別台帳に登録し、全頭結果へ `mode=SYNTHETIC` または `mode=REPLAY` を付けて `cycle04_workflow.review → summary` を実行した。両方とも回顧登録が成功し、Predictionの適格回顧1件・◎勝率1.0へ算入された。REPLAY例のsource_urlを非公式のexample.comへ変更しても通った。これは合成再現であり、実レースの成績ではない。

既存 `chat_result_reconciliation.audit_saved` は保存本文・変換・結果・固定予想を再照合するが、標準writer/validator/summaryから必須接続されていない。別入口の診断成功を正式適格性へ転用せず、同じ検査を正式算入条件へ接続する。

## 修正方針

1. 形式検査と正式結果の適格性を分離する。旧履歴や診断用Replay/Syntheticの読取を禁止せず、新規前向き成績への算入を拒否する。
2. 新規日別回顧entryに、保存したcapture/conversion/resultと固定予想・推奨への参照を持つ独立の結果照合manifestを接続する。各参照は既存の固定path/hash形式を使い、`result_ref` と同じ結果bytesを指すことを要求する。単独の「検査成功」フラグを信用しない。
3. 保存本文から変換を再構成し、race/date/発走予定・公式確定引用・全頭結果・複勝対象着数を既存照合で検査する。公式ドメインだけを真正性の証明にせず、実際に取得した本文と追跡可能な固定参照を残す。
4. captureとconversionの実測区分を保持し、正式算入はFORWARDに限定する。本体から区分を取り除いてもmanifest側で判定できる構造にする。診断結果の `formal_kpi_certified=false` をwriter側で無条件にtrueへ置換しない。
5. 結果の取得時刻を「発走予定以降、実際の検査時刻以下」に制限する。writerの検査時刻は実時刻を使い、CLIの任意未来時刻で回避できないようにする。テストは時計を明示的に固定する。
6. 結果の掲載更新時刻不明は、既存結果変換が許す範囲で不足情報として保持する。更新時刻の不明だけから本文取得時刻を捏造せず、結果用の規約を発走前入力へ流用しない。
7. 結果照合不足は結果artifactと保存済み予想を保全し、そのレースの結果/回顧を未完了または不適格として明示する。他レース・予想保存・価格不要推奨を止めない。source/ref不足を持つ既存第4記録を発見した場合も、後付け真正性で再認証しない。

## 実装対象・境界

| ファイル | 変更内容 |
|---|---|
| scripts/cycle04_operations.py | 共通の正式結果適格性検査を追加。旧形式検査とは責任を分離 |
| scripts/chat_result_reconciliation.py | 保存本文からの再照合を再利用可能にし、循環importを回避 |
| scripts/cycle04_workflow.py | review entryに固定照合参照を接続し、summaryの結果算入も同条件で検査 |
| scripts/check_cycle04.py | 直接編集台帳でもwriterと同じ結果照合を要求 |
| scripts/chat_review_package.py | 同じ結果参照・適格性・不足を引き継ぐ |
| scripts/test_cycle04_workflow.py、test_cycle04_acceptance.py、test_chat_result_reconciliation.py、test_chat_review_package.py | 正常/不正/不足/旧互換の回帰 |
| docs/validation/contracts/cycle04_operations.md、templates/chatgpt_prediction_task.md | 実際に実行できる結果保存・参照組立・回顧手順を追記 |

共通検査の配置はimport依存を確認して決める。writerをimportする診断moduleをそのまま逆importして循環を作らない。新規参照項目のschema/契約は明示し、全fixtureを同じ契約へ更新する。過去本文や既存結果を合成の真正原票へ置換しない。

## 小項目別の実装・コミット計画

| 小項目 | 作業と完了条件 | 日本語コミット案 |
|---|---|---|
| 01 | 上記の合成・再演・非公式出所・未来取得の受入漏れを一時fixtureの回帰テストにし、現行で失敗することを確認 | 公式結果の適格性抜けを回帰テストで再現 |
| 02 | 固定照合manifestと共通正式結果validatorを実装。本文/変換/結果の一致・区分・時点・identityを検査 | 固定公式本文に基づく結果適格性検査を追加 |
| 03 | review/validate_day/summaryへ接続。直接編集・区分削除・参照差替えの回避を拒否し、不足時の保存保全を確認 | 標準回顧と集計を公式結果照合へ接続 |
| 04 | 回顧資料・テンプレート・契約・関連fixtureを更新し、旧履歴と未最終/推奨なしを維持 | 結果照合の運用手順と不足表示を整備 |
| 05 | 全受入・manifest・統合検証・CIを実施し、要件対応を本書へ記録 | 結果適格性修正の統合受入とリリース整合を固定 |

## 受入条件

- 正常なFORWARD公式本文、確認済み注釈、固定結果、同一予想/推奨が一致すれば、初回のみ・最終あり・推奨なしのいずれも結果/回顧を保存できる。
- 合成・再演・区分不明、本文未接続、別レース/別日/別発走、別予想、hash不一致、未来取得、未確定、全頭不足は正式成績へ算入されない。
- 単独resultのmode削除、statusのOFFICIAL自己申告、別URLへの変更だけで適格化できない。
- 同着・取消・競走中止・複勝対象着数は既存の結果変換と券照合を保全する。未知の表示形式は理由付き不足のままにする。
- read_only診断、旧履歴、任意市場、保存済みProduction/Recommendationのbytesと独立KPIを変更しない。
- writer・日別validator・summary・回顧資料の同一ケース判定が一致する。チェック失敗時に旧台帳を中途半端に書換えない。

## 検証・実装結果の記録

関連テストから開始し、全回帰と通常checkerへ広げる。少なくとも `test_cycle04_workflow`、`test_cycle04_acceptance`、`test_chat_result_conversion`、`test_chat_result_reconciliation`、`test_chat_review_package` と旧予想/推奨の回帰を実施する。全回帰は `python3 -m unittest discover -s scripts -p 'test_*.py'`。受入更新・release整合・統合受入は共通規約に従う。

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
