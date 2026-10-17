# 10月17日 発走前保存の代替証拠回収

## 回収結果

これはレース終了後に行った証拠回収。事前receiptの新規発行ではない。
GitHub REST APIのworkflow runのhead SHA・repository・pushイベント・created_atと、そのSHAに含まれる原本bytesを結び付けた。
コミットに自己申告された日時だけでなくGitHub側の生成時刻を用いる。runの成否は存在確認の条件ではない。

| レース | 宣言のGitHub時刻 | 独立FIXのGitHub時刻 | 本体のGitHub時刻 | 発走予定 |
| --- | --- | --- | --- | --- |
| 新潟11R | 15:07:51 | 15:08:28 | 15:12:13 | 15:15 |
| 京都11R | 15:16:42 | 15:20:38 | 15:20:41 | 15:30 |
| 東京11R | 15:31:26 | 15:33:47 | 15:33:50 | 15:45 |

すべて2026年10月17日のJST。対象9原本の当時bytesと現在bytes、およびFIX内の本体・宣言ハッシュが一致する。
京都11R・東京11Rは「宣言サーバ時刻≦FIX時刻≦FIXサーバ時刻≦本体サーバ時刻」が整合する。
新潟11Rの宣言サーバ時刻はローカルFIX 15:04:45より後で、この順序の証明には使えない。

## 保存場所と再検査

- API観測抜粋・run URL・head SHA・原本path/hash・取得時刻：`2026-10-17-github-witnesses.json`
- 読取専用の照合結果：`2026-10-17-github-witness-report.json`
- 検査：`python3 scripts/check_github_presence_witness.py`
- 回帰：`python3 scripts/test_github_presence_witness.py`

検査はGitからの過去原本読出し、現在bytes、SHA256、宣言→FIX→本体の内容対応、runの同一commit/repository/branch/event、発走前のサーバ時刻を確認する。
保存した観測を再取得する場合は各`api_url`からGitHub APIで取得し、特にid/head_sha/event/repository/created_atを再照合する。
ローカル検査だけでは保存済みAPI応答の真正性自体は独立認証できないため、観測元URLを保持する。

## 代替証拠の受入範囲

本資料で受け入れるのは「当該bytesを含むcommitが発走前にGitHubへ存在した」という補強事実のみ。
workflow開始は、作業者が宣言/FIXを読戻して内容一致を確認した証明ではない。
検査は読戻し成功や正式KPI適格を生成せず、既存のreceipt・gate・不適格判定を変更しない。
全36Rの初回予想、未作成の推奨原本、公式scopeはこの証拠から復元できない。

v1.7.0の正式受入条件へ代替証拠を採用する変更は本対応には含まない。
正式適格性を変更するには、Ownerによる条件審査と別のルール変更PRが必要で、過去の読戻しが実施済みだったとの認証は行わない。
日次索引から本資料を辿れるよう接続し、従来の工程不足もそのまま保持する。
