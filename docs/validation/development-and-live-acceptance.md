# 開発受入と実運用評価の境界

## 最優先方針
全開発作業を完遂してPR69をmainへマージする。29番の実測はmainマージ後の実運用で取得・保存・評価し、PR69上の実測/実測完了を開発マージ条件にしない。37-05・校正・非劣化・性能・負荷も同じ境界で扱う。
計画正本はPR68のdocs/proposals/2026-10-14_pr69_remaining_implementation_plan.md。本文書は大項目01／01-04の実装受入・実運用責任の対応であり、競馬判断の正本はmainのdocs/manual。

## 状態と保存先
| 項目 | 開発受入 | 実運用評価 |
|---|---|---|
| 対象 | コード/入力契約/保存/監査/研究調査工程/旧互換 | 実依頼・公式scopeの発走前取得・固定予想/推奨・結果・比較 |
| 状態 | 未実施/実装中/実装受入/欠陥修正待ち | 未依頼/未試行/取得失敗/締切超過/取得済み/不足/継続検証/実測受入 |
| 保存先 | PR69の機能branch、docs/validation/implementation。計画更新はPR68 | mainから作るprediction/YYYY-MM-DD。既存日別台帳/intent/snapshot/receipt/結果/独立sidecar |
| Owner | 計画/実装Ownerとリリース管理 | 00_core/10_prediction/30_betting/40_shadow/50_review/60_marketの責任範囲 |
| 完了判断 | 小項目の実装/調査/関連検証/commit/readback/必要CI | 当時のscope/本文/時点/hash/receipt/Gitと対象網羅を照合。性能採用は別Owner審査 |
| 不足時 | 実装欠陥・未確定仕様は修正/確認する。原資料不足は調査結果とcoverageを保存 | 欠測/null/未確認/不適格を維持。合成/Replayを実測へ数えない |

研究PARTIALと調査工程完了を分け、歴史的保存不足40・旧KPI保留57・正式ROI nullを保持。実装受入で旧証跡を再認証しない。
性能実測待ちをコード欠陥の代わりに用いず、コード欠陥を運用実測待ちとして先送りしない。

## 既存checker・CIの照合結果
01-01基準HEAD cfdfaad5a3624fa48e26ed7ba67d8d54b365bab1と01-03までのコード不変を前提に確認した。

| 入口 | 役割・保持する条件 |
|---|---|
| check-cycle03.yml | 回帰・保存/台帳/原子的整合の開発監査。29の実測checkerをマージ条件として呼ばない |
| check-pedigree-research.yml | 原票/Registry/条件集計の監査。将来開催の取得成功を要求しない |
| check-integration-acceptance.yml | 合成受入と取得済みmain/branch開始境界。将来実測の成功を要求しない |
| run_release_readiness.py | branchの原子的整合と--require-mainの正式運用開始を分離。未マージ版の開始拒否は保持 |
| check_integration_acceptance.py | 取得済みmainの開始確認とUNMERGED_CONTRACT_REJECTEDを期待結果として扱う。実測待ちによるマージ拒否ではない |
| check_chat_market_live_validation.py | manifestを明示指定した実運用評価。2開催/8券種/2提供元・発走前Git・独立receipt・当時bytesを確認 |

上記の範囲では、実測未完了だけで開発マージを拒否するコードは見つからない。workflow/checkerの変更は不要。静的呼出し・条件照合結果であり、マージ保護設定の全項目取得や実運用実測の実施を主張しない。必要CIの実結果は小項目受入記録で追跡する。

## 29番と37-05の実運用接続
29=53-I11はmainマージ後に実依頼のscope/対象券/締切/出所を事前固定し、本文取得→分析→独立receipt→発走前Git→市場登録→実測checkerを既存方式で行う。日次成果のPR保存は認めるが、未マージPR69を実運用に代用しない。
第1/第2開催の日付は実運用の対象で決める。提供元失敗は理由付き不足とし、2提供元の成功を仮定しない。Prediction/Recommendationは価格なしで完結する。
37-05は10/17・18・24・25の実依頼全該当例、同一cutoff/全頭入力/基準・Shadow・bindingを発走前固定する。期間に間に合わない場合は不足を明示し利用者へ確認、日付を勝手に変更しない。

## マージ受入と性能採用
大項目01〜08の実装・調査・検証を完遂し、09の統合/必要CI/旧互換/契約整合でmainへマージ。大項目10〜12の実測完了を待たない。
性能採用は、実運用で対象母数・時点・校正・条件別非劣化と良好部分保全を審査した後に判断。合成CI、準備実装、平均改善、指定期間終了だけで昇格しない。
