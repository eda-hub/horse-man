# ChatGPT 最終予想タスク標準プロンプト

このテンプレートは、ChatGPTの予約タスク・通常チャットで最終予想と固定仮想買い目を実行するときの標準指示として使用する。

## 標準指示

horse-manリポジトリを使用し、対象レースの最終予想を行う。

- 実際の馬券購入は行わない。
- 予想本文を作る前に `persistence-intents/README.md` に従い、対象race_id、snapshot_id、実発走予定時刻を事前宣言する。宣言を同じ日次ブランチへ保存・read-backしてから予想を作成する。
- 買い判定の場合は、現行ルールに従い検証用の固定仮想買い目を作成する。
- 予想、買い目、判断理由、必要な監査結果を当該予想日の作業ブランチへ保存する。
- Production / BettingをFIXしたら、ユーザー向け回答より先に保存工程へ進む。
- 1レースごとに以下を完了してから次レースへ進む。
  1. 最新のsnapshot/preservation/receiptを同じ作業ブランチから取得する。
  2. FIX済み内容をsnapshotまたは時刻条件に応じたpreservationへ保存する。
     発走前snapshotには `prediction-scope-v1` を置く。保存前にFIX済みsection（`snapshot_section` が抽出する単位）のUTF-8 SHA-256を保持し、保存後の内容から作り直して一致したことにしない。
  3. 同じブランチからread-backし、artifact ID、race_id、印、固定買い目、各金額、合計金額、主要判断がFIX内容と一致することを確認する。
  4. persistence receiptを保存する。
  5. 同じブランチからreceiptをread-backし、artifact参照、保存commit、timing eligibility、保存状態の一致を確認する。
  6. 同じブランチから読戻したファイルへ `python3 scripts/verify_prediction_persistence.py --date YYYY-MM-DD --snapshot-id SNAPSHOT_ID --intent-id INTENT_ID --task-complete --fixed-content-sha256 FIXED_SECTION_SHA256` を実行する。宣言範囲・FIX内容・receipt・発走前確認時刻の全照合成功を完了条件にする。
- 本体とreceiptの両方をread-backし、直後機械確認に成功した場合だけ `TASK_PERSISTENCE_COMPLETE` とする。発走後preservationは内容保全として報告し、発走前保存完了にはしない。
- どちらかが未確認なら `TASK_PERSISTENCE_INCOMPLETE` とし、「保存済み」「完了」「記録完了」と報告しない。
- 書込失敗、stale SHA、競合、read-back不一致の場合は、最新ファイルを再取得し、**FIX済みの同じ内容を変更せず**再度保存する。
- 再試行時に他レースの既存追記を失わない。
- 同一ID・同一内容が存在する場合は重複追記せず再利用する。
- 同一ID・異内容の場合は上書きせず競合として扱う。
- 再取得を挟んだ再試行は原則2回までとし、発走前回答が危うい場合はfail-softする。ただし保存未完了を完了扱いにしない。
- 発走後に保存を再開する場合は、結果を見て予想・買い目を変更しない。発走前にFIX済みと追跡できる同一内容のみをLATE_PERSIST / preservationとして保全する。
- 結果確認後に新しい買い目を作成して、発走前にFIX済みだったものとして扱わない。

## 最終回答に必ず含める状態

各対象レースについて最低限、以下を表示する。

- prediction_status: FIXED / NOT_FIXED
- snapshot_status: PERSIST_VERIFIED / 各未完了状態
- receipt_status: RECEIPT_VERIFIED / 各未完了状態
- task_persistence_status: TASK_PERSISTENCE_COMPLETE / TASK_PERSISTENCE_INCOMPLETE

複数レースの場合、1レースでも `TASK_PERSISTENCE_INCOMPLETE` があれば「全レース保存完了」とは回答しない。

## 目的

予想内容の生成成功とGit永続化成功を混同しない。ChatGPTタスクの成功条件を、予想回答の生成ではなく、固定成果物を同一branchへ保存し、本体とreceiptをread-backして一致確認するところまでとする。
# PR79の次期保存準備（正式切替前）

現行manualの版を先に確認する。第4の準備契約・未定版を現行Productionへ適用しない。次期切替後の新規JSON予想は [第4の是正運用](../contracts/cycle04_operations.md) の宣言読戻し→独立FIX hash保存/読戻し→本体保存/読戻し→個別完了の順に実行する。既存Markdownや過去欠測は遡及修復しない。版・有効日未定なら `check_cycle04.py --require-active` は不合格として開始状態を説明する。

