# PR69 血統実データ照合（2026-10-09）

## 結果と対象期間

予想対象期間は **2026-08-16〜2026-10-04**。保存済みの予想・回顧ノートの期間を対象とし、期間を将来開催や旧年の全開催へ拡張しない。期間開始は海外のジャックルマロワ賞記録、終了は10月4日の日次snapshotによる。過年度馬・種牡馬の資料は、この期間の予想根拠で参照されていた血統の確認資料として扱う。

PR69の旧記述から抽出済みの**父・母父53頭106項目**をJRAの個体原票と照合した。**完全一致103項目、表記差一致3項目、親子関係の不一致0項目、取得不能0頭**。個体ID・生年月日・性別・母名も併記し、馬名だけの照合にしない。

過去ノートが参照する**JBIS52血統表・各5代62位置、計3,224位置**を取得した。基本情報ページの父・父父・父母・母・母父・母母の6関係とも一致し、共有される**1,774の独立した親子関係に競合0件**。祖先・参照対象を含む**1,430個体**をRegistryの唯一Writerで保存し、共通祖先を個体IDで再利用できるようにした。52件には予想対象馬に加えてCaro、Storm Cat、Bellamy Roadなど根拠の祖先馬も含む。52出走・52レースという意味ではない。

これは外部原票による血統事実の照合であり、全出走馬と公式結果に基づく期間全体の血統別勝率計算ではない。血統の一致を、適性・予測効果・条件別成績の検証成功へ読み替えない。

## 時点と保存

- `mode=REPLAY`、`production_eligible=false`。外部資料は2026-10-09に取得・確認した。過去発走前の既知情報として遡及登録しない。
- 旧予想・回顧本文と`migration.json`の535候補は変更せず、元commit・行・claim IDに対する照合sidecarを追加した。535候補全体を確認済みへ一括昇格しない。
- JBISはHTTP原票のSHA-256、JRAは抽出プロフィールのcanonical SHA-256を記録。後者をHTML全体のhashと称さない。URL・取得方法・取得時刻・外部個体IDを保持する。
- Registryの初期同定・保存時刻はWriterが実際に保存した時刻。10月4日以前のcutoffでは今回の新規個体・事実をVERIFIEDとして返さないことを検査した。
- source事実の確認者はCodex。人間による独立確認やJRA-VAN認証済みデータ取得を実施したとは記録しない。原票照合・62位置の整合・共通親子関係の整合を確認して登録した。
- mainへのマージ・現行manual変更・Production/推奨への採用は行わない。

## 表記差3項目

| 対象馬 | 項目 | 旧記述 | JRA原票 | 判定 |
|---|---|---|---|---|
| オミゴト | 母父 | アルデバランⅡ | アルデバラン2 | 同一名称の数字表記差 |
| ドンタククイーン | 父 | Highland Reel | ハイランドリール | 英語名・カナ名の対応 |
| リリーリリー | 母父 | ミッキーアイル | Mikki Isle | カナ名・英語名の対応 |

これらは照合時の明示対応として保存し、馬名の一般的な自動同定・別名統合規則へ拡張しない。

## JRA個体原票との照合一覧

父・母父の照合元は`docs/validation/snapshots/2026-10-04.md`の4新馬戦表。106項目の個別結果と元行は`matches.json`、原票から抽出した母・生年月日・性別・調教師・産地は`jra_profiles.json`に保持する。

