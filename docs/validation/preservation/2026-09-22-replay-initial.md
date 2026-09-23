# 2026-09-22 全12R Replay初回予想

- execution_date: 2026-09-23 JST
- target_date: 2026-09-22
- venue: 第4回中山7日
- working_branch: `prediction/2026-09-22`
- manual_release: `v1.6.1`
- manual_ref_commit: `063b23d444938730fe7ad8cb93e9574751e51ec7`
- mode: `REPLAY`
- timing_route: `LATE_PRESERVATION`
- result_usage: `PROHIBITED`
- source_production: `docs/validation/snapshots/2026-09-22.md` の発走前Production
- execution_gate_schema: `prediction-compliance-v1`

Replay初回工程では、9月22日に発走前固定されたProductionを再利用し、結果・払戻・確定着順を入力へ使用しない。全12Rを初回scopeとし、検証候補・購入候補を抽出する。

## 初回予想

| R | Production上位 | 確信度 | 初回選別 |
|---|---|---:|---|
| 1R | ◎14グランナヴィール ○9アバットゥータ ▲2カルマンフィルター | C | 見送り |
| 2R | ◎8バタフライ ○9ニシノムホウモノ ▲4スペシャルサンクス | C | 見送り |
| 3R | ◎5ドナビッグベン ○3ソウラスフロス ▲4シュアシング | C | 見送り |
| 4R | ◎4キャピタルストーン ○7ドナリー ▲3アニエーネ | C | 検証候補 |
| 5R | ◎2ローズサルーテ ○1ビーハッピーデイ | D | 見送り |
| 6R | ◎5テンポアニマート ○3ヤマメゴリュウ ▲1ネオロマーネ | D | 見送り |
| 7R | ◎7ユアフェリシティ ○1サムシングニュー ▲3タケルムサシ | B | 購入候補 |
| 8R | ◎7マーゴットソラーレ ○5メアヴィア ▲12イモータリス | C | 検証候補 |
| 9R | ◎3パースウェイド ○6フィールオーサム ▲5サファイアテソーロ | B | 購入候補 |
| 10R | ◎5デイトナチャンプ ○2レッドレナート ▲6セブンマイスター | B | 購入候補 |
| 11R | ◎12リフレックス ○5サノノワンダー ▲3ディーズゴールド ☆2キョウエイフロイデ | B | 購入候補 |
| 12R | ◎3フュルスティン | C | 検証候補 |

## scope

- initial_scope: `20260922-NAK-01`, `20260922-NAK-02`, `20260922-NAK-03`, `20260922-NAK-04`, `20260922-NAK-05`, `20260922-NAK-06`, `20260922-NAK-07`, `20260922-NAK-08`, `20260922-NAK-09`, `20260922-NAK-10`, `20260922-NAK-11`, `20260922-NAK-12`
- validation_candidates: `20260922-NAK-04`, `20260922-NAK-08`, `20260922-NAK-12`
- purchase_candidates: `20260922-NAK-07`, `20260922-NAK-09`, `20260922-NAK-10`, `20260922-NAK-11`
- selected_final_scope: `20260922-NAK-04`, `20260922-NAK-07`, `20260922-NAK-08`, `20260922-NAK-09`, `20260922-NAK-10`, `20260922-NAK-11`, `20260922-NAK-12`

## 選別根拠

- 1R〜3R: 確信度Cで初回見送り。
- 4R: 馬場適性・直前情報の確認価値があり検証候補。
- 5R・6R: 新馬戦で実戦情報が乏しく確信度D。価格だけで購入候補へ上げない。
- 7R: 確信度Bで購入候補。
- 8R: 馬場適性・当日状態の確認価値があり検証候補。
- 9R〜11R: 確信度Bで購入候補。
- 12R: 比較材料不足を残すため購入候補へ上げず検証候補。

## 機械ゲート

各race_idについて `docs/validation/execution-gates/2026-09-22/<race_id>.json` を作成する。

- replayのためProduction KPIは `INELIGIBLE`。元Productionが発走前に存在していても、現行機械ゲートが要求するreceipt証跡がないため適格化しない。
- replayで新たに生成するShadowは `INELIGIBLE`。
- 4R・7R・8R・9R・10R・11R・12Rは最終工程が未実施のためBetting KPIを `PENDING`。
- その他は初回見送りのためBetting KPIを `NOT_APPLICABLE`。
- E-11は現行尺度矛盾を解消していないため `PENDING_RULE_CONFLICT` のまま固定する。

## 次工程

最終予想は selected_final_scope の7レースだけを対象とし、初回12Rとの件数一致を要求しない。
