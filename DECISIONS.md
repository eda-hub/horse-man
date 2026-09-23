# Architecture Decision Record

JRA-VANローカル予想システムに関する確定判断を記録する。

## ADR-001 ローカル優先
Macを操作端末、Windows 11 VMをJRA-VAN/JV-Link実行環境とする。Web UIはインターネットへ公開しない。

## ADR-002 AIは補助機能
予想本体はルール、統計、特徴量、将来のMLで構成する。AIは回顧、説明、仮説生成、ルール改善候補の作成に限定する。

## ADR-003 DuckDB + Parquet
現役分析DBはDuckDB、長期アーカイブ/論理バックアップはParquetを基本とする。DuckDB書込は単一Writerに集約する。

## ADR-004 FINAL予想はImmutable
FINAL確定時点のmanual release、module hashes、feature version、data cutoff、利用オッズ、各馬評価、買い目候補を後から結果に合わせて上書きしない。

## ADR-005 SKIPは正常な意思決定
`BET` と `SKIP` を同格の最終判断として記録する。見送りでも推奨買い目を保存し、理論損益を後日計算する。

## ADR-006 全予想を回顧する
購入、見送り、的中、不的中に関係なくFINAL予想は結果確定後に回顧対象とする。

## ADR-007 オッズを3種類に分離
`observed_odds`、`predicted_final_odds`、`actual_final_odds` を別概念として保存・評価する。

## ADR-008 オッズは間引き保存
全レースの高頻度保存は行わない。全レースはFINAL、重賞はT-60/T-30/T-15/T-5/FINAL、予想対象のみ必要に応じ詳細保存する。

## ADR-009 AIルール変更は承認制
AI提案は検証・人間承認を経る。AIから `docs/manual/` や本番DBを直接変更しない。正式なルール変更は `docs/manual/50_review.md` の手順に従い別PRで行う。

## ADR-010 PAT非連携
買い目提案と手動購入記録までを対象とし、自動投票、PAT認証情報、銀行情報をシステムへ保存しない。

## ADR-011 バックアップは自動化
日次論理バックアップ、週次VM保護、Mac側/Time Machineへの退避を基本とし、復元テストも運用に含める。

## ADR-012 旧CLIを廃止
利用されていないNode/TypeScript CLIと関連テスト・設定は削除済み。`.agents/` と `.devcontainer/` はCodex利用のため保持する。

## ADR-013 時点再現性
予想・判断には必ず `data_cutoff` と使用snapshotを紐づけ、過去時点の判断を再現できるようにする。

## ADR-014 例外を履歴化
取消、騎手変更、馬場変更、発走時刻変更、返還等は上書きではなくevent/snapshotとして履歴化する。

## ADR-015 ルール正本はdocs/manual
単一のルール原本ファイルや別の `rules/` ディレクトリを正本にしない。`docs/manual/README.md` をmanifest、各Ownerモジュールを定義の正本とする。実装用の構造化表現を生成する場合もderived artifactとして扱う。

## ADR-016 Production / Shadow完全分離
Production基準予想を固定してからShadow比較を作る。Shadow、51B、Experimentalは同一レースのProduction順位・確率・正式買い目を上書きしない。価格観測・予測も能力順位へ逆流させない。

## ADR-017 baseline_forecast_idを同一性キーにする
チャットやオッズ更新だけを理由にProduction基準予想を再作成しない。正式な非価格情報更新条件を満たす場合だけルール契約に従って新しい基準予想を発行する。

## ADR-018 Git上の競馬記録領域を尊重する
JRA重賞の長期記録は `docs/yosou/jra_racing/`、進行中Shadow検証は `docs/validation/` の現行運用を尊重する。将来DBへ構造化する際も、明示的な移行決定まではこれらを勝手に置換しない。

## ADR-019 当日馬体重は発表Eventで捕捉する
当日馬体重はFINAL直前のWeb取得に依存せず、開催中の `JVWatchEvent` で `JVEvtWeight` を監視し、発表event受信時に `JVRTOpen(0B11, event key)` で取得・永続化する。Event取り逃し・Core Service再起動に備えて `0B11` のrace/day catch-upと未取得時のみの低頻度pollingを併設する。T-20は馬体重の取得開始時刻ではなく、保存済み当日WHと現在の出走構成のcoverageを検証する時刻とする。T-20より前に取得した完全な当日公式WHを、取得時刻だけを理由にSTALE扱いしない。


## ADR-020 予想実行の正式性は機械ゲートで確定する
チャットAI、Codex、その他の生成系は予想・買い目・回顧の準拠可否を自己申告しない。各race executionは `docs/validation/execution-gates/YYYY-MM-DD/<race_id>.json` に機械可読状態を持ち、`scripts/check_prediction_compliance.py` が現行manual release、日次branch、発走前証跡、receipt、KPI適格性、買い目構造、Replay境界、回顧必須項目を決定的に検査する。checker不合格の出力はチャットに表示されても正式Production/Betting/Shadow KPI/サイクル集計へ登録しない。日別cycle ledgerとの対応もCIで照合し、execution gate省略を成功扱いにしない。


## ADR-021 買い目数値根拠とreceiptは発走前構造化証跡で確定する
非◎縦目の例外理由はallowlist方式とし、現行は `INDEPENDENT_POSITIVE_EV` のみを許可する。価格・保守側成立確率・EVはgate JSON内の相互整合だけでは正式監査済みとせず、発走前に保存した `betting-evidence-v1` と完全一致させる。証跡artifact自身のreceiptは `persistence-receipt-v1` の独立レコードとして保存し、同じ `receipt_id` レコード内のartifact ID/path、保存状態、`PRE_RACE_ELIGIBLE`、保存確認時刻と発走予定時刻をcheckerが照合する。発走後Replayで新規算出した価格・確率は前向き数値証跡へ昇格させない。
