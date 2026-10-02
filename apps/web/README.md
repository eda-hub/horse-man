# horse-man 予想・買い目WebUI

Macのブラウザで初回予想を比較し、検証候補・購入候補を選び、対象レースの最終予想・買い目と購入／見送り判断を保存する、本人専用のWebUIです。

## 今回の範囲

- 初回一覧、候補チェック、候補だけの最終確認、判断履歴の3つの作業ビュー。
- 初回／FINAL snapshotは変更せず保存。同じ基準の馬・順位・印・勝率の変更は拒否。
- 観測オッズと予測最終オッズを区別。Shadowは取り込み契約に含めず正式予想へ混入させない。
- 見送りは理由＋任意メモ。初回だけの見送りも可能。FINALがあれば推奨買い目を保持。
- 判断訂正と見送り後の候補再選択は履歴へ追加。購入判断の記録は投票を行わない。
- 本人のサインインと所有者単位の記録分離。ホストの公開範囲は本人のみ。
- 実データ／架空サンプルを別領域に保存。サンプルはボタンを押した場合のみ読み込む。
- JSON取り込みと記録書き出し。再読み込み後も記録が残る。

JRA-VAN取得、ルールベース予想エンジン、DuckDBとの自動同期、結果精算、AI回顧は未接続です。予想を生成するボタンは設置せず、生成済みの予想を正確に表示・記録する最小の実用画面を先行実装しています。

## 設計との関係

`DECISIONS.md`、`docs/jravan/01_architecture.md`、`06_webui.md`、`docs/manual/README.md` の v1.6.1 を参照しました。今回の依頼で本人限定のホストを指定されたため、WebUIの配布と判断記録のコピーのみをSitesで提供しています。既存のローカル優先・DuckDB単一Writer・Parquet運用を置換する決定ではありません。D1はこの非公開UIのsnapshotと判断履歴の保存に限定し、DuckDBの競馬分析DBとしては扱いません。ルール本文、予想本体、既存Git記録は変更しません。

外部のexecution gate、receipt、persistence intentは未照合で、このUIの保存は正式ProductionやKPIの適格性、発走前Git永続化の証明を意味しません。取り込みファイルのhashは保持しますが、自己申告値だけで公式監査済みにしません。

## 操作

1. 初回予想JSONを取り込む（全レースを含められます）。
2. 初回一覧で「検証」「購入」にチェックする。
3. 「最終予想・買い目」で、候補のFINAL JSONを取り込んで確認する。
4. 詳細で見送り理由・判断メモ、または購入判断の金額を記録する。
5. 「判断記録」で保存状態を確認し、その日の全レースをJSONへ書き出す。

初回だけの見送りとFINALありの見送りは別のsnapshot参照を持ちます。FINALを作成していないレースを、FINAL保存済みとして表示しません。候補から外したレースも初回一覧と全日書き出しに残ります。

## 取り込み契約

契約：`lib/domain.ts` の `importSchema`。ルートは `POST /api/races`、操作は `action: "import"`、データは `{schema_version:"horse-man-webui-v1",demo:false,races:[...]}`。予想の時点は `INITIAL` または `FINAL`。本文は2MBまで、1回72レースまでです。

各レースには `race_id,date,venue,number,name,starts_at,course,going,snapshot` を入れます。snapshotは `snapshot_id,baseline_forecast_id,stage,manual_release,module_hashes,data_cutoff,created_at,source,summary,recommendation,confidence,horses,tickets,buy_condition,skip_condition` を必須とします。現行リリースはv1.6.1。実データには00_core／10_prediction／20_conditional／30_bettingのSHA-256を必須とします。サンプルの形式は画面から保存できます。

FINALは初回と同じ基準・レース情報・馬・順位・印・勝率で、データ時点は初回以降、予想作成は発走前であることを確認します。オッズと買い目だけを取り込めます。強い非価格情報による基準予想の正式更新は予想エンジンの契約で扱う必要があり、このUIで暗黙に行いません。

購入判断は購入候補で、FINAL・買い目があり、発走前の場合に可能。見送りとメモは発走後も履歴へ追加できます。購入判断を実購入実績として精算する機能は未実装です。

記録書き出しは `horse-man-webui-records-v1`。初回・FINAL・現在の判断・全判断履歴・UI保存時刻を含みます。取り込み形式とは別で、書き出した履歴を別環境へ再取り込みする機能は未実装です。

## ローカル起動（Mac）

Node.js 22.13以上とpnpm 11.25.0を用意し、このディレクトリで `pnpm install --frozen-lockfile`、`npm run db:generate`（schemaを変えた場合のみ）、`npm run build` を実行します。既存のdrizzle migrationを、生成された `dist/server/wrangler.json` のDBへ `node --import ./scripts/sites-env.mjs ./node_modules/wrangler/bin/wrangler.js d1 execute DB --local --config dist/server/wrangler.json --persist-to .wrangler/state --file drizzle/0000_broken_shooting_star.sql` で1回適用します。

`npm run dev` で起動し、表示されたloopback URLを開きます。ローカル開発用のサインインは `/signin-with-chatgpt?return_to=/`。このmockは本番に含まれません。ローカルD1は本番D1と別で、実予想データや本人認証情報をテストコードに埋め込まないでください。

## 検証

`node node_modules/typescript/bin/tsc --noEmit` と本番ビルドを実行。`scripts/test-race-api.mjs` で、実APIの取り込み・候補選定・FINAL・見送り／購入判断履歴・再取得・権限分離・競合・immutable・時点整合性を検証します。入力は架空データで、所有者キーもランダムな検証用を使います。

UIの保存はサーバーAPIとD1で行い、localStorageを正本にしません。APIは毎回所有者を確認し、別Originからの書き込みを拒否します。更新revisionの一意制約で同時操作の上書きを防ぎます。

## 切り戻し

公開範囲は本人限定を維持。ホスト側は前バージョンへ戻せます。今回のmigrationは新規2テーブルで既存競馬DBに変更なし。予想・判断履歴を消して切り戻す処理は実装しません。
