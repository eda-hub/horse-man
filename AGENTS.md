# Codex implementation guidance

このリポジトリで JRA-VAN Data Lab 対応のローカル競馬予想システムを実装するときは、次を優先する。

1. 競馬判断の正本は `docs/manual/`。チャット予想では `eda-hub/horse-man` を直接指定し、必ず `main` の `docs/manual/README.md` から読み、必要なOwnerモジュールだけ参照する。owner未記載を利用者への確認待ち理由にしない。
1a. 計画書、未マージPR、将来コード、Shadow検証案を現行Productionルールとして使わない。チャット予想はREADMEから辿れる現行Productionだけを使用する。
1b. 予想・snapshot・回顧の書込みは `docs/manual/00_core.md` の日次作業ブランチ `prediction/YYYY-MM-DD` 契約に従い、`main` へ直接コミットしない。
2. 現行ルール版は `docs/manual/README.md` の `現行リリース` を正とする。2026-09-13時点は `v1.6.1`。
3. 必須モジュール間で `manual_release` が一致しない場合、予想ロジック実装・予想実行・ルール編集を進めない。
4. システム設計の正本は `DECISIONS.md` と `docs/jravan/`。実装は `docs/jravan/phases/` の順に1フェーズずつ進める。
5. JRA重賞の長期記録運用は `docs/yosou/jra_racing/README.md` を正本とし、各重賞は固定パスの1ファイルで管理する。
6. 進行中のShadow検証データは `docs/validation/` を現行サイクル専用領域として扱う。ここを正式ルールの正本にしない。
7. ProductionとShadowを完全分離する。Shadow、51B、Experimentalから同一レースのProduction順位・確率・正式買い目へ逆流させない。
8. `baseline_forecast_id` を予想の同一性キーとして扱う。チャットやオッズ更新だけを理由にProduction基準予想を作り直さない。
9. PRE / DAY / FINAL はシステム上のデータ時点スナップショットであり、`docs/manual/` のOwner境界やProduction/Shadow境界を上書きする概念にしない。
10. FINAL予想、買い目候補、ユーザーの購入/見送り判断、結果、回顧は履歴として保存し、結果に合わせて遡及書換えしない。
11. 見送りレースも予想記録・仮想精算・回顧の対象から除外しない。
12. AIは予想システム本体にしない。AIにDBの直接書込権限やルールの自動昇格権限を与えない。
13. ルールの正式変更は `docs/manual/50_review.md` の検証・昇格手順を経て別PRで行う。
14. PAT・銀行口座・投票認証情報は扱わず、自動投票を実装しない。
15. バックテストでは `data_cutoff` より未来の情報を使わない。
16. DuckDBへの書込は単一プロセス/単一Writerへ集約する。
17. 外部公開を前提にしない。Web APIはMacからWindows VMへのローカルアクセスを前提にする。
18. `.agents/` と `.devcontainer/` はCodex利用基盤として保持する。
19. 各フェーズ完了時にテスト、ドキュメント更新、受入条件確認を行う。

旧Node/TypeScript CLIは廃止済みであり、互換性維持や復元を行わない。未決事項をコードで暗黙決定せず、必要なら `docs/jravan/00_project_plan.md` の未決事項へ追記する。
