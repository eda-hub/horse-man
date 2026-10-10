# 第2検証サイクル — U-02 ユーザー提供情報台帳

- **状態**: 進行中
- **開始日**: 2026-09-17
- **基準Production**: v1.6.1
- **詳細プロトコル**: `records/2026-09-17_user_supplied_evidence_protocol.md`
- **蓄積知見seed**: `records/2026-09-17_user_accumulated_heuristics_seed.md`
- **用途**: 現行サイクル内の実データ保存。恒久ルールの正本ではない

## 運用

予想前にユーザー提供情報を受け取った場合、**予想中は本台帳を更新しない**。ユーザー原文とProductionへの採否・影響先は発走前チャットで固定する。

結果後の回顧開始時に、発走時刻より前のチャット履歴から事前snapshotを抽出し、その時点で `user_evidence_id`、対象、claim、情報種別、元ソース、事前確認状態、Production利用有無を本台帳へ登録する。その後、同じ回顧作業内で factual validity、predictive relevance、decision contribution を記録する。

結果後に初めて得た情報はこの台帳の事前情報として遡及登録しない。発走前チャットを参照できない場合は結果から復元せず、そのレースは `PRE_RACE_SNAPSHOT_UNAVAILABLE` としてU-02前向き集計から除外する。

### BACKFILL_SEEDの扱い

2026-09-17に受領した過去蓄積の条件別知見40グループは、レース固有の発走前情報ではないため本台帳の「登録情報件数」へそのまま加えない。

- 原文カタログとして `records/2026-09-17_user_accumulated_heuristics_seed.md` に保存する。
- 該当レースで実際に使う場合は、結果確認前のチャットで採否・影響先が分かるように固定する。
- 回顧時に、その発走前チャットを根拠として原子的なclaimへ分解し、本台帳へ登録する。
- 過去レースへ遡って成功・失敗件数を付けない。

## Evidence ledger

| race / baseline | user_evidence_id | pre_race_chat_ref | 対象 | claim | evidence_type | upstream_source | precheck | production_usage | influence_area | factual_validity | predictive_relevance | contribution | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|

| 20260926-HAN-11 / MISSING_IN_INITIAL_SNAPSHOT | 20260926-SIRIUS-01 | 2026-09-26 pre-race chat | シリウスS | 差し有利 | INTERPRETATION | USER_ACCUMULATED_MEMO | CONFLICT | NOT_USED | pace | NOT_APPLICABLE | NEUTRAL | NOT_USED | 勝ち馬11・3着12は中団寄りから伸びた一方、2着9は前方で残り、2026年単年では一律の差し有利とは判定しない |
| 20260926-HAN-11 / MISSING_IN_INITIAL_SNAPSHOT | 20260926-SIRIUS-02 | 2026-09-26 pre-race chat | シリウスS | 関西馬優勢 | INTERPRETATION | USER_ACCUMULATED_MEMO | PARTIAL | NOT_USED | condition_fit | NOT_APPLICABLE | NEUTRAL | NOT_USED | 16頭中13頭が栗東で識別力が低く、勝ち馬11は美浦。所属単独の有効性は確認できない |
| 20260926-HAN-11 / MISSING_IN_INITIAL_SNAPSHOT | 20260926-SIRIUS-03 | 2026-09-26 pre-race chat | シリウスS | 前走4角4番手以内かつ1着の成績が良い | INTERPRETATION | USER_ACCUMULATED_MEMO | PARTIAL | NOT_USED | condition_fit | NOT_APPLICABLE | NEGATIVE | NOT_USED | 発走前に6を該当扱いしたのは事実誤認。6の直前走はマーキュリーC3着で、勝利は2走前。明確に確認した該当例3・14は2026年本番で馬券外。過去阪神開催6回では1-5-2-7・複勝53.3%のため仮説自体は継続検証 |
| 20260926-HAN-11 / MISSING_IN_INITIAL_SNAPSHOT | 20260926-SIRIUS-04 | 2026-09-26 pre-race chat | シリウスS | 前走上がり1位または2位で連対した馬の成績が良い | INTERPRETATION | USER_ACCUMULATED_MEMO | UNVERIFIED | NOT_USED | condition_fit | UNVERIFIABLE | UNRESOLVED | NOT_USED | 発走前に全頭同一定義での照合を完了しておらず、結果後に該当馬を作らない |
| 20260926-HAN-11 / MISSING_IN_INITIAL_SNAPSHOT | 20260926-SIRIUS-05 | 2026-09-26 pre-race chat | シリウスS | 前走1700〜2000m組が優勢 | INTERPRETATION | USER_ACCUMULATED_MEMO | PARTIAL | NOT_USED | condition_fit | NOT_APPLICABLE | POSITIVE | NOT_USED | 2026年上位3頭11・9・12はいずれも前走1700〜1800m。単年支持として保持し過去母数は別途再集計 |
| 20260926-HAN-11 / MISSING_IN_INITIAL_SNAPSHOT | 20260926-SIRIUS-06 | 2026-09-26 pre-race chat | シリウスS | 前走着差0.9秒以内だと成績が良い | INTERPRETATION | USER_ACCUMULATED_MEMO | PARTIAL | NOT_USED | condition_fit | NOT_APPLICABLE | NEGATIVE | NOT_USED | 勝ち馬11の前走は1.1秒差、2着9も前走大敗で厳格な0.9秒閾値外。2026年は強い反例 |

