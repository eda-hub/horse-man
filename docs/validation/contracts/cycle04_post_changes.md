# 第4サイクル・公式発走時刻変更の追記運用

対象：第4サイクルの登録済み同一開催日・同一レース。旧v1.6.1の証跡は遡及的に変更しない。

## 不変条件

- 日別台帳 races[race_id].scheduled_post_time_jst と official_scope は初回登録時刻として保持する。既存の予想・推奨・Shadow・FIX・receipt・選定履歴は変更しない。
- 変更は日別台帳の schedule_changes へ原本の固定path・SHA-256参照を追記する。URLやフラグだけでは認証しない。
- 対象証跡の保存・読戻し時点までに確認された変更だけを適用する。遅延を後から知っても旧LATE/REPLAYは適格化しない。
- 延長後の正式予想は当時確認済みの新時刻に基づく別の事前宣言・FIX・本体・receipt・gateを作る。Gitに保存されていない発走変更を前向き適格性の根拠としない。
- 前倒しで既存証跡が新時刻に間に合わない場合は不適格・保留。証跡時点で確認済みの予定は最新の一件を採用し、すでに延長で上書きされた途中の時刻を独立した期限として再検査しない。証跡より後に確認した改訂のうち、直前予定より前倒しとなった新時刻が証跡の保存・読戻し以前なら、当時の認識とは別に正式適格性を拒否する。後から確認した延長で旧LATEを適格へ戻さない。原本と旧予定の履歴は保持する。取消、中止、翌日延期、開催日・race ID変更はOwnerと公式資料の確認まで保留し、cycleや依頼scopeを自動移動しない。

## 公式原文の固定

JRAの公式画面を人が確認し、以下の項目を持つ独立JSONとして保存・読戻しする。以下は**形式の例**であって実レース記録ではない。

    {
      "provider": "OFFICIAL", "mode": "FORWARD",
      "retrieval_kind": "PAGE_TEXT",
      "source_url": "https://www.jra.go.jp/...",
      "retrieved_at_jst": "<実取得したJST ISO 8601>",
      "text": "<公式本文>"
    }

JRA公式の掲載時刻が不明ならnullとする。レース日時・場名・番号・旧/新発走時刻が引用部分から一致確認できない場合、推測で補わず保留する。旧時刻と新時刻の存在だけでなく、引用内の「旧時刻 → 新時刻」（「⇒」「->」「から」も可）の向きが宣言値と一致しなければ拒否する。方向を明示しない公式記載は保留し、推測で延長として扱わない。日付・開催場・レース番号・方向付き時刻を同一の発走変更記載内で照合し、引用中に別場・別レースの識別情報が混在したら認証せず保留する。引用の範囲を単一の明示的な変更記載へ絞って再確認する。HTTPSの公式ドメイン表記自体は外部サイトの真実性を証明しない。

## 変更原本と登録入口

変更原本の固定pathは docs/validation/schedule-changes/YYYY-MM-DD/YYYYMMDD-TOK-01/0001.json とする。0002以降は直前のJSONのbytes hashと変更後時刻を継承し、番号や改訂chainに欠番・分岐を認めない。

    {
      "schema_version": "cycle04-official-post-change-v1",
      "race_date_jst": "YYYY-MM-DD",
      "race_id": "YYYYMMDD-TOK-01",
      "revision": 1,
      "previous_sha256": null,
      "old_post_time_jst": "<初回予定時刻>",
      "new_post_time_jst": "<公式変更後の予定時刻>",
      "official_text_ref": {
        "artifact_path": "<公式原文の固定path>",
        "sha256": "<原文bytesのSHA256>"
      },
      "quotation": {
        "start": 0, "end": 0, "text": "<公式本文の一致引用>"
      },
      "official_published_at_jst": null,
      "observed_at_jst": "<取得・確認時刻>",
      "readback_verified_at_jst": "<読戻し確認時刻>"
    }

引用位置start/endはUTF-8デコード後の文字列の文字位置。endは排他的。上記の0/0は記入欄でありそのままでは登録不可。取得 <= 観測 <= 読戻し、公式掲載 <= 取得、未来日時なし。同一race/dateの前改訂に連続すること。

    {
      "race_id": "YYYYMMDD-TOK-01",
      "change_ref": {
        "artifact_path": "docs/validation/schedule-changes/YYYY-MM-DD/YYYYMMDD-TOK-01/0001.json",
        "sha256": "<変更原本JSON bytesのSHA256>"
      }
    }

上記entry JSONを change-entry.json として保存し、次を日次作業ブランチで実行する。

    python3 scripts/cycle04_workflow.py --date YYYY-MM-DD --register-post-change change-entry.json --preview
    python3 scripts/cycle04_workflow.py --date YYYY-MM-DD --register-post-change change-entry.json

プレビューは原本と既存台帳の全検査のみを実施し、恒久台帳へ書き込まない。成功を確認してから正式登録する。

新時刻を既存 --register-scope / --extend-scope によって再定義しない。変更原本・公式原文・日別台帳をGit保存・読戻しし、変更前に固定した予想と別の新時刻用証跡を維持する。

## 各入口と互換境界

| 対象 | 実装 | 変化時の取り扱い |
|---|---|---|
| 登録と日別台帳 | cycle04_workflow.py / check_cycle04.py | 原時刻を保持、変更chainを検査 |
| 原文・改訂 | cycle04_schedule_change.py | path/hash、JRA引用、観測時刻、Git先行記録 |
| 予想と保存 | check_prediction_compliance.py / verify_prediction_persistence.py / cycle04_operations.py | 証跡読戻し時点の予定を検査 |
| Shadow・推奨 | check_prediction_compliance.py / recommendation.py | 別原本/receiptと当時予定を検査 |
| 選定 | selection_history.py / cycle04_operations.py | scheduled_postsは初回予定、変更後の新イベントはscheduled_post_time_jstを個別明記 |
| 公式結果・回顧 | chat_fact_capture.py / chat_result_conversion.py / chat_result_reconciliation.py | 公式見出しの予定と同一race/dateの履歴一致が必要 |
| 完了・集計 | cycle04_completion.py / task_completion.py / check_cycle04.py | 過去の固定予定を再検査、証跡不足を自動適格化しない |

任意市場sidecarを変更後に保存する場合はentryへ scheduled_post_time_jst を明示する。旧時刻の選定イベント・receiptは上書きせず、新時刻のイベント・証跡を追加する。旧Markdown複数レース予想のreceipt共通期限は最早発走時刻を表すため、各レースの公式予定時刻と等値比較せず、各レースの発走より保存・読戻しが早いことを別途確認する。

## テスト・切り戻し

    python3 -m unittest discover -s scripts -p 'test_*.py'
    python3 scripts/run_cycle04_acceptance.py --write
    python3 scripts/build_v170_manifest.py
    python3 scripts/check_cycle04.py
    python3 scripts/run_release_readiness.py
    python3 scripts/check_integration_acceptance.py --full

3系統CIは check-cycle03.yml、check-integration-acceptance.yml、check-pedigree-research.yml。実行ログがない場合はPASSとしない。合成テスト成功だけでは実レースの公式変更を証明しない。

切り戻しは実装変更commitをrevertし、契約・受入・releaseを再整合する。既存の公式原本、変更原本、receipt、固定予想、結果・回顧は削除しない。
