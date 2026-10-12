# 21番：父・母父のEU/US地域4条件

20番固定manifestの14R・215実出走行だけを既存集計入力へ変換し、父EU/US・母父EU/USの4条件を計算。本人調教国を使用し、EUはGB/IE/FR/DE/IT、USはUS。既存定義の地域分類・選択規則・比較NON_MATCHを保持。日付とcutoff、対象4条件だけを差分用に固定した。

全4条件COMPLETE、血統coverage100%、UNKNOWN/CONFLICT/結果保留0。公式着順で勝利/2着内/3着内を集計し、同着を保持。条件は重複し得るため、4条件の件数合計を全出走母数としない。該当0の率はnullのまま。

入力・定義を内容アドレスarchiveに固定し、snapshot/入力/定義hashとRegistry依存traceを保存。20番の保存済み国選択から独立に全860分類と群別件数・率・母数を検算し、通常計算の再実行でも全群/依存trace一致。外部取得・Registry追記・旧snapshot上書き0。REPLAY_ONLY（既存snapshot契約RESEARCH_SHADOW_ONLY）、v1.6.1/Draft/PENDINGを保持。次は22番の先頭固定5条件。