## 集計

| 指標 | 現在値 |
|---|---:|
| BACKFILL_SEED claim group | 40 |
| 前向き登録情報件数 | 6 |
| PRE_RACE_SNAPSHOT_UNAVAILABLE race | 0 |
| FACT | 0 |
| OBSERVATION | 0 |
| COMMENT | 0 |
| INTERPRETATION | 6 |
| FORECAST | 0 |
| VERIFIED | 0 |
| PARTIAL | 4 |
| UNVERIFIED | 1 |
| CONFLICT | 1 |
| factual CONFIRMED | 0 |
| factual REFUTED | 0 |
| predictive POSITIVE | 1 |
| predictive NEGATIVE | 2 |
| contribution HELPFUL | 0 |
| contribution HARMFUL | 0 |
| predictive NEUTRAL | 2 |
| predictive UNRESOLVED | 1 |
| contribution NOT_USED | 6 |

率を出す場合は分母を必ず併記し、少数サンプルの高率・低率だけで評価を変えない。

## サイクル終了時

情報種別 × 元ソース / origin group × 情報テーマ × 条件の単位で再現性を確認する。

- 再現性あり: 将来の確認優先度・evidence weight調整候補
- 条件依存: 適用条件を限定して継続検証
- 不明: 判断保留
- 悪化傾向: source取り違え、解釈飛躍、重複、観測タイミングを調査

Productionの正式な重み変更はこの台帳から自動実行せず、`50_review.md` の昇格基準に従って別審査する。


## 2026-09-26 シリウスS 過去傾向追加検証

- 差し有利: 過去10年は差し6勝だが複勝率は先行31.7% > 差し26.1%、追込5.9%。「差し一辺倒」ではなく脚質を細分化する。
- 関西馬優勢: 美浦複勝23.5%（4/17）、栗東19.8%（26/131）。出走構成を補正すると単独優位を確認できない。
- 前走4角4番手以内＋1着: 阪神開催6回で1-5-2-7、複勝53.3%。方向性は支持。ただし2026年発走前の6該当認識は誤り。
- 前走上がり1/2位: 1位複勝37.5%、2位35.0%で支持。「かつ連対」の複合母数は未確定。
- 前走1700〜2000m: 過去10年10勝、3着内28/30で強く支持。条件が広いため単独の選別力は別評価。
- 前走0.9秒以内: 負け馬では0.9秒以内複勝25.0%、1.0〜1.9秒8.3%。ただし2026年上位2頭が条件外のため足切りには使用しない。
- 正式Productionへの自動昇格: なし。サイクル終了審査まで補助仮説として保持。
