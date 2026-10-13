# 29番残件：公式JV-Link経路・正規化・実測受入

公式SDK5.0.0の配布物とPythonサンプルを実取得してhashを固定し、前回残った取得元/呼出し方式を確定した。主経路は全賭式速報0B30、代替は券種別0B31〜0B36。異なるデータ要求の代替であり同一提供元、JV-Link未導入/認証/サービス全体障害は両方に影響する。公開WebのPC/SP入口は200でもオッズ本文のGETは専用エラー、正規化JSON endpointとは扱わず、独立した代替接続の成功に数えない。

[公式SDK](https://developer.jra-van.jp/t/topic/45)、[JV-Data仕様](https://jra-van.jp/dlb/sdv/sdk/JV-Data4901.pdf) p15〜16、[JV-Link仕様](https://jra-van.jp/dlb/sdv/sdk/JV-Link4901.pdf) p22/25/27を基準にする。[出所・応答hash・接続制限](implementation/2026-10-11-task29-provider.json) に実probe runとSDK/archive/sampleのhashを保存。SDK原ソースや27MBの配布物はリポジトリへ複製しない。取得確認だけのworkflowは除去する。

## Windowsでの実取得

1. 既存のParallels Windows 11 VMで、同じPythonとbit数に対応するJV-Linkとpywin32が利用できることを確認する。既存Data Lab設定を使用し、clientは利用キーの設定/表示・投票APIを操作しない。VMの接続先はこの環境に未登録なので、ここからの実サービス接続は未検証。
2. 要求JSONに対象race/券・発走・締切/cutoff・timeout/待ち時間を指定する。routes URLを利用者が考案する必要はない。
3. `python scripts/market_acquisition.py --jvlink --request REQUEST_JSON --root ROOT --evidence-dir docs/validation/market-acquisitions/DATE/PRIMARY_RUN` を実行する。race_idから公式の12桁要求keyと券種別specを決定。予想・推奨・日次台帳は操作しない。
4. 両データ要求の実接続確認では、別runで同じコマンドに `--alternate-first` を付ける。全賭式/券種別の優先順を切り替えて実取得し、主経路の架空障害を作らない。各runの全試行・原bytes・実return codeを保持。
5. 分析を既存の独立artifact/receipt保存・読戻しへ接続する。市場の日次登録は正式mainのreadiness成立後、28番の既存writerを使う。

SDKのCOM/JVGetsは別processで呼び、timeoutで待機を打ち切る。JVInit→JVRTOpen→JVGets、ファイル切替-1/EOF0/エラー、最後のJVCloseを処理。SDKの実bytearray呼出し型に合わせる。Linuxやpywin32/JV-Link不在はJV_UNAVAILABLEとして失敗記録、HTTP200や取得済みへ置換しない。SDKの負return codeとHTTP statusを分離する。

O1〜O6原bytesの長さ/終端・race/場/R・中間区分1・発売フラグ・発表時刻・券の組合せを照合。最終/確定/中止/削除・欠測/無投票/取消・上限価格を正確な観測価格へ変換しない。複勝/ワイドは実観測の最低/最高をprice_detailsへ保持し、oddsには明示した観測範囲の下端を使う。統計的下限や予測値とは称さず、EVは未評価null。rawから範囲も再照合する。

## 2開催以上の発走前実測

`market-live-validation-v1` manifestのentriesへ、各実測のmarket_ref（artifact/sha256/receipt/ID）と固定commit_shaを登録する。日次の公式scope/実発走、原応答、FORWARDの実取得、独立receipt、発走前のGit固定と元bytesを照合する。

`python scripts/check_market_live_validation.py --root ROOT LIVE_MANIFEST_JSON` で検査。2つ以上の開催日と全賭式/券種別の実取得成功が揃うまでCONTINUE_VALIDATION、条件成立時だけPASS。receiptファイルの後続追記は許容するが当時の同一receiptレコードが元Gitで一致することを要求。原応答・分析の後日書換え、発走後commit、未登録scope、合成/REPLAY、同一ID重複は拒否。受入成功をPrediction/Recommendation性能・正式ルール昇格へ転用しない。

現時点ではこの実行環境がLinuxでpywin32なし、利用者Windows VMへの接続設定もないため、実サービス接続はOPEN。10/17・18等の将来2開催の発走前実測は今日生成できない。ダミー台帳・実測0・過去の宣言/価格/receiptを補造しない。公式経路・正規化・実測checkerの実装受入と、この2残件を分けて保持する。

最終セルフレビュー：Windows作成のresponse_refはGit共通のPOSIX pathへ正規化する。実装LAYOUT/LENGTHSを参照しない公式位置・組合せ順の独立fixtureで再照合。native17＋実測受入7＝追加24回帰、全564回帰/skip0と3系統CIが成功。合成試験をWindows実サービス接続や実開催実測へ数えない。
