# v1.7.0 初回・最終・回顧の標準実行テンプレート

## 開始

eda-hub/horse-manのmainからmanual READMEを取得し、同一参照commitで必要Owner・v1.7.0を確認する。`run_release_readiness.py --require-main`でmain有効化を確認する。対象開催日と実発走予定・依頼scope・既存基準を確認し、prediction/YYYY-MM-DDを再利用する。

## 初回

公式番組と依頼scopeから `cycle04-official-scope-v1` の全対象を登録する。予定192Rから勝手に補完しない。開始前に予想/推奨scopeの宣言をGit保存・読戻ししてから予想を作る。全対象馬の事実→評価→全頭確率→順位→印・根拠・確信度を固定し、初回全scopeと選定/未取得を残す。

## 最終

選定候補の既存基準・静的入力を再利用し、当日馬体重/取消/馬場等を取得試行する。候補追加・用途変更は発走前のselection-history revisionと独立receiptを保存する。重賞属性だけで対象を増やさない。

1. 宣言の読戻し後、FIX bytesと独立manifestを `seal_prediction.py` で作成する。
2. FIX manifestをGit保存・読戻してから同じbytesの本体を独立JSONへ保存する。
3. 本体とreceiptをGit保存・読戻しし、同じartifact/time/hashで個別確認する。
4. Production固定後、価格なしで `recommendation.py --prepare/--generate/--seal` の独立推奨を保存する。推奨なし/印のみ/未完了を別状態にし、購入確認や予算を入力にしない。
5. 本体、receipt、FIX hash、個別確認、gate、該当Shadowを独立検査する。全体audit成功を個別完了としない。
6. `cycle04_workflow.py --record-prediction`で日別台帳へ接続し、検査した台帳を同日branchへGit保存・読戻す。

保存/取得障害でも予想回答を発走時刻まで無限に待たせず、未完了範囲と原因を日本語で示す。結果後に宣言・買い目・時刻を生成して適格にしない。

## 回顧

公式結果を同じrace/dateと取得時刻で保存し、 `cycle04_workflow.py --review` に誤差分類・良好部分保護・次の検証を与える。初回scope全件を対象に未最終/推奨なしも回顧し、 `--summary` でPrediction/推奨/Shadow/任意市場を独立集計する。回顧完了は日別→サイクル集計のGit読戻しまで。

実購入・払戻なしでPredictionと推奨的中を評価する。0適格・未測定を0%にせず、未来値・旧☆・旧Betting・研究Replayを新KPIへ混ぜない。

## 利用者への回答

順位/印/確率/根拠/確信度、推奨または理由付き推奨なし、対象ごとの本体/個別完了/不足を日本語で示す。内部IDや工程コードをそのまま列挙しない。

## 公式結果と前向き回顧

初回のみ・最終あり・推奨なしを問わず、結果JSON単独の `OFFICIAL` 自己申告から正式KPIを計算しない。発走後に実際に取得したJRA確定本文をFORWARDで保存し、race/date/発走、公式確定引用、全頭着順・同着/取消/中止・複勝対象着数を注釈する。

`chat_result_conversion.py` で保存本文から変換/結果を再構成し、別ファイルのpath/SHA256へ固定する。最新Prediction gate/hash/原本と存在するRecommendation gate/hashを同じ `cycle04-result-reconciliation-manifest-v1` のrefsに含め、manifest自身もpath/SHA256で固定する。回顧入力は `race_id`、`result_path`、`result_reconciliation_ref` と回顧分析を必須とする。

更新時刻不明はnullで保持し、結果取得時刻を偽造しない。診断出力の `formal_kpi_certified=false` をtrueに書き換えない。出所不明・Replay/Synthetic・未来取得・本文不一致は正式回顧を未完了とし、保存済み原本を保全する。入力JSONとコマンドは `docs/validation/contracts/cycle04_operations.md` を参照。

## Shadow初回・最終の適用状態の固定

