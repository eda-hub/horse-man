# 競馬予想ルール — v1.7.0モジュールmanifest

- **現行リリース**: `v1.7.0`
- 有効化条件: **PR79のmainマージ後**。未マージbranchの新版を正式Productionへ使わない。
- 正本: eda-hub/horse-manのmain、docs/manual。本READMEを最初に読み、同一commitの必要Ownerだけ参照する。
- 検証サイクル: **第4、2026-10-17〜25**。10/17・18・24・25、東京・京都・新潟。予定144Rと実測を分ける。

## Ownerと一方向の処理

| Owner | 唯一の責任 |
|---|---|
| 00_core | 実行モード、scope/用途、日次branch、保存/期限、基準IDと責任境界 |
| 10_prediction | 非価格の事実→評価→全頭確率→順位→印、予想確信度・根拠 |
| 20_conditional | 正式当日補正、重賞の直接事実取得。重賞も通常の同じ骨格 |
| 30_betting | ファイル名を維持した価格不要推奨の唯一のOwner。券種・具体的組合せ・点数・優先順位・理由 |
| 40_shadow | 固定Productionから独立する比較仮説。過去集団傾向と新規featureの検証 |
| 50_review | 公式結果照合、Prediction/推奨/Shadowの独立KPI、非劣化・個別採否 |
| 60_market（任意） | 価格観測/予測・市場乖離・任意仮想収益。標準予想へ逆流しない |

標準フローは事実→Prediction→該当直接情報→基準固定→価格不要推奨→該当Shadow→結果→回顧。全Ownerのmanual_release不一致なら開始しない。実購入意思・金額・購入確認・実購入ROIは新規中核に含めない。WebUIは実装対象外。

## 依頼別の入口

| 依頼 | 読むOwnerと実行 |
|---|---|
| 初回事前予想/開催全体選別 | 00_core・10_prediction・50_review所属、該当20_conditional/40_shadow。初回全scope・基準・選定/未取得を保存 |
| 選定候補の最終予想 | 上記＋30_betting。当日馬体重等を取得試行し、選定集合のみを最終化。推奨または理由付き推奨なしまで独立保存 |
| JRA/海外重賞 | 通常の共通Predictionを先に固定。docs/yosouの現行記録と20_conditionalの直接情報を参照。過去集団傾向は固定後Shadow |
| 回顧 | 00_core・50_review、元のPrediction/推奨/該当Shadow。初回全scopeの公式結果→日別→サイクルを読戻す |
| 任意市場検証 | 固定後60_market。価格なしのPrediction/推奨を止めない |

通常の初回・最終・回顧依頼だけで該当サイクルの検証まで実行する。予約タスクも同じ。開催全体の候補属性だけで最終対象を増やさない。

## 保存と運用入口

`00_core` 0.0.9〜0.0.12と [第4運用契約](../validation/contracts/cycle04_operations.md) に従い、prediction/YYYY-MM-DDへ宣言→独立FIX hash→本体→receiptを保存・読戻す。新規は1artifactごとのJSONで、旧Markdownを修復しない。予想と推奨の個別完了、gate、適用Shadowを独立確認し、日本語で状態を示す。

`run_release_readiness.py --require-main` でmain有効化を確認し、`cycle04_workflow.py` で公式scope登録・初回/最終記録・結果照合/回顧・独立集計を行う。新規第4台帳はcycle04-day-v1。未実施日を空scopeや実測0で作らない。

## 情報取得・変更・旧履歴

当日馬体重は依頼時にJRA公式→スポーツナビ→信頼できる代替を試行し、未取得を未発表/0と断定しない。全頭coverage・出所・観測/取得/読戻し時刻と不確実性を残す。静的証拠は再利用し、動的情報だけ必要に応じ更新する。

基準IDを別チャット/オッズ更新だけで作り直さない。強い非価格事実で更新する場合は新revisionと前後根拠を固定する。ユーザー向けには内部検証IDを表示せず、結果・原因・不足・次の確認を平易な日本語で伝える。

第3以前は当時のv1.6.1/旧gate/KPI契約の読取履歴。旧☆・Betting・実購入を新KPIへ混ぜず、後付けの事前証跡や結果に合わせた変更を行わない。Git commit/PR/tagを履歴正本にし、oldディレクトリや複製manualを作らない。

正式効果昇格は50_reviewの条件・非劣化と別PRで審査する。システム設計の正本はDECISIONS/docs/jravan。Windows/JRA-VANの実接続はこのチャット/Git運用の切替とは別のPhase受入であり、未接続を稼働済みと呼ばない。
