# 正式監査・研究監査・準備readerの入口（S02）

正式版はmainのv1.7.0。以下の入口を用途ごとに使う。監査成功、準備資料の整合、対象artifactの保存完了、正式KPI認証、前向き性能、Windows/JRA-VAN接続は別の判定である。

| 対象 | 読む形式・正本 | 検査・実行入口 | 意味 |
|---|---|---|---|
| 第3の終了資料 | 旧 `cycle03-day-v1` / summary、固定原文・collection | `check_cycle03.py --require-data --require-complete`、`build_cycle03_review.py --check --require-complete` | 全7日の集合・入力hash・精算整合。過去の保留を昇格しない |
| 第4の正式日別台帳 | `cycle04-day-v1`、`docs/validation/records/cycle_04/YYYY-MM-DD.json` | `check_cycle04.py`。書込は `cycle04_workflow.py` の対象日branchのみ | 初回/選定/最終/結果・回顧を同じ公式scopeで照合。開催前に空実測を作らない |
| Prediction/推奨の保存 | 独立snapshot JSON、宣言、FIX manifest、receipt、gate | 標準保存checker / recommendation audit / 個別completion | 同一artifact・時刻・内容を検査。監査だけで個別完了を与えない |
| 正式版の整合・開始 | `v170-release.json` / 全Owner・入口 | `run_release_readiness.py`、実開始は取得済みmainへ `--require-main` | 原子整合とmain開始を分離。PR69の未マージmanifestを開始へ代用しない |
| 血統・条件統計研究 | Registry、原票、revision、cutoff、REPLAY snapshot | `check-pedigree-research.yml` の17研究監査 | データ保全・原票/経路/時点・再計算を独立確認。適性効果・Production昇格ではない |
| 準備・履歴Markdown | `prediction-day-v2`、`docs/validation/records/*.md` | `check_prediction_cycle.py` | 読取検査だけ。第4JSONの標準writer/checkerとして使わない |

## workflowの接続

正式workflow `.github/workflows/check-cycle03.yml` はS01の依存是正済みbytesをそのまま保持。第3終了・第4契約・推奨・正式版の監査と全回帰を引き続き実行する。

研究workflow `.github/workflows/check-pedigree-research.yml` はPR69の旧workflowから研究17工程だけを移し、正式checker・推奨audit・台帳writer・準備readerを呼ばない。checkout全履歴とPDF依存準備を持ち、pull_request/main pushで動く。contents権限はreadのみ。Registry、国内/海外原票、調教国、指定祖先、歴史的Git証跡、11日差分と統計snapshotを検査する。工程のskip・検査簡略化・原データの追記はしない。

正式workflowの日本語のjob summaryと、研究のinventory/snapshot監査summaryを区別する。研究成功を正式Prediction/Recommendationの適格性へ流用せず、正式監査成功で研究原票/coverageを認証しない。

## 準備readerの利用

```sh
python scripts/check_prediction_cycle.py --root .
python scripts/check_prediction_cycle.py --root . --json
```

通常出力は「準備・履歴のMarkdown台帳をN件検査。第4JSON台帳の正式完了は判定していない」と表示する。監査用JSONは `preparation-history-reader-v1` で、read_only=true、official_cycle04_checked=false、formal_completion_certified=false、evidence_created=falseを必ず示す。0件で検査終了0でも、正式台帳の完了ではない。

同じ日付の準備Markdownと正式JSONを合算・二重登録しない。正式JSONはreaderの対象外であり、不正な正式JSONの検出も正式checkerで行う。readerにはwrite/register/review操作がなく、通常API `run` の件数返却と既存Markdown整合判定は保持する。不正な準備本文は終了1、未知の書込オプションは拒否する。

変更したreader/回帰のhashは既存 `build_v170_manifest.py` で再固定する。S02で正式workflow/Owner/現行schema/gate/日別writerは変えない。新規研究workflowは正式manifestの監視対象を無言で増減する手段ではない。

S02の保存・保全・CI結果は [checkpoint](handoffs/2026-10-13-s02.json) とPR68/PR69を参照。次のS03では全入口の再利用・受入とmain開始確認を改めて照合し、実測/未実測を分離する。
