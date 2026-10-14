# Backup and recovery

## 目的
DB未経験でもWeb UIのsystem statusだけで保護状態を確認でき、Mac/VM/DB障害から復旧できること。

## バックアップ層
### 日次
Core Serviceが書込を安全に停止/flushし、DuckDBの論理ExportをParquetへ出力。manifestとSHA-256を生成する。保持14日。

### 週次
Windows VMを適切に停止した状態でVM保護。Snapshotは更新失敗のrollback用途であり、唯一のバックアップにはしない。保持8週を目安。

### 月次
Mac側または外付けストレージへ長期世代を退避。保持12か月を目安。

### Git
rules、設計、migration、コードはGit履歴で保護する。DBや秘密情報はGitへ入れない。

## Macへの退避
Parallels共有は原則OFFとし、必要なら `KeibaBackupDrop` のようなバックアップ専用共有だけ許可する。Mac側でTime Machine対象にする。

## RAW保持
RAWを一律永久保存しない。
- 重要/再取得困難速報: 長期保存
- 処理済みで再取得可能: 30-90日候補
- cache/一時ファイル: 削除可

## 復旧テスト
3か月に1度を目安に、新規DuckDBへIMPORTし、レース件数、FINAL予想の順位・確率・印・根拠、結果、回顧が参照できるか確認する。旧releaseの買い目・実購入・仮想精算履歴が存在する場合は、旧契約のread-only履歴として参照可能であることも確認する。

## ops.backup_run
開始/終了、対象、出力先、hash、検証結果、errorを記録し、Web UIへ表示する。