初回と最終のPrediction gateを別phaseの固定履歴として登録する。日別writer/preview用entryには各phaseの `shadow_applicability`（`status`, `reason`, `item_ids`）を必ず入れる。項目が存在する場合は `APPLICABLE` としてgateの全項目IDを一致させる。対象条件を実際に確認して非該当なら `NOT_APPLICABLE`、未確認なら `UNKNOWN`（保留）とし、単なる空の `shadow_items` だけでは非該当としない。

初回に存在した項目を最終gateから外すときは、`previous_item_dispositions` に消えたIDごとの `status` と具体的な `reason` を全件記録する。初回の原本とreceipt、固定gateのSHAと当時の比較状態は変更・削除しない。最終のShadow対象外/不足は日別最新Shadow KPIだけに反映し、独立Productionと価格不要推奨の完了判定へ流用しない。プレビューはwriterと同じ検証を通す。

回顧では `shadow_history` と `shadow_history_gaps` をphase別に読み、同一gate・baseline・cutoff・項目IDの固定比較キーで重複を除外する。初回比較と最終比較を混ぜず、未実施や証跡不明は保留/不足とする。

## サイクル終了時の追加確認

各日で初回scope・初回FIX/個別完了・選定revision・最終予想/独立推奨・公式結果・回顧を対象ごとに照合する。未選定の初回と選定済み未最終を分け、推奨なし/明示的印のみは個別保存検査が完了していれば正常として扱う。推奨PENDINGの無言置換、取得不足の0埋め、後日の宣言・receipt再生成をしない。

`cycle04_workflow.py --summary`で工程不足と独立KPIを表示する。6日全件の正常一巡は、Git保存/読戻し済みの各日・集計固定参照を与えた`check_cycle04.py --require-complete --completion-manifest ...`が成功した場合だけとする。未実施を残して終えるなら、Owner/審査者・全不足・保護対象・次試験の実際の審査記録をGit保存し、`--closure-review`で別途検査する。自己承認・性能昇格はしない。


## 保存拒否と発走時計の是正（2026-10-17、実装後の新規試行に適用）

正式レースでの発走前保存は次の順序を必須とする。未マージのPR・計画を既存本番で有効と自己申告しない。

1. 対象開催日とrace ID、公式scope、公式発走変更chain、日次branchと作業対象pathを確認する。実際のChatGPT/GitHub連携の権限と利用経路を確認する。未確認なら成功と表現しない。
2. 書込み直前・本体読戻し直後・receipt読戻し直後に、現在UTCを取得して `prediction_clock.py` / `verify_prediction_persistence.py --clock-status --date YYYY-MM-DD --clock-race-id RACE_ID` で判定する。第4運用入口は `cycle04_workflow.py --clock-status --date YYYY-MM-DD --clock-race-id RACE_ID`。JST表示、残秒、根拠、状態を返す。実時計が取れない環境では読取専用の計算値を用意できても、実測と混同せず時刻未判定とする。公式scopeと発走変更chainの読取りが終わった**後**に判定時計を新規取得する。取得前の時計を読取り後まで流用しない。時計が5秒超古い、オフセット/秒精度がない、monotonicとの乖離が2秒超、境界不明なら未判定。予定到達は実発走確認済みではない。
3. 正式intentは分析前にGit保存・固定commitから同一bytes読戻しする。FIX独立manifest→本体→receipt→個別検査の順序を守る。自己申告のreadback、ローカル保存、Actions成功だけで正式完了にしない。
4. 固定bytesとSHA-256を保持し、障害を `prediction_persistence_io.py` の拒否分類・操作記録に残す。権限/branch制約、SHA競合、通信/timeout、CI失敗、安全性拒否、理由不明を分ける。拒否された操作を別経路や高権限で迂回しない。通信系のみ、同一原本の遠隔読取り後に最大2回まで許可済みの保存を再試行する。独立した許可済み経路がなければ切替不可と明記する。
5. 実行環境にPythonと承認済みGitHub Contents API認証情報がある場合は、`python3 scripts/prediction_persistence_io.py --date YYYY-MM-DD --race-id RACE_ID --path RELATIVE_PATH --payload-file FIXED_FILE --operation-id UNIQUE_ID --write` を使用できる。同一bytesの既存原本はcommit固定で読戻し、再書込みせず存在確認済みとして扱う。固定原本と異なる内容は `--allow-update` を指定しても上書きせず、新しいrevision/pathで独立保存する。トークンや権限の自動取得・branch自動作成はしない。ChatGPTのGitHub連携利用時は同等の書込→返却commit固定読戻しを連携ツールで実行し、Pythonアダプター成功と取り違えない。
6. 失敗時は固定原本と秘匿済み障害記録を実行環境に保全し、GitHub正式保存は未完了と表示する。branch初期確認段階の拒否（HTTP 403等）でも `--local-incident` へ要求ID・応答分類・API到達状態を保存する。ローカルログ保存失敗も別途表示する。機密文字列を公開リポジトリに記録しない。事故記録の正式保存先は `docs/validation/persistence-incidents/YYYY-MM-DD/` だが、これは当時のreceiptを代替しない。旧データ・過去の証跡を遡及補完しない。

