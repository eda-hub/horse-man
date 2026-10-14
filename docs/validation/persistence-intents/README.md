# 予想保存の事前宣言と直後確認

次期v1.7.0の**推奨買い目**は既存prediction intentとは別の `recommendation-persistence-intent-v1` を用いる。固定Prediction参照・推奨scope・artifactを事前宣言し、同一artifactの独立receiptとSHA-256を `scripts/recommendation.py --seal/--audit` で確認する。詳しい操作は [次期推奨買い目](../recommendations/README.md)。現行v1.6.1の予想宣言と旧prediction gateの意味は変更しない。

全レース予想や個別レースの依頼を受けた時点で、予想本文の作成前に対象レース・保存予定のsnapshot ID・最も早い発走時刻を宣言する。予約実行なら予約設定時に日次作業ブランチへ保存し、同じブランチから読戻す。既存ブランチ・既存ファイルは再利用する。

`scripts/verify_prediction_persistence.py --prepare` は `docs/validation/persistence-intents/YYYY-MM-DD/<intent-id>.json` を作る。既存の同名宣言を異なる内容で上書きしない。日付や競馬場は固定しない。

```bash
python3 scripts/verify_prediction_persistence.py --prepare \
  --date YYYY-MM-DD --intent-id morning --snapshot-id SNAPSHOT_ID \
  --deadline-jst YYYY-MM-DDThh:mm:ss+09:00 \
  --race-id RACE_ID_1 --race-id RACE_ID_2
```

v2 JSON snapshotでは、1レース1artifactを基本とし、予想作成前に保存予定pathも宣言する。

```bash
python3 scripts/verify_prediction_persistence.py --prepare \
  --date YYYY-MM-DD --intent-id RACE_INTENT \
  --snapshot-id SNAPSHOT_ID \
  --artifact-path docs/validation/snapshots/YYYY-MM-DD/SNAPSHOT_ID.json \
  --deadline-jst YYYY-MM-DDThh:mm:ss+09:00 \
  --race-id RACE_ID
```

`artifact_path` はv2 JSONで推奨し、receiptの `artifact_path` と同一でなければ保存完了としない。旧Markdown intentでは省略可能で、従来どおり `snapshots/YYYY-MM-DD.md` 内の該当sectionを解決する。

旧Markdown snapshotでは、宣言したレースを漏れなく次の構造化ブロックで記録する。見送りも含める。v2 JSON snapshotでは `race_id` 自体を対象範囲とし、intentの `required_race_ids` と完全一致させる。

```prediction-scope-v1
{"race_ids":["RACE_ID_1","RACE_ID_2"]}
```

保存順序は「宣言を保存・読戻し → 予想snapshotを保存・読戻し → receiptを保存・読戻し → 直後照合」。照合は**日次作業ブランチから読戻した内容**に対して実行する。

```bash
python3 scripts/verify_prediction_persistence.py --date YYYY-MM-DD --snapshot-id SNAPSHOT_ID
python3 scripts/verify_prediction_persistence.py --audit --date YYYY-MM-DD
```

直後照合はsnapshotの単一存在、宣言とのレース範囲一致、宣言したartifact path、同一artifactのreceipt、両方の読戻し時刻が最も早い発走前かを確認する。v2 JSONでは `schema_version=prediction-snapshot-v2`、`snapshot_id`、`race_id`、`working_branch` も検証する。欠落時は発走前に保存・読戻しを再試行する。発走後は時刻を遡らせず実際の保存状態を報告・保全する。照合の失敗を理由にFIXED済みの予想内容をチャット回答から消さない。

GitHub Actionsの監査は保存済み宣言の未完了を通知する補助手段であり、書込みの前提条件でも正式KPIの適格判定でもない。宣言がない過去の予想は `NO_INTENTS` と表示され、完全性を保証しない。

タスク完了確認は直接照合に `--task-complete --intent-id INTENT_ID --fixed-content-sha256 HASH` を付ける。旧MarkdownではHASHをFIX済みsectionのUTF-8 bytesから、v2 JSONでは保存するJSONファイル全体のbytesからSHA-256で計算して保持する。事前宣言ファイル、scope、artifact path、内容ハッシュ、同一artifactのreceiptと時刻を照合できない場合は完了にしない。監査はsnapshot IDごとの宣言欠落も報告するため、朝の宣言だけで個別最終の保存成功を保証しない。

v2 JSON snapshotも `--audit` の対象であり、intentなしのJSONは `NO_INTENT`、対応execution gateがないJSONはcompliance auditで `SNAPSHOT_UNREGISTERED` として検出する。旧Markdown snapshotも同じ監査を継続する。

失敗した旧形式の試行は `failed-attempts/` に原文を保持し、現行の宣言一覧から分離する。2026-10-03のmorning旧形式は `failed-attempts/2026-10-03-morning.json`、後続有効形式は `2026-10-03/morning-v2.json`。旧形式のpayload・ID・時刻は変更していない。後続もreceipt欠落のため未完了であり、旧形式を成功した事前宣言へ変換しない。
