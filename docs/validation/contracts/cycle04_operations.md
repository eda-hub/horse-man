# 第4サイクル v1.7.0 実運用契約

正式版はv1.7.0、有効化はPR79のmainマージ後。価格不要のPrediction→Recommendation→保存→結果/回顧を標準にする。開催日は10/17・18・24・25、東京・京都・新潟。開始前は実測・性能をnull/未測定とし、予定144Rを未依頼scopeへ補完しない。

## main確認と日別実行

最新mainを取得し、以下の開始確認を通す。`v170-release.json`の全対象hashがローカルと取得済みmainで同じ場合だけ開始できる。候補branchの受入成功だけでは開始しない。

```bash
python3 scripts/run_release_readiness.py --require-main
python3 scripts/check_cycle04.py --require-active
```

予想依頼時に日次branch `prediction/YYYY-MM-DD` を作り、公式出馬情報から依頼範囲を明示する。scope入力は `cycle04-official-scope-v1`、`race_date_jst`、`source_url`、`observed_at_jst`、`races`（`race_id`とJST発走予定）を持つ。登録は発走前に行い、既存日を上書きしない。

```bash
python3 scripts/cycle04_workflow.py --register-scope official-scope.json
python3 scripts/cycle04_workflow.py --date YYYY-MM-DD --record-prediction initial-entry.json
python3 scripts/cycle04_workflow.py --date YYYY-MM-DD --select selection-entry.json
python3 scripts/cycle04_workflow.py --date YYYY-MM-DD --record-prediction final-entry.json
python3 scripts/cycle04_workflow.py --date YYYY-MM-DD --review review-entry.json
python3 scripts/cycle04_workflow.py --summary
```

予想entryは`race_id`、`phase=INITIAL/FINAL`、`prediction_gate_path`、`operations`（下記の独立証跡）、`input_complete`、不足理由/影響、`market`を持つ。FINALは`recommendation_gate_path`も必須。selection entryはrace_idとselection_ref。review entryはrace_idとresult_path、review（error_classification / non_degradation / next_validation）。公式結果はOFFICIAL、同一ID/開催日、source_url、発走後retrieved_at_jst、同着をまとめたfinish_groups、place_placesを持つ。着順・non_finishers・scratched_horsesの和は固定予想の全頭と一致させ、不完全な結果を完了へ算入しない。

日別JSONは`docs/validation/records/cycle_04/YYYY-MM-DD.json`。初回・最終の独立固定参照を履歴として保持する。ローカル保存・検査後、従来どおり日次branchへGit保存し、保存先を読戻して同一bytesを確認する。CLI成功だけをGit保存完了とは説明しない。

`run_cycle04_acceptance.py --write`は合成受入を保存する。`check_cycle04.py --require-active --require-complete`は4日の実測・全初回scope回顧が揃ってからのみ成功する。

## 新規予想の保存

1. 日次branchで、対象1R・保存path・期限・必要な推奨scopeを含む事前宣言を予想作成前にGit保存して読戻す。宣言自身の同一artifact/内容hash/保存・receipt読戻し時刻を記録する。
2. 新規予想は `docs/validation/snapshots/YYYY-MM-DD/ID.json` に保存する。本文と版/cutoff/全頭順位・確率・根拠を固定する。既存Markdownはそのまま読む。
3. `seal_prediction.py --root . --draft 草稿.json --artifact-path 本体path --fix-path docs/validation/fix-manifests/YYYY-MM-DD/ID.json --intent-ref 宣言参照.json` でFIX時のbytes hashを独立ファイルへ先に書込む。この段階で本体を書込まない。
4. 独立FIXファイルをGit保存・読戻しし、別artifactとしてhash付きreceiptを記録する。同じコマンドに `--fix-ref FIX参照.json` を加えて本体を書込む。締切後やhash不一致は拒否。異なる内容は新revisionへ保存する。
5. 本体をGit保存・読戻しし、`verify_prediction_persistence.py --date YYYY-MM-DD --snapshot-id ID --intent-id 宣言名 --task-complete --fixed-content-sha256 FIX前hash` と個別 `--completion-status` を実行する。本体/receipt/hash/個別確認/gate/適用Shadowの不足を独立表示する。
6. 保存が失敗しても本文を消さず、未試行・書込失敗・読戻し不一致・本体保存済みで個別未完了を伝える。監査成功を個別完了へ転用しない。

参照JSONは `artifact_id / artifact_path / sha256 / receipt_path / receipt_id` を持つ。receiptは同一ID・path・content_sha256、保存/receipt確認済み、発走前状態、実際の保存・読戻し・発走時刻を持つ。宣言読戻し≦FIX≦独立hash保存≦hash読戻し≦本体保存＜発走を照合する。時刻/receiptを自動生成して発走前保存を装わない。旧記録のFIX hashを事後作成して認証しない。

