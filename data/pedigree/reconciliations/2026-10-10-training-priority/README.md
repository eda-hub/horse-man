# 2026-10-10 血統調査・調教国・海外レース・過去証跡の実施記録

## 実施範囲と結果

- 調査対象は保存済み予想期間 2026-08-16〜2026-10-04。JRA159レース・全2,089頭について既存JBIS342頭と別サイト1,747頭の親子関係を**再利用**した。
- 父2,089参照、母父2,089参照から、異なる父・母父の個体ID **613頭**を同定し、馬名・登場回数を[全件台帳](all-jra-sire-damsire-inventory.json)に保存。抽出元[parts 00〜07](part-00.json)と出馬表由来の馬名ラベル[names 00〜02](names-00.json)を保持する。馬名ラベルは外部IDの独立同定証拠ではない。
- 30頭の父・母父について、競走馬としての調教所属を説明する公開資料URLと国を[調査中の出所台帳](training-country-source-review.json)へ記録した。R01対象の先頭5頭（ディープインパクト、ハーツクライ、キングカメハメハ、ロードカナロア、キズナ）は公開JBISプロフィールの調教師・栗東所属と照合済みで、既存Registryに `attribute:training_country_matches` の `VERIFIED` revisionが保存されGitから読戻せる。**5頭のsource hashは抽出項目を正規化したSHA-256であり、取得HTML原文のハッシュではない。原文保存は未完了**。その他の資料確認済み25頭は未登録、残り583頭は未検索。未検索を「検索一致ゼロ」と見なさない。
- 既に具体的な調教所属エピソードを検証していたCaro、Storm Cat、Bellamy Roadは[既存資料に基づく再評価](training-selected-ancestors-evidence.json)に記録。確認した調教国は順にFR、US、US。**Caroの18走/19走の原資料差は未解決だが、最多出走法を廃止したため国選択に使用しない**。全調教履歴が完了したとは主張しない。
- 旧535記述・626成分は[検証状態別台帳](legacy-535-claim-review.json)に全行を保管。うち父・母父の106成分は既存JRA公式原票に正確に照合し、53記述の客観項目に出所を紐づけた。その他482記述の解釈・傾向は原文/UNVERIFIEDを保持。自動昇格禁止。
- [海外4レース42登録行](foreign-42-entry-review.json)は38出走・4取消を保存。うち候補ID31行、ID未取得3行、候補サイト未収録8行。ダリズはJRA原票・JBIS・netkeiba・France Sireで生年/父母/母父を照合済み、残りの個体同定と全42行の5代血統保存は未完了。既存公式結果・過去予想を書き換えない。
- [予想保存証跡不足40件](persistence-40-audit.json)をGitHub Actions #594の実ログで個別台帳化。39件NO_INTENT、1件receipt file missing。発走前宣言を捏造・遡及追加せず、過去の適格性を変更しない。過去全Gitコミットの逐次追跡・真正な旧receiptの検索は残作業。

## 指定祖先の調査対象

[JRA父・母父613頭](all-jra-sire-damsire-inventory.json)に加えて、旧予想535記述から[明示祖先名の言及候補](designated-ancestor-mentions-review.json)を抽出した。28種類の名称表記について出典claim IDを持つ。候補は「この祖先を予想・集計のどの馬に対し何代目で使用したか」の判断を要し、本文の単なる言及は指定祖先として確定しない。Caroなどの3頭に限定して祖先調査完了としない。

## 調教国の確定方法

新規判定では`SEARCH_MATCH_PRIORITY_V1`を使用する。

1. 検索で調教所属国が1国一致したらその国を採用してその馬の国調査を終了。
2. 複数国が一致したら、出走回数でなく実際の調教所属時期が**最も直近の国**を採用。所属時点不明・同日別国の矛盾は保留。
3. 実際に検索済みで一致する国がゼロなら`TRAINING_COUNTRY_USER_INPUT_REQUIRED`を記録し、他作業終了後チャットでユーザーに質問。回答は原文・取得時刻・出所とともに専用属性に唯一Writerで保存する。

生産国、開催国、遠征先、種牡馬供用国は分類の代用にしない。既存旧方式のsnapshotは改変しない。今回の調査記録は後日確認のREPLAY専用で、過去の発走前情報・Production実績へ流用しない。

## 完了判定と継続する残件

| 項目 | 判定 | 残作業 |
| --- | --- | --- |
| JRA父・母父全件棚卸し | 完了 613/613 | なし |
| 父・母父の調教国の資料確認 | **資料URL確認30/613、Registry登録5/613（抽出項目hash）** | 5頭のHTML原文hash未取得、残り25頭のRegistry未登録、583頭未検索 |
| 指定祖先の候補抽出 | 暫定28表記 | 実際の予想使用範囲の個体同定、全必要祖先の調教国照合 |
| 既知3祖先の所属エピソード確認 | 3/3再評価 | 旧国別集計の履歴は保全 |
| 海外4レースの登録行棚卸し | 完了 42/42 | 個体同定41行と全5代血統確認、York公式原票 |
| 旧血統の客観父・母父成分 | 完了 106/106照合 | 旧記述全体の確認済み昇格は禁止 |
| 旧血統の他記述 | 482記述保留 | 派生系統・適性主張の資料と全出走母数の個別確認 |
| 過去の予想証跡 | 40/40件原因分類 | 真正な元証拠が他の旧Git版にあるか確認。時刻偽装禁止 |

**今回の完了は個別棚卸し・一部資料調査・分類の範囲のみ**。未調査の583頭を「ユーザー回答待ち」へ変えず、「Web運用機能を実装して解消した」とも扱わない。

## 変更境界と検証

PR68の計画とPR69の調査データだけを変更し、現行`docs/manual/README.md`のrelease v1.6.1、過去の予想snapshot・gate・KPI、WebUI、DBは変更しない。PR69はDraftを維持。

チェック項目は`python3 scripts/pedigree_registry.py audit`、`python3 scripts/check_pedigree_alternative.py`、`python3 scripts/check_pedigree_followup.py`、`python3 scripts/pedigree_stats.py --audit`、`python3 scripts/verify_prediction_persistence.py --audit`、`python3 -m unittest discover -s scripts -p 'test_*.py'`。過去の40件監査不足は既知のまま残す。CI successと全調査完了は同義ではない。

## R01：先頭5頭のRegistry確認（2026-10-10）

ディープインパクト、ハーツクライ、キングカメハメハ、ロードカナロア、キズナの公開JBISプロフィールを再確認し、各馬本人の調教師と栗東所属が、Registryに保存済みの国 `JP`・個体ID・抽出項目と一致することを確認した。5頭とも検索一致1国の `SEARCH_MATCH_PRIORITY_V1` で処理可能で、既存のVERIFIED factを重複登録・更新しない。参照元、抽出項目hash、既存revision ID、Git blob SHAは調査中の出所台帳に保存した。

**保存の区別**：Git上のRegistryファイルと抽出項目SHA-256の読戻しは確認済み。ただし当該hashはHTTP応答本文のSHA-256ではなく、HTML原文のbyte列は未収集。R01で当初予定した原文byte hashを使う厳格な出所保存は未達であり、5頭を「原HTML保存完了」と報告しない。raw HTML取得環境が利用可能になった段階で、同一個体・同一資料の原文を別証跡として保存・検査する。既存revisionと旧cutoffは書き換えない。その他25頭/583頭およびWebUI・DB・Productionには触れない。
