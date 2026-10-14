# 最新：利用者指定による調教国2頭の解消（2026-10-11）

Sakhee（1997、ブライトライトの母父）は英国GB、Starspangledbanner（2006、プリサイスの父）は豪州AUとして、利用者の回答原文・受領時刻2026-10-11 02:06:52 JST・hash付きUSER_PROVIDEDを追記。元の複数国所属原票と旧cutoff・14snapshotを保持し、国待ち0。詳細はexplicit-country-reply.jsonとprogress.jsonのuser_resolution。

新時点の海外2snapshotを追加し、全16snapshotを監査。公式結果3レース30出走・43条件はCOMPLETE、UNKNOWN/CONFLICTは0。Yorkを含む4レース版は国欠測0だがBHA未確認8頭のためPARTIAL。結果・取消・母数は変更しない。以下は前回の受入履歴。

# R08：血統・成績集計の受入再照合

開始HEAD `6ad3dab9e32dc3ffbc090b741fd4a675300101c3`、同じPR69の作業ブランチで再開した。前回手元に作成済みだった39構造条件・海外43条件の8snapshot、原票、本人調教国20頭の追加調査を引き継ぎ、当時の時点・hashを保持して保存する。現在のリモート19個体の全記録を照合し、既存revision・同定履歴をそのまま保持した追記であることを確認した。

| 受入項目 | 結果 | 範囲・残件 |
|---|---|---|
| 国内対象・実出走母数 | 照合済み | 159レース・2,182登録行・2,177実出走・2,089固有馬。6期間が重複なく全対象を覆う |
| 国内39構造条件 | COMPLETE | 指定祖先21・父直系6・母父直系6・クロス6。UNKNOWN/CONFLICTは0 |
| 取消・除外・中止・同着 | 照合済み | 取消1・除外4は出走分母から除外、中止6は出走分母に残す。10/4の3着同着により24レースの3着内頭数は73 |
| 海外本人・結果対応 | 照合済み | 42登録行の個体IDと原結果行を一対一対応。取消4を保持 |
| 海外43条件 | PARTIAL | 39構造条件＋父/母父EU・USの4条件。公式JRA結果3レース30出走のみ成績分母に採用 |
| 海外追加父/母父調教国 | 18確認・2保留 | 前回17確認を保持。CommissionerはIFHA公式2014本人行のTrained列USAで確認。SakheeとStarspangledbannerは最新所属日不足 |
| York公式結果 | 未取得 | BHA公開APIの再取得も403。8頭PENDING、成績分母に算入しない。原応答とhashを保存 |
| cutoff・分類版・出所 | 照合済み | SEARCH_MATCH_PRIORITY_V1、欧州GB/IE/FR/DE/IT・米国US。本人の確認済み所属を使い、生産・供用・開催国で補完しない |
| 旧snapshot・冪等・履歴 | 保持・照合済み | 既存4＋前回追加8＋今回更新2の全14snapshot。今回Commissionerの再保存追加0、旧cutoffは未確認を維持 |
| REPLAY/SHADOW | REPLAY研究専用 | 本集計は遡及研究であり、SHADOW前向き実績・Production入力・正式採用へ昇格しない |

直系は5代内の父経路S/SS/SSS/SSSS/SSSSSと母父経路DS/DSS/DSSS/DSSSSで指定個体の独立IDが一致する条件。広い系統名の分類とは別条件。クロスは同じ独立IDが5代内の2位置以上であり、特定の3×4等とは区別する。選定理由・原文参照は前回のstructural-condition-selection.jsonに固定する。

今回追加の海外2snapshotはCommissioner確認後の新cutoffで別定義として保存。成績母数と結果は変更せず、国UNKNOWNの条件×登録行の延べ件数が各snapshotで6から4へ減少した。これを不明馬6頭から4頭とは解釈しない。旧snapshotはそのまま保管する。

`python3 scripts/check_r08_acceptance.py` は原国資料・本人名/生年・Trained列、revision追記・旧cutoff、全42行対応、全159レース範囲、固定snapshot hash、母数、BHA失敗原応答を再照合する。`python3 scripts/pedigree_stats.py --audit` は全14snapshotを原入力・固定定義・Registryの当時cutoffから再計算する。直系と祖先内包の混同、出生国の流用、複数国の最新日不足、異なる本人生年、cutoffの遡及、未確認結果の分母混入を回帰検証する。

最新結果はprogress.json、Commissionerの原票対応はcommissioner-review.json、BHA再取得はbha-retry.jsonとbha-retry-response.json.gz。調教国2頭の採用国または日付付き所属資料、Yorkの真正なBHA全出走結果が得られるまで該当部分はPARTIALを維持する。未選定条件、5代を超える系統・クロス、統計的優位性、前向きアプリ接続はこの受入範囲に含めない。
