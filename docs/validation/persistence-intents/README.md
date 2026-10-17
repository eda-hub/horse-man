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


## 保存拒否と発走時計の是正（2026-10-17、実装後の新規試行に適用）

正式レースでの発走前保存は次の順序を必須とする。未マージのPR・計画を既存本番で有効と自己申告しない。

1. 対象開催日とrace ID、公式scope、公式発走変更chain、日次branchと作業対象pathを確認する。実際のChatGPT/GitHub連携の権限と利用経路を確認する。未確認なら成功と表現しない。
2. 書込み直前・本体読戻し直後・receipt読戻し直後に、現在UTCを取得して `prediction_clock.py` / `verify_prediction_persistence.py --clock-status --date YYYY-MM-DD --clock-race-id RACE_ID` で判定する。第4運用入口は `cycle04_workflow.py --clock-status --date YYYY-MM-DD --clock-race-id RACE_ID`。JST表示、残秒、根拠、状態を返す。実時計が取れない環境では読取専用の計算値を用意できても、実測と混同せず時刻未判定とする。公式scopeと発走変更chainの読取りが終わった**後**に判定時計を新規取得する。取得前の時計を読取り後まで流用しない。時計が5秒超古い、オフセット/秒精度がない、monotonicとの乖離が2秒超、境界不明なら未判定。予定到達は実発走確認済みではない。
3. 正式intentは分析前にGit保存・固定commitから同一bytes読戻しする。FIX独立manifest→本体→receipt→個別検査の順序を守る。自己申告のreadback、ローカル保存、Actions成功だけで正式完了にしない。
4. 固定bytesとSHA-256を保持し、障害を `prediction_persistence_io.py` の拒否分類・操作記録に残す。権限/branch制約、SHA競合、通信/timeout、CI失敗、安全性拒否、理由不明を分ける。拒否された操作を別経路や高権限で迂回しない。通信系のみ、同一原本の遠隔読取り後に最大2回まで許可済みの保存を再試行する。独立した許可済み経路がなければ切替不可と明記する。
5. 実行環境にPythonと承認済みGitHub Contents API認証情報がある場合は、`python3 scripts/prediction_persistence_io.py --date YYYY-MM-DD --race-id RACE_ID --path RELATIVE_PATH --payload-file FIXED_FILE --operation-id UNIQUE_ID --write` を使用できる。同一bytesの既存原本はcommit固定で読戻し、再書込みせず存在確認済みとして扱う。固定原本と異なる内容は `--allow-update` を指定しても上書きせず、新しいrevision/pathで独立保存する。トークンや権限の自動取得・branch自動作成はしない。ChatGPTのGitHub連携利用時は同等の書込→返却commit固定読戻しを連携ツールで実行し、Pythonアダプター成功と取り違えない。
6. 失敗時は固定原本と秘匿済み障害記録を実行環境に保全し、GitHub正式保存は未完了と表示する。branch初期確認段階の拒否（HTTP 403等）でも `--local-incident` へ要求ID・応答分類・API到達状態を保存する。ローカルログ保存失敗も別途表示する。機密文字列を公開リポジトリに記録しない。事故記録の正式保存先は `docs/validation/persistence-incidents/YYYY-MM-DD/` だが、これは当時のreceiptを代替しない。旧データ・過去の証跡を遡及補完しない。

固定原本の保存前には `--race-id`、`--date`、日次branch、対象path、JSON本文のrace ID／開催日／発走予定を照合し、公式scope／発走変更chainから**当該レース**について取得した時刻判定のID・日付・予定時刻とも一致させる。11Rの原本に12Rの時計を使うこと、異なる日付・snapshot IDのパスへ固定することは不可。複数レースの一括intentは最早発走時刻と等しい公式時計を指定する。推奨の独立宣言は `docs/validation/recommendation-intents/YYYY-MM-DD/`、推奨認証は `docs/validation/recommendation-gates/YYYY-MM-DD/`、Prediction固定gateは `docs/validation/recommendation-prediction-gates/YYYY-MM-DD/` に限って新規原本保存を許可する。古い原本や同名gateを異内容上書きせず、新revision・historyによる別pathを使用する。

**ID互換・共有receiptの例外・障害記録復旧**：レースIDは `20261018-TOK-11`（TOK/KYO/NII短縮形式）と `2026-10-18-TOKYO-11`（TOKYO/KYOTO/NIIGATA長形式）を同じ開催日・場・レース番号へ正規化して照合する。異なるレースを混用してはならない。正式推奨は共有 `docs/validation/persistence-receipts/YYYY-MM-DD.md` へ、先行するR01および他レースのreceiptを**1 byteも変更せず**R02を新規追記する。CLIは共有ファイルの既存bytesに追加レコードを末尾連結した完成版を `--payload-file` に渡し、`--append-receipt --write` を明示する。既存blob SHAと原本bytesの両方を再照合し、整合する場合だけ条件付き更新し、返却commitの読戻しを実施する。R02の `previous_receipt_ref`、artifact、内容SHA、保存/読戻し時刻を一致確認する。R01など過去の固定証跡や推奨本体JSONへの変更は引き続き禁止。 `incident_record()` で生成した障害JSONはrace ID・開催日・branchを保持し、`persistence-incidents/YYYY-MM-DD/` へ復旧後（発走後を含む）に新規保存・読戻し可能。ただし事故記録の保全は発走前保存、receipt認証、KPI適格を代替しない。

時計判定・保存成功・読戻し一致・宣言/FIX順序・個別完了・正式KPIは独立した項目として表示する。現在の時計が発走後というだけで、過去の固定commitによる発走前保存を遅延へ書換えない。実チャット/予約/再開の経路試験は合成CIと別に記録する。安全性拒否の内部理由はログ未取得につき未確定のまま扱う。
