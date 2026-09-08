# Architecture Decision Record

JRA-VANローカル予想システムに関する確定判断を記録する。

## ADR-001 ローカル優先
Macを操作端末、Windows 11 VMをJRA-VAN/JV-Link実行環境とする。Web UIはインターネットへ公開しない。

## ADR-002 AIは補助機能
予想本体はルール、統計、特徴量、将来のMLで構成する。AIは回顧、説明、仮説生成、ルール改善候補の作成に限定する。

## ADR-003 DuckDB + Parquet
現役分析DBはDuckDB、長期アーカイブ/論理バックアップはParquetを基本とする。DuckDB書込は単一Writerに集約する。

## ADR-004 FINAL予想はImmutable
FINAL確定時点のrule version、feature version、data cutoff、利用オッズ、各馬score、買い目を後から上書きしない。

## ADR-005 SKIPは正常な意思決定
`BET` と `SKIP` を同格の最終判断として記録する。見送りでも推奨買い目を保存し、理論損益を後日計算する。

## ADR-006 全予想を回顧する
購入、見送り、的中、不的中に関係なくFINAL予想は結果確定後に回顧対象とする。

## ADR-007 オッズを3種類に分離
`observed_odds`、`predicted_final_odds`、`actual_final_odds` を別概念として保存・評価する。

## ADR-008 オッズは間引き保存
全レースの高頻度保存は行わない。全レースはFINAL、重賞はT-60/T-30/T-15/T-5/FINAL、予想対象のみ必要に応じ詳細保存する。

## ADR-009 AIルール変更は承認制
AI提案は `DRAFT -> BACKTESTED -> APPROVED/REJECTED` を経る。AIからrulesファイルや本番DBを直接更新しない。

## ADR-010 PAT非連携
買い目提案と手動購入記録までを対象とし、自動投票、PAT認証情報、銀行情報をシステムへ保存しない。

## ADR-011 バックアップは自動化
日次論理バックアップ、週次VM保護、Mac側/Time Machineへの退避を基本とし、復元テストも運用に含める。

## ADR-012 旧CLIを廃止
利用されていないNode/TypeScript CLIと関連テスト・設定は削除し、新システムをクリーンな構成で実装する。`.agents/` と `.devcontainer/` はCodex利用のため保持する。

## ADR-013 時点再現性
予想・判断には必ず `data_cutoff` と使用snapshotを紐づけ、過去時点の判断を再現できるようにする。

## ADR-014 例外を履歴化
取消、騎手変更、馬場変更、発走時刻変更、返還等は上書きではなくevent/snapshotとして履歴化する。