| 対象馬 | JRA個体ID | 父（原票） | 母父（原票） | 出典 |
|---|---|---|---|---|
| アスクハイタッチ | 2024102223 | サートゥルナーリア | Forestry | [JRA](https://www.jra.go.jp/JRADB/accessU.html?CNAME=pw01dud102024102223%2F8E) |
| アストロカノン | 2024102760 | アルクトス | フォーティナイナーズサン | [JRA](https://www.jra.go.jp/JRADB/accessU.html?CNAME=pw01dud002024102760%2F83) |
| アップルペアー | 2024107251 | スマートファルコン | タイムパラドックス | [JRA](https://www.jra.go.jp/JRADB/accessU.html?CNAME=pw01dud102024107251%2F83) |
| アマリス | 2024101482 | アジアエクスプレス | ディープインパクト | [JRA](https://www.jra.go.jp/JRADB/accessU.html?CNAME=pw01dud102024101482%2FEE) |
| アルヴィットーリア | 2024101248 | アルクトス | ディープブリランテ | [JRA](https://www.jra.go.jp/JRADB/accessU.html?CNAME=pw01dud002024101248%2F17) |
| アンバーライト | 2024104135 | エイシンフラッシュ | Danehill Dancer | [JRA](https://www.jra.go.jp/JRADB/accessU.html?CNAME=pw01dud002024104135%2F4A) |
| インユアスカイ | 2024103353 | ドレフォン | エピファネイア | [JRA](https://www.jra.go.jp/JRADB/accessU.html?CNAME=pw01dud002024103353%2FF7) |
| ウィレマイト | 2024106317 | マインドユアビスケッツ | ダイワメジャー | [JRA](https://www.jra.go.jp/JRADB/accessU.html?CNAME=pw01dud002024106317%2F50) |
| エコロゴッド | 2024107322 | American Pharoah | Munnings | [JRA](https://www.jra.go.jp/JRADB/accessU.html?CNAME=pw01dud102024107322%2FF7) |
| エリーマイラヴ | 2024108341 | Army Mule | Sky Kingdom | [JRA](https://www.jra.go.jp/JRADB/accessU.html?CNAME=pw01dud102024108341%2F93) |
| オミゴト | 2024105657 | ロジャーバローズ | アルデバラン2 | [JRA](https://www.jra.go.jp/JRADB/accessU.html?CNAME=pw01dud102024105657%2F1B) |
| オーケーグラン | 2024102824 | マインドユアビスケッツ | フジキセキ | [JRA](https://www.jra.go.jp/JRADB/accessU.html?CNAME=pw01dud002024102824%2F40) |
| オージーブラック | 2024101134 | シャンハイボビー | スペシャルウィーク | [JRA](https://www.jra.go.jp/JRADB/accessU.html?CNAME=pw01dud002024101134%2F0A) |
| ギニー | 2024102946 | チュウワウィザード | ゴールドアリュール | [JRA](https://www.jra.go.jp/JRADB/accessU.html?CNAME=pw01dud102024102946%2F5E) |
| クラウンソクラテス | 2024100299 | ルーラーシップ | モーリス | [JRA](https://sp.jra.jp/JRADB/accessU.html?CNAME=sj01ude002024100299%2F60) |
| コールドアズアイス | 2024102162 | サンダースノー | アドマイヤムーン | [JRA](https://www.jra.go.jp/JRADB/accessU.html?CNAME=pw01dud002024102162%2F43) |
| コールレスポンス | 2024106796 | ミッキーアイル | ダンカーク | [JRA](https://www.jra.go.jp/JRADB/accessU.html?CNAME=pw01dud002024106796%2F21) |
| ゴールドパーティー | 2024103682 | ゴールドアクター | フジキセキ | [JRA](https://www.jra.go.jp/JRADB/accessU.html?CNAME=pw01dud002024103682%2F47) |
| サラサハヤブサ | 2024104345 | シニスターミニスター | Medaglia d'Oro | [JRA](https://www.jra.go.jp/JRADB/accessU.html?CNAME=pw01dud002024104345%2FBC) |
| サンデー | 2024102192 | モーリス | アドマイヤムーン | [JRA](https://www.jra.go.jp/JRADB/accessU.html?CNAME=pw01dud002024102192%2F73) |
| ザキノシュガー | 2024103519 | エフフォーリア | Indygo Shiner | [JRA](https://www.jra.go.jp/JRADB/accessU.html?CNAME=pw01dud002024103519%2FCB) |
| シドニーハーバー | 2024100645 | タワーオブロンドン | オルフェーヴル | [JRA](https://www.jra.go.jp/JRADB/accessU.html?CNAME=pw01dud002024100645%2F93) |
| シュテルンライト | 2024102827 | レイデオロ | ハービンジャー | [JRA](https://www.jra.go.jp/JRADB/accessU.html?CNAME=pw01dud102024102827%2F80) |
| シンボリサーブル | 2024102327 | マジェスティックウォリアー | サクラバクシンオー | [JRA](https://www.jra.go.jp/JRADB/accessU.html?CNAME=pw01dud102024102327%2F8B) |
| ジュンキング | 2024106382 | キタサンブラック | Noble Mission | [JRA](https://www.jra.go.jp/JRADB/accessU.html?CNAME=pw01dud002024106382%2F81) |
| ジワールドコア | 2024103199 | オルフェーヴル | Mr. Greeley | [JRA](https://www.jra.go.jp/JRADB/accessU.html?CNAME=pw01dud002024103199%2F87) |
| ジーティーカグラ | 2024102550 | ルヴァンスレーヴ | ゴールドアリュール | [JRA](https://www.jra.go.jp/JRADB/accessU.html?CNAME=pw01dud002024102550%2F11) |
| スリーオブスペイズ | 2024108284 | Tacitus | Despite the Odds | [JRA](https://www.jra.go.jp/JRADB/accessU.html?CNAME=pw01dud102024108284%2FFB) |
| タイザンフクン | 2024106984 | ナダル | ネオユニヴァース | [JRA](https://www.jra.go.jp/JRADB/accessU.html?CNAME=pw01dud002024106984%2F8D) |
| タナオルフォーリア | 2024109036 | エフフォーリア | オルフェーヴル | [JRA](https://www.jra.go.jp/JRADB/accessU.html?CNAME=pw01dud102024109036%2F1E) |
| ダイヴ | 2024100874 | インディチャンプ | クロフネ | [JRA](https://www.jra.go.jp/JRADB/accessU.html?CNAME=pw01dud002024100874%2FB2) |
| ディアム | 2024102901 | エフフォーリア | モーリス | [JRA](https://www.jra.go.jp/JRADB/accessU.html?CNAME=pw01dud002024102901%2FF8) |
| トロカアニマダ | 2024103593 | ベンバトル | ゴールドシップ | [JRA](https://www.jra.go.jp/JRADB/accessU.html?CNAME=pw01dud102024103593%2F80) |
| ドンタククイーン | 2024105603 | ハイランドリール | サクラプレジデント | [JRA](https://www.jra.go.jp/JRADB/accessU.html?CNAME=pw01dud102024105603%2FFF) |
| ドーリック | 2024105845 | マインドユアビスケッツ | ゴールドアリュール | [JRA](https://www.jra.go.jp/JRADB/accessU.html?CNAME=pw01dud102024105845%2F87) |
| ニシノメガミサマ | 2024101683 | サリオス | オペラハウス | [JRA](https://www.jra.go.jp/JRADB/accessU.html?CNAME=pw01dud002024101683%2FDC) |
| ピュアティアラ | 2024101205 | シニスターミニスター | ゴールドアリュール | [JRA](https://www.jra.go.jp/JRADB/accessU.html?CNAME=pw01dud102024101205%2F65) |
| フェイマスウルフ | 2024100276 | シャンハイボビー | パイロ | [JRA](https://www.jra.go.jp/JRADB/accessU.html?CNAME=pw01dud102024100276%2F59) |
| フェデュデスタン | 2024102205 | チュウワウィザード | ヴィクトワールピサ | [JRA](https://www.jra.go.jp/JRADB/accessU.html?CNAME=pw01dud102024102205%2F54) |
| ヘヴンリーワールド | 2024103194 | ワールドプレミア | ヨハネスブルグ | [JRA](https://www.jra.go.jp/JRADB/accessU.html?CNAME=pw01dud102024103194%2F2F) |
| マカロンボイス | 2024101322 | フィレンツェファイア | チーフベアハート | [JRA](https://www.jra.go.jp/JRADB/accessU.html?CNAME=pw01dud102024101322%2F5D) |
| マックスプロックス | 2024106024 | マインドユアビスケッツ | ステイゴールド | [JRA](https://www.jra.go.jp/JRADB/accessU.html?CNAME=pw01dud102024106024%2F5B) |
| マンノエンプレス | 2024101394 | ロジャーバローズ | トウカイテイオー | [JRA](https://www.jra.go.jp/JRADB/accessU.html?CNAME=pw01dud002024101394%2FCC) |
| ミホマル | 2024101431 | グレーターロンドン | シニスターミニスター | [JRA](https://www.jra.go.jp/JRADB/accessU.html?CNAME=pw01dud102024101431%2F2B) |
| ランスオブナイト | 2024106792 | シャンハイボビー | ヘニーヒューズ | [JRA](https://www.jra.go.jp/JRADB/accessU.html?CNAME=pw01dud002024106792%2F55) |
| ランプリサージュ | 2024102484 | キタサンブラック | キングカメハメハ | [JRA](https://www.jra.go.jp/JRADB/accessU.html?CNAME=pw01dud002024102484%2FDC) |
| リアルハーン | 2024102352 | ヴァンゴッホ | アグネスタキオン | [JRA](https://www.jra.go.jp/JRADB/accessU.html?CNAME=pw01dud002024102352%2F95) |
| リプレイハズシ | 2024109045 | サトノクラウン | アドマイヤムーン | [JRA](https://www.jra.go.jp/JRADB/accessU.html?CNAME=pw01dud102024109045%2FBB) |
| リリーリリー | 2024103863 | アドマイヤマーズ | Mikki Isle | [JRA](https://www.jra.go.jp/JRADB/accessU.html?CNAME=pw01dud102024103863%2FE3) |
| ルージュクエーサー | 2024103405 | ブリックスアンドモルタル | ディープインパクト | [JRA](https://www.jra.go.jp/JRADB/accessU.html?CNAME=pw01dud002024103405%2FBE) |
| レンミッキ | 2024100094 | ウインブライト | ヤマニンセラフィム | [JRA](https://www.jra.go.jp/JRADB/accessU.html?CNAME=pw01dud002024100094%2F4A) |
| ワイドヴァラー | 2024108373 | Yaupon | Into Mischief | [JRA](https://www.jra.go.jp/JRADB/accessU.html?CNAME=pw01dud002024108373%2FC2) |
| ヴェントセラーレ | 2024106966 | ルヴァンスレーヴ | オルフェーヴル | [JRA](https://www.jra.go.jp/JRADB/accessU.html?CNAME=pw01dud002024106966%2F53) |

## JBIS原票・5代祖先の再確認一覧

位置は対象馬を0代、父母を1代として最大5代までの全62位置。祖先名の内包は位置から再計算できるが、系統分類・評価点は登録していない。表は取得時点の直接関係であり、過去の調教国を意味しない。

| 参照個体 | JBIS ID | 父 | 母父 | 5代位置 | 出典 |
|---|---|---|---|---|---|
| Caro(IRE) | 0000334731 | フオルテイノ(FR) | Chamossaire(GB) | 62/62 | [JBIS](https://www.jbis.or.jp/horse/0000334731/pedigree/) |
| Storm Cat(USA) | 0000337102 | Storm Bird(CAN) | Secretariat(USA) | 62/62 | [JBIS](https://www.jbis.or.jp/horse/0000337102/pedigree/) |
| Bellamy Road(USA) | 0001127392 | Concerto(USA) | Deputed Testamony(USA) | 62/62 | [JBIS](https://www.jbis.or.jp/horse/0001127392/pedigree/) |
| ファインニードル | 0001173702 | アドマイヤムーン | Mark of Esteem(IRE) | 62/62 | [JBIS](https://www.jbis.or.jp/horse/0001173702/pedigree/) |
| カラテ | 0001218051 | トゥザグローリー | フレンチデピュティ(USA) | 62/62 | [JBIS](https://www.jbis.or.jp/horse/0001218051/pedigree/) |
| ウインカーネリアン | 0001232540 | スクリーンヒーロー | マイネルラヴ(USA) | 62/62 | [JBIS](https://www.jbis.or.jp/horse/0001232540/pedigree/) |
| ミスニューヨーク | 0001235530 | キングズベスト(USA) | マンハッタンカフェ | 62/62 | [JBIS](https://www.jbis.or.jp/horse/0001235530/pedigree/) |
| シュヴァリエローズ | 0001265020 | ディープインパクト | Sevres Rose(IRE) | 62/62 | [JBIS](https://www.jbis.or.jp/horse/0001265020/pedigree/) |
| ステラヴェローチェ | 0001268890 | バゴ(FR) | ディープインパクト | 62/62 | [JBIS](https://www.jbis.or.jp/horse/0001268890/pedigree/) |
| メイショウゲキリン | 0001307055 | キズナ | キングカメハメハ | 62/62 | [JBIS](https://www.jbis.or.jp/horse/0001307055/pedigree/) |
| レッドモンレーヴ | 0001309017 | ロードカナロア | ディープインパクト | 62/62 | [JBIS](https://www.jbis.or.jp/horse/0001309017/pedigree/) |
| エーティーマクフィ | 0001309048 | マクフィ(GB) | ハーツクライ | 62/62 | [JBIS](https://www.jbis.or.jp/horse/0001309048/pedigree/) |
| ママコチャ | 0001310713 | クロフネ(USA) | キングカメハメハ | 62/62 | [JBIS](https://www.jbis.or.jp/horse/0001310713/pedigree/) |
| キングズパレス | 0001311211 | キングカメハメハ | Dubawi(IRE) | 62/62 | [JBIS](https://www.jbis.or.jp/horse/0001311211/pedigree/) |
| シェイクユアハート | 0001319644 | ハーツクライ | Sri Pekan(USA) | 62/62 | [JBIS](https://www.jbis.or.jp/horse/0001319644/pedigree/) |
| ココナッツブラウン | 0001320645 | キタサンブラック | キングカメハメハ | 62/62 | [JBIS](https://www.jbis.or.jp/horse/0001320645/pedigree/) |
| トップナイフ | 0001326655 | デクラレーションオブウォー(USA) | スピニングワールド(USA) | 62/62 | [JBIS](https://www.jbis.or.jp/horse/0001326655/pedigree/) |
| プロトポロス | 0001328639 | War Front(USA) | Sunday Break(JPN) | 62/62 | [JBIS](https://www.jbis.or.jp/horse/0001328639/pedigree/) |
| ワールズエンド | 0001336773 | ロードカナロア | ゼンノロブロイ | 62/62 | [JBIS](https://www.jbis.or.jp/horse/0001336773/pedigree/) |
| ピューロマジック | 0001338391 | アジアエクスプレス(USA) | ディープインパクト | 62/62 | [JBIS](https://www.jbis.or.jp/horse/0001338391/pedigree/) |
| クリスマスパレード | 0001338648 | キタサンブラック | Blame(USA) | 62/62 | [JBIS](https://www.jbis.or.jp/horse/0001338648/pedigree/) |
| メイショウヨゾラ | 0001339489 | グレーターロンドン | ヨハネスブルグ(USA) | 62/62 | [JBIS](https://www.jbis.or.jp/horse/0001339489/pedigree/) |
| ロードフォアエース | 0001340263 | ロードカナロア | War Front(USA) | 62/62 | [JBIS](https://www.jbis.or.jp/horse/0001340263/pedigree/) |
| ラヴァンダ | 0001341405 | シルバーステート | ベーカバド(FR) | 62/62 | [JBIS](https://www.jbis.or.jp/horse/0001341405/pedigree/) |
| サクラファレル | 0001352772 | サートゥルナーリア | シンボリクリスエス(USA) | 62/62 | [JBIS](https://www.jbis.or.jp/horse/0001352772/pedigree/) |
| フリッカージャブ | 0001354060 | サートゥルナーリア | サクラバクシンオー | 62/62 | [JBIS](https://www.jbis.or.jp/horse/0001354060/pedigree/) |
| ミニトランザット | 0001354702 | エピファネイア | ゼンノロブロイ | 62/62 | [JBIS](https://www.jbis.or.jp/horse/0001354702/pedigree/) |
| サウンドモリアーナ | 0001355065 | ミッキーアイル | ケイムホーム(USA) | 62/62 | [JBIS](https://www.jbis.or.jp/horse/0001355065/pedigree/) |
| クラスペディア | 0001355171 | ミスターメロディ(USA) | アグネスタキオン | 62/62 | [JBIS](https://www.jbis.or.jp/horse/0001355171/pedigree/) |
| ジーティーアダマン | 0001356235 | ルーラーシップ | マンハッタンカフェ | 62/62 | [JBIS](https://www.jbis.or.jp/horse/0001356235/pedigree/) |
| レイピア | 0001357582 | タワーオブロンドン | エンパイアメーカー(USA) | 62/62 | [JBIS](https://www.jbis.or.jp/horse/0001357582/pedigree/) |
| ジョバンニ | 0001357974 | エピファネイア | Footstepsinthesand(GB) | 62/62 | [JBIS](https://www.jbis.or.jp/horse/0001357974/pedigree/) |
| パンジャタワー | 0001359664 | タワーオブロンドン | ヴィクトワールピサ | 62/62 | [JBIS](https://www.jbis.or.jp/horse/0001359664/pedigree/) |
| ダノンシーマ | 0001360338 | キタサンブラック | Include(USA) | 62/62 | [JBIS](https://www.jbis.or.jp/horse/0001360338/pedigree/) |
| サトノシャイニング | 0001360350 | キズナ | Star Dabbler(USA) | 62/62 | [JBIS](https://www.jbis.or.jp/horse/0001360350/pedigree/) |
| レディネス | 0001360434 | スワーヴリチャード | Shamardal(USA) | 62/62 | [JBIS](https://www.jbis.or.jp/horse/0001360434/pedigree/) |
| ティニア(IRE) | 0001360735 | Frankel(GB) | Giant's Causeway(USA) | 62/62 | [JBIS](https://www.jbis.or.jp/horse/0001360735/pedigree/) |
| カラマティアノス | 0001361718 | レイデオロ | ハーツクライ | 62/62 | [JBIS](https://www.jbis.or.jp/horse/0001361718/pedigree/) |
| スターアニス | 0001368949 | ドレフォン(USA) | ダイワメジャー | 62/62 | [JBIS](https://www.jbis.or.jp/horse/0001368949/pedigree/) |
| レザベーション | 0001369090 | ダノンプレミアム | ジャングルポケット | 62/62 | [JBIS](https://www.jbis.or.jp/horse/0001369090/pedigree/) |
| ロデオドライブ | 0001370684 | サートゥルナーリア | スニッツェル(AUS) | 62/62 | [JBIS](https://www.jbis.or.jp/horse/0001370684/pedigree/) |
| ディールメーカー | 0001371741 | イスラボニータ | ホワイトマズル(GB) | 62/62 | [JBIS](https://www.jbis.or.jp/horse/0001371741/pedigree/) |
| ゾロアストロ | 0001372977 | モーリス | ディープインパクト | 62/62 | [JBIS](https://www.jbis.or.jp/horse/0001372977/pedigree/) |
| ロブチェン | 0001374057 | ワールドプレミア | Giant's Causeway(USA) | 62/62 | [JBIS](https://www.jbis.or.jp/horse/0001374057/pedigree/) |
| マスターソアラ | 0001374938 | シスキン(USA) | ダイワメジャー | 62/62 | [JBIS](https://www.jbis.or.jp/horse/0001374938/pedigree/) |
| フォルテアンジェロ | 0001375647 | フィエールマン | Dark Angel(IRE) | 62/62 | [JBIS](https://www.jbis.or.jp/horse/0001375647/pedigree/) |
| ロジケープ | 0001375999 | ロジユニヴァース | ハーツクライ | 62/62 | [JBIS](https://www.jbis.or.jp/horse/0001375999/pedigree/) |
| トップチェッカー | 0001387175 | インディチャンプ | クロフネ(USA) | 62/62 | [JBIS](https://www.jbis.or.jp/horse/0001387175/pedigree/) |
| ビスケットサンド | 0001389298 | マインドユアビスケッツ(USA) | ダイワメジャー | 62/62 | [JBIS](https://www.jbis.or.jp/horse/0001389298/pedigree/) |
| ジーティーマイカ | 0001391340 | シスキン(USA) | ダイワメジャー | 62/62 | [JBIS](https://www.jbis.or.jp/horse/0001391340/pedigree/) |
| レッチュベルク | 0001396835 | インディチャンプ | Galileo(IRE) | 62/62 | [JBIS](https://www.jbis.or.jp/horse/0001396835/pedigree/) |
| ショウナンガレオン | 0001401349 | Flightline(USA) | Full Mast(USA) | 62/62 | [JBIS](https://www.jbis.or.jp/horse/0001401349/pedigree/) |

## 調教国・条件別成績の保留

JRA53頭の原票はいずれも美浦または栗東の調教師所属を示し、取得時点の本人の調教国は日本と確認できる。米国産・英語父名などを米国調教と判断しない。たとえばスリーオブスペイズ、エリーマイラヴ、ワイドヴァラーは海外産地表記があっても日本の調教師所属である。

JBIS52参照個体のうち49個体は取得時点の美浦・栗東所属が明記される。残る **Caro(IRE)、Storm Cat(USA)、Bellamy Road(USA)** は具体的な調教国を原票から確定できない。「海外」や出生国の接尾辞だけでUS/EUに分類しない。過去の移籍・調教国履歴も今回の現所属から補完しない。

父・母父・指定祖先それぞれの調教国履歴、EUの対象国・複数地域履歴の扱い、全予想レースの公式全出走母数・確定結果、統一した父系・母父系の分類版は別途必要。これらが未確認のため、`official-runners-manifest-v1`や実成績snapshotを作ったと報告せず、勝率・連対率・3着内率を算出しない。

535記述・626成分には明示父/母父106成分以外に、派生・系統218、傾向・解釈83、未分類219成分がある。今回の親子関係照合だけで、これらの文意・人気別母数・歴史的集計・適性解釈まで一致確認したことにはしない。詳細の保留状態は元manifestを正本として維持する。

## 再検証と受入

```sh
python3 scripts/check_pedigree_reconciliation.py
python3 -m unittest discover -s scripts -p 'test_*.py'
python3 scripts/pedigree_registry.py audit
```

- 既存Python unittest **212件成功**。
- 照合checkerは106項目の元claim/成分/行と公式個体・原票値・hashの一致、全53頭の網羅性、3表記差の明示対応を検査する。
- JBIS全52表の62位置、全参照個体ID、Registryの親子関係との一致、独立関係の競合・数、過去cutoffへの流用拒否を検査する。
- Registry監査は全個体・revision/hash・外部ID重複・初期時刻・旧535候補の未昇格を検査する。照合checker内の監査は単一Writerのlock下で読取集合を固定し、同定重複検査のための反復ディスク読込を省く。CLIの`audit`は従来どおりGit移行元commitも検査する。
- `audit_result.json`は実行した照合checkerの結果。GitHub上の保存確認はcommitのtree/blob SHAと読戻しで別途検証する。Actionsの成功や原票取得を、過去の予想保存証跡の修復とみなさない。
