# Implementation phases

Codexは実施対象のPhaseを番号順に実装する。各Phaseは独立したPRにし、受入条件を満たしてから次へ進む。利用者指定でPhase 4は対象外/N/Aのため、非UI Phase 3→5→6→7→8へ進み、WebUI完成を前提にしない。

- Phase 0: Foundation
- Phase 1: JV-Link ingest
- Phase 2: Data expansion
- Phase 3: Feature / Rule engine
- Phase 4: Prediction Web UI（対象外/N/A・参考設計のみ）
- Phase 5: Odds forecast / Betting decision
- Phase 6: Result / Settlement / Automation
- Phase 7: AI review
- Phase 8: Backtest / Rule lifecycle

各PRには「実装内容」「migration」「テスト」「既存CLIへの影響」「rollback方法」を記載する。



WebUIの画面受入を省略しても、保存・読戻し・監査・Prediction/Shadow分離・結果照合・履歴失効の非UI受入は維持する。現行v1.6.1の予想契約は変更せず、次期Prediction/Recommendationへの正式切替は第3サイクル終了審査後の別PRで原子的に行う。
