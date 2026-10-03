# 予想保存の事前宣言と直後確認

全レース予想や個別レースの依頼を受けた時点で、予想本文の作成前に対象レース・保存予定のsnapshot ID・最も早い発走時刻を宣言する。予約実行なら予約設定時に日次作業ブランチへ保存し、同じブランチから読戻す。既存ブランチ・既存ファイルは再利用する。

`scripts/verify_prediction_persistence.py --prepare` は `docs/validation/persistence-intents/YYYY-MM-DD/<intent-id>.json` を作る。既存の同名宣言を異なる内容で上書きしない。日付や競馬場は固定しない。

```bash
python3 scripts/verify_prediction_persistence.py --prepare \
  --date YYYY-MM-DD --intent-id morning --snapshot-id SNAPSHOT_ID \
  --deadline-jst YYYY-MM-DDThh:mm:ss+09:00 \
  --race-id RACE_ID_1 --race-id RACE_ID_2
```

全レース予想のsnapshotには、宣言したレースを漏れなく次の構造化ブロックで記録する。見送りも含める。個別予想にも同じ形式で対象レースを一つ記録する。

```prediction-scope-v1
{"race_ids":["RACE_ID_1","RACE_ID_2"]}
```

保存順序は「宣言を保存・読戻し → 予想snapshotを保存・読戻し → receiptを保存・読戻し → 直後照合」。照合は**日次作業ブランチから読戻した内容**に対して実行する。

```bash
python3 scripts/verify_prediction_persistence.py --date YYYY-MM-DD --snapshot-id SNAPSHOT_ID
python3 scripts/verify_prediction_persistence.py --audit --date YYYY-MM-DD
```

直後照合はsnapshotの単一存在、宣言とのレース範囲一致、同一artifactのreceipt、両方の読戻し時刻が最も早い発走前かを確認する。欠落時は発走前に保存・読戻しを再試行する。発走後は時刻を遡らせず実際の保存状態を報告・保全する。照合の失敗を理由にFIXED済みの予想内容をチャット回答から消さない。

GitHub Actionsの監査は保存済み宣言の未完了を通知する補助手段であり、書込みの前提条件でも正式KPIの適格判定でもない。宣言がない過去の予想は `NO_INTENTS` と表示され、完全性を保証しない。

タスク完了確認は直接照合に `--task-complete --intent-id INTENT_ID --fixed-content-sha256 HASH` を付ける。HASHは予想FIX時に保存前のsectionから保持する。事前宣言ファイル、scope、内容ハッシュ、同一artifactのreceiptと時刻を照合できない場合は完了にしない。監査はsnapshot IDごとの宣言欠落も報告するため、朝の宣言だけで個別最終の保存成功を保証しない。

失敗した旧形式の試行は `failed-attempts/` に原文を保持し、現行の宣言一覧から分離する。2026-10-03のmorning旧形式は `failed-attempts/2026-10-03-morning.json`、後続有効形式は `2026-10-03/morning-v2.json`。旧形式のpayload・ID・時刻は変更していない。後続もreceipt欠落のため未完了であり、旧形式を成功した事前宣言へ変換しない。
