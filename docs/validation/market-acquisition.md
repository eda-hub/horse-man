# 29番：任意価格の2経路HTTP取得・障害再現

28番の状態・独立保存APIを再利用する。取得先の正規化済みHTTP JSON endpointを主経路1つ・代替1つ設定し、同じrace/券種/組合せの観測価格を取得する。追加の公式JV-Link COM・8券種正規化は [残件対応](market-jvlink.md) へ実装済み。サービス固有HTMLは未実装。Windows実機への接続と2開催以上の実測はOPEN。HTTP経路と公式SDK経路の実装受入は合成試験で、実サービス接続の成功とは区別する。

## 取得要求と応答

要求schema `market-price-request-v1`：mode（FORWARD/SYNTHETIC）、race_id、race_date_jst、scheduled_post_time_jst、ticket、deadline_at_jst、data_cutoff、routes（主/代替のsource_url・max_attempts）、timeout_seconds、retry_delay_seconds。URLは異なる2endpoint。通常はHTTPS、合成のHTTPはloopback限定。URL内user/passwordは禁止。各経路1〜3試行、timeout .01〜30秒、再試行待ち0〜30秒。deadline≦cutoff＜発走、対象日と発走日が一致。ticketは8券種の既存arity、馬単/三連単は順序付き、他は正規化して照合。

応答schema `market-price-response-v1`：race_id、ticket、observed_at_jst、odds。観測専用。予測最終価格や結果後の最終価格を観測価格へ偽装しない。取得したresponseのrace/券事象が要求と一致し、観測時刻≦実取得時刻かつ要求cutoff/締切以内、oddsは有限正数であることを検査。未校正確率や期待値は作らず、取得済みでも判断NOT_EVALUATED/expected_value nullを維持。

## 処理・証跡

- 主経路のGETを最大試行数まで実行し、失敗時に指定時間を待って再試行。主経路枯渇後に代替へ進む。成功したら停止。
- 各通信のtimeoutは締切残時間以下。試行/待機の前にも締切を確認し、締切後は次のGETを開始しない。redirectは出所変更として自動追跡せず失敗に記録。
- 未試行のまま締切を迎えたらattempts空・attempted_at nullで停止。架空の試行を作らない。timeout処理が締切を越えて戻った場合は実finishを保持し、DEADLINE_EXCEEDED/FAILEDとして原応答を保存。遅い成功応答を価格へ採用しない。
- 受信bytesは128KiB+1まで。response_refに実受信bytesのsha256/path/サイズ/完全受信可否、試行にHTTP status/error_codeを保存。ネットワーク失敗で応答がないときはref nullで、空の原本/hashを捏造しない。過大応答は切り詰めた受信prefixと明示し、完全応答として認証しない。
- `market.acquisition.transport_schema: market-http-acquisition-v1` と元requestを保持。原bytesからhash/サイズ/HTTP成否、race/券/価格/観測、経路順・試行上限・再試行待ちを再検査する。誤った失敗diagnosticも拒否。
- cutoffを超えて応答が戻った場合、出力cutoffは実finishまで拡張し、元request cutoffを保持。価格は採用せず遅延記録だけとする。発走以降に終了した分析は日次writerの発走前契約で拒否される。
- 原応答→analysis.jsonの順で専用の新規runフォルダへ追記保存・読戻し。既存runへの上書きなし。中断原本を消さず、新規runで再開する。取得clientは予想・推奨・日次台帳・DBを操作しない。

## 操作

1. 実取得元の正規化契約を確認し、実race/券と主/代替URLを要求JSONへ設定する。未登録のURLを実稼働確認済みとしない。
2. 日次作業branchで `python scripts/market_acquisition.py --root ROOT --request REQUEST_JSON --evidence-dir docs/validation/market-acquisitions/DATE/RUN_ID` を実行する。
3. 成功/失敗のいずれも原応答・分析の保存読戻しを確認する。取得済みのみ終了0。失敗/締切は記録を残して終了1。フォルダは毎回新規とする。
4. 28番の `market_sidecar.py ANALYSIS_JSON` で状態・理由を確認し、独立artifact/receiptを保存・読戻しする。既存 `cycle04_workflow.py --record-market` へmarket_refで登録する。
5. 日次readerでも成功/保留双方の原応答を再照合する。SYNTHETICは独立保存できるが正式市場へ登録できない。価格取得成功を予想/推奨完了・期待値・KPI性能へ転用しない。

## 受入と継続検証

新規22回帰。実HTTP loopbackで503×2→代替200、redirect拒否を再現。注入transportと同じ価格/判断出力、応答hashと読戻し、2経路枯渇、再試行/締切、試行なし停止、遅い応答の実finish保全、timeout残時間、誤race/券/順序/未来価格/非有限値/invalid JSON/過大応答、要求異常、raw改変・再hash後の価格相違、synthetic登録拒否、保存不変、正式writer/readerへの接続と保留raw改変拒否を検証。28番18件、第4既存56件、readiness9件を保持。

29番の共通HTTP処理は実装受入完了。親29番は実接続・実測継続検証。公式JV-Linkの取得spec/要求key・正規化adapterと実測checkerは追加実装済み。Windows実サービス接続・2開催以上の発走前実測が未完了。旧11日の価格不足の原因は未確認のまま。合成開催日を実測日として数えず、過去の価格・宣言・receiptを補造しない。次のコード作業30番はこの実測待ちに価格不要予想を従属させない。
