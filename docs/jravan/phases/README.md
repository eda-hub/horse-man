# Implementation phases

Codexは実施対象のPhaseを番号順に実装する。Phase 4は対象外/N/Aで、非UI Phase 3→5→6→7→8へ進み、画面完成を前提にしない。各Phaseは独立したPRにし、受入条件を満たしてから次へ進む。

- Phase 0: Foundation
- Phase 1: JV-Link ingest
- Phase 2: Data expansion
- Phase 3: Feature / Rule engine
- Phase 4: Prediction Web UI（対象外/N/A・参考設計）
- Phase 5: Odds forecast / Market validation
- Phase 6: Result / Review preparation / Automation
- Phase 7: AI review
- Phase 8: Backtest / Rule lifecycle

各PRには「実装内容」「migration」「テスト」「既存CLIへの影響」「rollback方法」を記載する。


## 次期Prediction中心契約の依存順

第3検証サイクル終了後の次期契約では、manual / validation / execution gate / checkerの切替を先に整合させた後、既存Phase順を維持してコード実装する。

```text
次期契約切替
 -> Phase 3 Feature / Production / Shadow engine
 -> Phase 5 Odds forecast / Market validation
 -> Phase 6 Result / Review preparation / Automation
 -> Phase 7 AI review
 -> Phase 8 Backtest / Rule lifecycle
```

Phase 5以降を先に実装してProduction順位・印・根拠の契約を迂回しない。新規予想featureはPhase 3でShadowとして実装し、Phase 8で追加価値・非劣化・data cutoffを確認した後、別のmanual変更PRでProduction昇格を判断する。



今回のPR69準備実装・終了審査・正式切替は同じPRで管理し、審査記録と切替コミットを分ける。後続のアプリPhaseは上記の独立PR契約を維持する。WebUI対象外でも、チャット出力・保存/読戻し・監査・結果照合・履歴失効の非UI受入は維持する。
