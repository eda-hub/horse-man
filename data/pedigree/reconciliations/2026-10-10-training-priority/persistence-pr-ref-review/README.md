# R07再開：PR参照に残る削除branch・中間commitの保存証跡

開始HEAD `b29454a04dc2dcf06ab7c162bea7a97bf711913b`。同じPR69のbranchで前回の現存8branch・60中間commitの証跡を保持し、PR参照を使う追加探索を実施した。

GitHubの全75件のPR一覧（1ページ100件未満）から、2026-09-25 00:00 UTC以上・2026-10-05 00:00 UTC未満に作成された22件（PR46〜67）を選定。各PRのHEAD、PR commit履歴の全ページ、閉鎖21PRのmerge commitを取得した。232個のPR commitと21merge commit、計253個の独立commitを照合。前回の実ツリー探索に含まれなかった192commitも含む。

各commitのroot treeと完全なdocs treeを保存し、220種類のdocs treeの全ディレクトリについてGit tree SHAを再計算した。宣言・receiptの59種類のblob原文（60のpath/blob組合せ）もGit blob SHAで検査した。宣言ディレクトリの日付、schema、作業branch、レース範囲の形式、deadline、failed-attemptsを確認し、receiptは文字列の部分一致ではなく既存parserのartifact ID完全一致で候補化した。

| 対象40件の状態 | 件数 | 判定 |
|---|---:|---|
| 対応宣言なし | 38 | 不適格・保留。receipt候補があっても事前宣言の代用にはしない |
| 対応宣言の形式不足 | 1 | 10/4朝の旧形式。failed-attemptsへの移動も元のpayload/hashを保持。事前宣言へ変換しない |
| 有効形式の宣言あり・receiptなし | 1 | 10/3朝のmorning-v2。今回の全探索でも対応receiptなし |
| 適格性回復 | 0 | 全40件は未解決のまま |

28件に対応するreceipt候補を保存した。これらは元々Gitにある本文であり、新しいreceiptを作成したものではない。artifact・hash・発走前保存/読戻し・事前宣言を組み合わせた完全認証を意味しない。Git commit時刻がdeadlineより前でも、receiptの発走前読戻し時刻を補完しない。当時の予想・snapshot・receipt・正式KPIを変更しない。

`git-evidence.json.gz` はPR一覧・各PR commit APIページ・merge commit・完全なGit tree・候補本文。`checks.json` は40対象の元の不足理由・宣言/receipt候補・最初に観測できたcommitと時刻・不適格判定。`progress.json` は探索範囲と固定archive hash。`python3 scripts/check_historical_pr_refs.py` で全範囲を再計算し、CIでも監査する。

利用可能なGitHub branchと対象期間PR参照を通じた追加探索は実施済み。PRのない削除branch、GitHub APIから参照できないcommit、ローカルreflog、Git外の真正な保存証跡は取得できていない。もし真正な当時の証跡が別にある場合は、元commit SHA/リポジトリ、改変していない宣言・snapshot・receipt、当時の保存/読戻し時刻が必要になる。存在を推測せず、全40件の不適格・保留を維持する。R07の調査実施と40件の不足解消は区別する。
