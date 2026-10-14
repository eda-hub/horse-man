# 追加の血統条件・海外調教国・結果照合

選定39構造条件（指定祖先21、父直系6、母父直系6、クロス6）を固定定義で追加した。対象馬から5代までの独立IDの経路一致を用い、曖昧な系統名を自動分類しない。クロスは同一IDが2位置以上という明示条件であり、特定の3×4等とは区別する。定義根拠・選定範囲はstructural-condition-selection.json。

JRA159レース・2,182登録行・2,177実出走を6期間に分割して39条件を固定集計した。全期間COMPLETE、構造条件UNKNOWN/CONFLICTは0。旧4snapshotは不変更。新6snapshotは各期間の統計であり、同馬が複数期間に出走するためhorses欄を足して固有頭数としない。

海外42登録行の父・母父63個体は既存43個体を再利用し、追加20個体を調査した。17個体の単一調教国を確認、複数国2個体は所属日未確定、Commissionerは本人調教国未確認。19個体に出所付き属性を追記し、旧revision・旧cutoffを保持した。国の採用方式はSEARCH_MATCH_PRIORITY_V1。生産国・開催国・供用国・調教師の経歴から本人国を推測しない。

公式JRA結果の海外3レース33登録・30実出走は、構造39条件と父/母父EU/US4条件を保存した。構造条件にUNKNOWN/CONFLICTはないが、国不足があるためsnapshot全体はPARTIAL。海外4レース42登録・4取消の別snapshotではYork8頭をPENDINGとし、成績分母に含めない。BHA公開結果APIの再取得は403で結果表を得られず、取得停止状態と応答hashを保存した。JRA3レースの実出走30頭のみが両snapshotの成績分母である。

確認待ち: Sakhee（1997、GB/AEで直近所属日不明）、Starspangledbanner（2006、AU/IEで直近所属日不明）、Commissioner（2011、本人調教国未確認）。対象役割は父/母父。利用者指定を受けるまでUNKNOWNを保持する。

country-reviews.jsonと原票archive、foreign-runner-bindings.json、statistics-progress.jsonが各受入証跡。scripts/check_r08_acceptance.pyは本人名/生年/調教師所属国/IFHAのTrained列、追記履歴、原結果への42行対応、固定snapshotのhash、JRA159レースの重複なし範囲と件数、York除外を照合する。scripts/pedigree_stats.py --auditは旧4＋新8snapshotを再計算する。

すべてREPLAY研究専用。旧535記述全体、未選定条件、統計的優位性、Production採用、FORWARDアプリ接続の完了ではない。

2026-10-11再開追記: この節は前回の固定時点での調査結果。Commissionerは既存IFHA公式2014本人行のTrained列USAを追加照合し、新cutoffで確認済み。最新は ../2026-10-11-r08-acceptance/README.md とprogress.jsonを参照する。旧UNKNOWNと固定snapshotは保持。
