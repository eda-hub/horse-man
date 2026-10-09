# PR68 §11.7 血統確認・成績集計の受入対応

**区別する完了段階**: 過去候補の整理・Git血統調査基盤・合成fixtureによる集計処理の検証は、実データの原出所確認/公式全出走母数の取得/正式統計採用とは異なる。PR69の既存manualとPrediction KPIは変更しない。

| §11.7 | 要件 | PR69の実装・検証 | 状態 |
|---|---|---|---|
| 1 | 血統候補の状態・出所・未確認件数 | `pedigree_stats.py --inventory`：既存migrationの元ファイル・commit・成分分類・未確認数、現行Registryの同定・事実確認数を出力。未確認を自動昇格させない | 棚卸し機能実装、元外部出所の実検証は未完了 |
| 2 | 全出走母数・勝/連対/3着数と率 | 結果確定済み全出走からrace×horseを計数。`test_01`の同着例で分母・率を検証 | テスト入力で完了、実データ照合待ち |
| 3 | 入力重複・同馬別レース・共通祖先重複 | 重複行は同一内容のみ除去、矛盾重複拒否、出走IDで計数。`test_02/03/13/15` | テスト入力で完了 |
| 4 | UNKNOWN/CONFLICTを非該当に混ぜない | MATCH/NON_MATCH/UNKNOWN/CONFLICTと理由別不足/coverage。`test_04` | テスト入力で完了 |
| 5 | 米国型/欧州型と調教履歴確認・ユーザー照会 | 対象HORSE/SIRE/DAM_SIRE/ANCESTORの本人の確認済み調教国だけ使用。`test_05/06/18/20`。未確認・多地域の理由を表示 | 安全な保留と判定は実装、ユーザー問合せ回答ログ/外部検証は未実装 |
| 6 | 同着・取消・中止・失格・未確定・訂正・分母0 | 版付き整数着順ルールを明示し`test_01/09/11/12`で確認 | テスト実装済。provider固有の降着/除外規則の正式対応は未確定 |
| 7 | cutoffとFORWARD/REPLAY | 結果観測/出走観測/Registry同定・血統・分類時点を検査。`test_07/08/16/21`。全出力は研究Shadow限定 | テスト実装済。実運用FORWARD接続は未実装 |
| 8 | 同一入力冪等・旧snapshot保持 | input/definition原本archive・digest識別・原子保存・読戻し・改変監査。`test_09/14/21` | テスト実装済 |
| 9 | 差分再計算・不要な外部再取得禁止 | `--previous`で前snapshotの登録済みrevision依存hashが同じ馬の派生を再利用。`test_19/20`。外部API照会なし | Git JSON機構実装済。DB/大規模ジョブ連携は後続 |
| 10 | 保存失敗・不足・再開 | atomically archived inputs / readback, partial+missing/coverage, verify/audit。Snapshot 0件でも集計完了と誤認しない | Git JSON準備実装。実DB障害/再開ジョブは後続 |
| 11 | 公式実データ母数の照合 | 全出走宣言と出所hash必須。スコープ未完了はPARTIAL | 未完了：Phase 2の公式出走/結果原票の取得・照合作業が必要 |
| 12 | 重賞固有Shadow隔離・Prediction非干渉 | `production_eligible=false` と `usage=RESEARCH_SHADOW_ONLY` 固定。既存manual/checker/既存記録を不変更 | 構造上隔離。Phase 8での性能評価・Production昇格は未実装 |

## 現時点の段階判定

- **既存候補整理**: PR69のmigration（旧記述は未確認）を棚卸すCLI・出所hash参照を実装。原出所を検証して確認済みにする作業は未完了。
- **集計処理**: 条件限定のJSON計算と固定snapshot・監査・差分再計算を実装し、合成fixtureで検証済み。
- **実データ照合**: 公式レース別の全出走馬・結果manifestが未提供のため未完了。「本物の血統別勝率が計算できた」とは報告しない。
- **画面UI**: Phase 4未実装。出力JSONの母数/coverage/出所/保留理由を表示する画面は後続。
- **予想採用**: Phase 8と別PRの承認まで禁止。オッズ、実購入、回収率は統計計算の必須入力にしない。

テスト: `python3 -m unittest discover -s scripts -p 'test_*.py'`。監査: `python3 scripts/pedigree_stats.py --inventory` および `--audit`。最新実行結果はPR69のChecksを参照。GitHub Actionsの成功は**保存済み実データが存在する証明ではない**。

未決項目：集計対象期間・取得元（JRA-VAN契約/APIと全出走母数）・分類対象国と複数地域履歴の確定規則・provider固有の同着/降着/取消・サンプル数下限・Phase 2のDB移行/唯一Writer・実データShadow照合・Phase 4表示・Phase 8効果検証。根拠なしで数値・モデルは補完しない。
