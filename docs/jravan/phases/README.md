# Implementation phases

Codexは原則として番号順に実装する。各Phaseは独立したPRにし、受入条件を満たしてから次へ進む。

- Phase 0: Foundation
- Phase 1: JV-Link ingest
- Phase 2: Data expansion
- Phase 3: Feature / Rule engine
- Phase 4: N/A（WebUIは対象外）
- Phase 5: 任意市場sidecar
- Phase 6: 公式結果・Prediction/推奨照合・回顧
- Phase 7: AI review
- Phase 8: Backtest / Rule lifecycle

各PRには「実装内容」「migration」「テスト」「既存CLIへの影響」「rollback方法」を記載する。
