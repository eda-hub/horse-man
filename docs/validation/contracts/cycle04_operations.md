# 第4サイクル検査契約と是正運用

2026-10-13の利用者指示により、次期版と有効日は未定のままとする。現行正本はmainのv1.6.1。本書・準備コード・合成試験を現行予想ルールへ読み替えない。

## 準備と開始の判定

- `python3 scripts/check_cycle04.py`：個別採否、候補集合差、合成受入の入力hash、第4の登録済み日別記録を照合する。日別未登録なら実測0/4日と表示し、開始成功としない。
- `python3 scripts/check_cycle04.py --require-active`：正式切替・版・有効日と初日への適用を要求する。現在は不合格が正しい。
- `python3 scripts/check_cycle04.py --require-active --require-complete`：正式切替に加えて4日の実測・全初回対象回顧を要求する。未実施を0件完了としない。
- `python3 scripts/run_cycle04_acceptance.py --write`：実際に全回帰を実行し、成功時だけ合成受入と対象ソースhashを保存する。版変更・性能昇格・Git保存/読戻しの代用にはならない。

第4の対象は10/17・18・24・25、東京・京都・新潟。予定144Rから未依頼のscopeを補完しない。初回対象を固定して日別JSON `docs/validation/records/cycle_04/YYYY-MM-DD.json` に記録する。schemaは `cycle04-day-v1`、第3のMarkdown台帳を流用しない。日別記録がない時点では実測・介入数・遅延・性能をnull/未測定とする。

## 新規予想の保存

1. 日次branchで、対象1R・保存path・期限・必要な推奨scopeを含む事前宣言を予想作成前にGit保存して読戻す。宣言自身の同一artifact/内容hash/保存・receipt読戻し時刻を記録する。
2. 新規予想は `docs/validation/snapshots/YYYY-MM-DD/ID.json` に保存する。本文と版/cutoff/全頭順位・確率・根拠を固定する。既存Markdownはそのまま読む。
3. `seal_prediction.py --root . --draft 草稿.json --artifact-path 本体path --fix-path docs/validation/fix-manifests/YYYY-MM-DD/ID.json --intent-ref 宣言参照.json` でFIX時のbytes hashを独立ファイルへ先に書込む。この段階で本体を書込まない。
4. 独立FIXファイルをGit保存・読戻しし、別artifactとしてhash付きreceiptを記録する。同じコマンドに `--fix-ref FIX参照.json` を加えて本体を書込む。締切後やhash不一致は拒否。異なる内容は新revisionへ保存する。
5. 本体をGit保存・読戻しし、`verify_prediction_persistence.py --date YYYY-MM-DD --snapshot-id ID --intent-id 宣言名 --task-complete --fixed-content-sha256 FIX前hash` と個別 `--completion-status` を実行する。本体/receipt/hash/個別確認/gate/適用Shadowの不足を独立表示する。
6. 保存が失敗しても本文を消さず、未試行・書込失敗・読戻し不一致・本体保存済みで個別未完了を伝える。監査成功を個別完了へ転用しない。

参照JSONは `artifact_id / artifact_path / sha256 / receipt_path / receipt_id` を持つ。receiptは同一ID・path・content_sha256、保存/receipt確認済み、発走前状態、実際の保存・読戻し・発走時刻を持つ。宣言読戻し≦FIX≦独立hash保存≦hash読戻し≦本体保存＜発走を照合する。時刻/receiptを自動生成して発走前保存を装わない。旧記録のFIX hashを事後作成して認証しない。

## 用途・入力・市場

`selection-history-v1` の既存revision chainを使う。検証用、正式仮想、実購入に加え、価格不要推奨と任意市場を別用途にする。各イベントは原文JSON/hashと同一artifact receiptを持ち、締切前・連続revision・追加選定・変更/取消の根拠を検査する。履歴内の `BUY` は当該用途の案固定イベントであり、投票実行を意味しない。実購入には別の本人確認明細が必要。用途を移すには新用途のSELECTが必要で、旧案を変えず履歴を残す。

入力JSONは `race-input-coverage-v1`、race_id・cutoff・全出走馬番号を持つ。馬体重と近5走の全頭行を記録し、状態を取得済み/不足/初出走による近走対象外に分ける。取得済みは出所・公式/代替・観測/取得/読戻し時刻を必須とし、cutoff後の入力を拒否する。代替元は公式取得できなかった理由を残す。近5走は利用可能な過去実走数に応じて最大5走、クラス・相手レベルの根拠を記録する。初古馬混合・昇級の事実は元入力から判断し、一律年齢減点を作らない。

入力不足はnullと不足頭数を残す。予想を保全して不確実性・影響を明示できるが、入力完備や正常一巡成功とは表示しない。全頭順位・勝率/連対率/3着内率・根拠を照合し、確率合計1/2/3とscope一致を要求する。入力artifactの読戻しもcutoff以前であることを確認する。

価格は未試行/取得失敗/締切打切り/取得済みと、未評価/正の期待値/取得済み期待値不足を別属性にする。未取得ならodds/期待値はnull、判断は未評価。価格不要の予想・推奨を価格欠測で見送りへ置換しない。市場は任意sidecar、能力順位を変えない。次回の実測2開催以上で再発を確認する。

## 推奨と券種・確率の検査

PR69の価格不要推奨生成・独立保存・結果照合を再利用する。推奨本体の券種生成は既存7券種、枠連を含む8券種の事象比較・欠測検査は `cycle04_operations.py` で別検査する。枠連生成/性能を実装済みとは扱わず、未比較なら理由付きMISSINGにする。

8券種は全行を比較済み/不足/非該当へ分類する。枠連は枠内事象、同枠は異なる実出走2頭を要求。馬単/三連単の順序、取消・未知馬・重複を検査する。同時確率は不足/未校正中心値/裁量縮小/実測校正を分け、未校正値から校正済み下限を宣言できない。構造検査が通っても最適性・集中上限・全損率の性能を認証しない。二頭軸・集中・配分は個別採否に従って継続検証する。

## 日別契約

日別JSONは初回/選定/最終/回顧scope、未最終理由、全初回レース行と独立KPIを持つ。Production対象は全初回、推奨対象は全最終を記録する。各KPIの対象は適格∪不適格∪保留（相互排他）、理由を全件要求する。任意市場と実購入を推奨KPIから認証しない。

適格を宣言する行には `operations` 内の宣言・FIX・本体・入力・選定履歴の参照、全出走馬番号、枠対応、8券種比較を添付する。予想/推奨の機械gateは同じレース・本文・版・発走予定へ接続する。実購入は本人確認、券明細合計と総額の一致を別artifactで要求する。Replayは前向き適格にできない。未登録・欠測は保持し、過去21Rとの差を第4の有効例へ合算しない。

## 切替・切り戻し

正式切替は未実施。版/有効日の利用者確定後、採用済み運用改修と既合意次期仕様を、全Owner・README・AGENTS・DECISIONS・保存schema/監査・テンプレート・Phase文書・契約状態へ1commitで反映して再受入する。準備コード内のv1.7.0はPR69から継承した試験候補識別子であり、確定した次期版ではない。性能改訂は別の既存昇格基準を満たす必要がある。

切替commitのrevertで全入口/Owner/機械監査を同時に戻し、新規保存済みJSONと旧履歴は削除しない。本PRの取込みだけで第4が正常開始したと説明しない。Windows/JRA-VAN接続、未追加研究、前向き実測はそれぞれ既存計画/Phaseに残す。