固定原本の保存前には `--race-id`、`--date`、日次branch、対象path、JSON本文のrace ID／開催日／発走予定を照合し、公式scope／発走変更chainから**当該レース**について取得した時刻判定のID・日付・予定時刻とも一致させる。11Rの原本に12Rの時計を使うこと、異なる日付・snapshot IDのパスへ固定することは不可。複数レースの一括intentは最早発走時刻と等しい公式時計を指定する。推奨の独立宣言は `docs/validation/recommendation-intents/YYYY-MM-DD/`、推奨認証は `docs/validation/recommendation-gates/YYYY-MM-DD/`、Prediction固定gateは `docs/validation/recommendation-prediction-gates/YYYY-MM-DD/` に限って新規原本保存を許可する。古い原本や同名gateを異内容上書きせず、新revision・historyによる別pathを使用する。

**ID互換・共有receiptの例外・障害記録復旧**：レースIDは `20261018-TOK-11`（TOK/KYO/NII短縮形式）と `2026-10-18-TOKYO-11`（TOKYO/KYOTO/NIIGATA長形式）を同じ開催日・場・レース番号へ正規化して照合する。第4の公式scopeに別表記で登録されている場合は登録済みの実キーを解決して公式時計を取得し、同一レースの二重登録があれば未判定として停止する。異なるレースを混用してはならない。正式推奨は共有 `docs/validation/persistence-receipts/YYYY-MM-DD.md` へ、先行するR01および他レースのreceiptを**1 byteも変更せず**R02を新規追記する。CLIは共有ファイルの既存bytesに追加レコードを末尾連結した完成版を `--payload-file` に渡し、`--append-receipt --write` を明示する。既存blob SHAと原本bytesの両方を再照合し、整合する場合だけ条件付き更新し、返却commitの読戻しを実施する。R02の `previous_receipt_ref`、artifact、内容SHA、保存/読戻し時刻を一致確認する。R01など過去の固定証跡や推奨本体JSONへの変更は引き続き禁止。 `incident_record()` で生成した障害JSONはrace ID・開催日・branchを保持し、`persistence-incidents/YYYY-MM-DD/` へ復旧後（発走後を含む）に新規保存・読戻し可能。ただし事故記録の保全は発走前保存、receipt認証、KPI適格を代替しない。

時計判定・保存成功・読戻し一致・宣言/FIX順序・個別完了・正式KPIは独立した項目として表示する。現在の時計が発走後というだけで、過去の固定commitによる発走前保存を遅延へ書換えない。実チャット/予約/再開の経路試験は合成CIと別に記録する。安全性拒否の内部理由はログ未取得につき未確定のまま扱う。