## 用途・入力・市場

`selection-history-v1` の既存revision chainを使う。検証用、正式仮想、実購入に加え、価格不要推奨と任意市場を別用途にする。各イベントは原文JSON/hashと同一artifact receiptを持ち、締切前・連続revision・追加選定・変更/取消の根拠を検査する。履歴内の `BUY` は当該用途の案固定イベントであり、投票実行を意味しない。新規実購入はこの運用では扱わない。用途を移すには新用途のSELECTが必要で、旧案を変えず履歴を残す。

入力JSONは `race-input-coverage-v1`、race_id・cutoff・全出走馬番号を持つ。馬体重と近5走の全頭行を記録し、状態を取得済み/不足/初出走による近走対象外に分ける。取得済みは出所・公式/代替・観測/取得/読戻し時刻を必須とし、cutoff後の入力を拒否する。代替元は公式取得できなかった理由を残す。近5走は利用可能な過去実走数に応じて最大5走、クラス・相手レベルの根拠を記録する。初古馬混合・昇級の事実は元入力から判断し、一律年齢減点を作らない。

入力不足はnullと不足頭数を残す。予想を保全して不確実性・影響を明示できるが、入力完備や正常一巡成功とは表示しない。全頭順位・勝率/連対率/3着内率・根拠を照合し、確率合計1/2/3とscope一致を要求する。入力artifactの読戻しもcutoff以前であることを確認する。

価格は未試行/取得失敗/締切打切り/取得済みと、未評価/正の期待値/取得済み期待値不足を別属性にする。未取得ならodds/期待値はnull、判断は未評価。価格不要の予想・推奨を価格欠測で見送りへ置換しない。市場は任意sidecar、能力順位を変えない。次回の実測2開催以上で再発を確認する。

## 推奨と券種・確率の検査

PR69の価格不要推奨生成・独立保存・結果照合を再利用する。推奨本体の券種生成は既存7券種、枠連を含む8券種の事象比較・欠測検査は `cycle04_operations.py` で別検査する。枠連生成/性能を実装済みとは扱わず、未比較なら理由付きMISSINGにする。

8券種は全行を比較済み/不足/非該当へ分類する。枠連は枠内事象、同枠は異なる実出走2頭を要求。馬単/三連単の順序、取消・未知馬・重複を検査する。同時確率は不足/未校正中心値/裁量縮小/実測校正を分け、未校正値から校正済み下限を宣言できない。構造検査が通っても最適性・集中上限・全損率の性能を認証しない。二頭軸・集中・配分は個別採否に従って継続検証する。

## 日別契約

日別JSONは初回/選定/最終/回顧scope、未最終理由、全初回レース行と独立KPIを持つ。Production対象は全初回、推奨対象は全最終を記録する。各KPIの対象は適格∪不適格∪保留（相互排他）、理由を全件要求する。任意市場を推奨KPIから認証しない。互換用actual_purchase集合は空にする。

適格を宣言する行には `operations` 内の宣言・FIX・本体・入力・選定履歴の参照、全出走馬番号、枠対応、8券種比較を添付する。予想/推奨の機械gateは同じレース・本文・版・発走予定へ接続する。新規実購入の適格認証は拒否する。Replayは前向き適格にできない。未登録・欠測は保持し、過去21Rとの差を第4の有効例へ合算しない。

## 切替・切り戻し

利用者は次期版v1.7.0、有効化をmainマージ後と指定した。全Owner・README・AGENTS・DECISIONS・監査・テンプレート・Phase・機械契約は同一commitで切り替える。合成受入は性能昇格・実レース・Windows/JRA-VAN接続を認証しない。

切替commitのrevertで全入口/Owner/監査を同時に戻し、新規保存済みJSONと旧履歴は削除しない。新しいサイクルを未実施のまま完了と表示しない。

## 追加受入：FIX参照・発走予定・相手情報の同一性

FIX manifestには固定本体と一致する `fixed_at_jst` と、実際に先行保存・読戻しした `intent_ref` を保持する。日別operationsのintentと同一参照であることを検査し、宣言の保存先・deadline・日次branchも本体と照合する。単に同じsnapshot IDを記載した別宣言で代用しない。

各レース行の `scheduled_post_time_jst` は開催日（JST）と一致し、適格gateの実発走予定と同じ時刻であることを必須とする。別日・別時刻のreceipt/gateで認証しない。

近5走の `opponent_level` は `{status, value, source_ref, observed_at_jst}` の構造化属性にする。ACQUIREDにはcutoff以前の情報時点・出所・値が必要。MISSINGは値nullとreasonを保持し、入力充足へ含めない。近走の開催日が過去でも、その対戦相手の未来結果を現在の評価に利用しない。
