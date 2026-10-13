# 30番：確率の中心値・根拠区分・不確実性表示

既存8券種比較の probability_method / probability / calibrated_lower_bound / calibration_ref を読取表示する。Predictionの確率生成、順位、印、保存原本、価格不要推奨の生成条件を変更しない。任意市場の価格取得は前提にしない。

| 既存区分 | 表示 | 中心値 |
|---|---|---|
| MISSING | 未算定 | nullを未算定と表示、0へ補完しない |
| UNCALIBRATED | 未校正 | 有限の0〜1を百分率で表示 |
| DISCRETIONARY | 裁量評価 | 有限の0〜1を百分率で表示 |
| CALIBRATED | 校正済みの区分 | 既存契約の校正参照が必要。参照の存在を証跡認証の完了へ読み替えない |

probability_range は任意の表示補助。未指定/nullは範囲未算定として扱う。指定時は下端≦中心値≦上端、各値は0〜1の有限数。未算定の項目に範囲を付けない。boolean、非数、無限値、逆転範囲、中心値を含まない範囲は拒否する。

未校正/裁量レンジの下端を統計下限と呼ばない。CALIBRATEDでもレンジ下端を calibrated_lower_bound へ自動転記しない。明示した下限だけを別項目として表示し、0≦下限≦中心値を検査する。未校正・裁量に校正済み下限を付ける入力は拒否する。

入力に確率区分がない場合は推測せず検査失敗。表示処理は入力dictや原本JSONを書き換えない。表示の成功は実レース校正、性能昇格、独立artifact/receipt認証の成功ではない。

## 使用入口

- scripts/probability_presentation.py の describe：既存比較券の確率項目を日本語へ変換。
- 同 describe_comparison：既存8券種比較の検査を通して対象券別に表示。
- 同CLI：`python3 scripts/probability_presentation.py <比較券JSONのpath>`。読取専用で中心値・根拠・範囲・別下限・校正参照を表示。
- 同 describe_production/CLI：既存Productionまたはgate JSONの全頭勝率・連対率・3着内率を読取表示。既存全頭確率には校正区分/レンジの正式項目がないため「原本に記録なし」と示す。比較券の区分をProductionへ移植せず、0を未算定へ変換しない。欠測のProduction確率は現行契約どおり拒否する。
- cycle04_operations.validate_ticket_comparison：同じ検査へ接続し、表示だけで不正な範囲が通ることを防止。

## 受入と継続検証

30-01は中心値と既存根拠区分の対応、30-02はnullと0%、30-03は範囲・下限分離と不正入力拒否を検査。新規15回帰に正常・異常、CLI読戻し、既存比較入口、不変性を含む。実測の確率校正・性能評価は未実施で継続検証。29の実測待ちを前提にしない。

実施記録は implementation/2026-10-13-task30.json。計画と進捗の正本はPR68の番号付き実施計画。
