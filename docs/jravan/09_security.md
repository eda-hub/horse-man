# Security design

## Windows VM
Windows 11 VMはJRA-VAN専用アプライアンスとして運用する。
- Defender / Firewall / SmartScreen ON
- Secure Boot / vTPM ON
- 可能ならBitLocker
- 管理者アカウントと通常実行アカウントを分離
- 日常Web閲覧、メール、Office用途に使わない
- RDP、Remote Assistance、SMB共有、Network Discovery、WinRM等は不要ならOFF

## Network
- Bridgedを基本的に使わない
- InternetからFastAPIへ到達させない
- Port forwardingしない
- FastAPIはMacからアクセス可能なParallels側アドレスに限定
- Windows Firewallでも送信元をMacへ限定

## Python
- プロジェクト専用venv
- 依存パッケージを最小化・lock
- 不明なGitHubリポジトリから直接pip installしない
- 定期的に既知脆弱性監査
- 本番環境へJupyter等の不要な開発サービスを常駐させない

## Secrets
API key等をソースコードへ書かない。Gitignore対象のlocal secret store / Credential Manager等を使用する。

## Database
- DuckDB writeはCore Serviceのみ
- Web UIから任意SQLを実行させない
- 入力値Validation
- FINAL/history系はapplication layerで更新/削除禁止

## AI
AIにDB、ファイル、OSコマンドの直接権限を渡さない。AIへ送るデータはReview Packageに限定し、認証情報を含めない。

## 投票系
PAT、銀行情報、投票認証情報を一切保持しない。
