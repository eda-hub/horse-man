# 運用是正 受入試験 — 2026-09-21

- 対象: PR #35で実装した発走前snapshot保存・回顧scope・WIN5時点監査
- 種別: **運用手順の受入試験**
- 実レース証跡: **使用しない**
- Production / KPI: **算入しない**
- 実施branch: `docs/operation-corrective-plan-reassessment-20260920`
- 正規運用先 `main` での実レース保存確認: **PRマージ後の前向き運用で確認する**

## 1. 正常系 — Git保存と読戻し

### 入力

この試験記録ファイル自体を実装branchへ保存し、保存commitを指定して同じファイルを再取得する。

### 期待

- 保存commitが取得できる。
- 再取得した本文に本試験ID `OA-20260921-01` が存在する。
- 保存内容を別の値へ再生成せず、同一内容として確認できる。

### 実際

- test_id: `OA-20260921-01`
- 初回保存commit: `4c22cbd2975ae4000da7901d899f8e4f4f9e60e0`
- 読戻し: commit指定・branch指定の双方で `OA-20260921-01` を確認
- 判定: **PASS**

## 2. 保存失敗 — fail-soft机上試験

- test_id: `OA-20260921-02`
- 入力: 正式FIXED後、Git書込が権限不足または時間切れで失敗したものとする。
- 期待:
  - Production内容を発走前にチャットへ返す。
  - `PRE_RACE_SNAPSHOT_PERSIST_FAILED` を明示する。
  - 後付け保存を「発走前保存済み」へ変更しない。
  - Git永続化必須KPIだけを不適格とし、Shadow等の別KPIへ無条件に波及させない。
- 実際: `00_core.md` 1 / 1.1 と `snapshots/README.md` 6 の分岐が上記を要求する。
- 判定: **TABLETOP_PASS**

## 3. 読戻し失敗 — 参照失敗机上試験

- test_id: `OA-20260921-03`
- 入力: 書込応答は成功したが、正規参照先から同一 `snapshot_id` を読戻せないものとする。
- 期待:
  - 保存成功扱いにしない。
  - `PRE_RACE_SNAPSHOT_READBACK_FAILED` を明示できる。
  - 基準予想や買い目を記憶から再生成しない。
  - 発走前回答を遅らせずfail-softする。
- 実際: `00_core.md` と `snapshots/README.md` の読戻し完了条件・引継ぎ契約が上記を要求する。
- 判定: **TABLETOP_PASS**

## 4. 再送とID衝突 — 机上試験

| ケース | 入力 | 期待 | 判定 |
|---|---|---|---|
| 同一ID・同一内容 | 同じsnapshotを再送 | 重複追記せず既存snapshotを再利用 | TABLETOP_PASS |
| 同一ID・異なる内容 | 同じIDで順位等が異なる | `SNAPSHOT_ID_CONFLICT`、上書き禁止 | TABLETOP_PASS |
| 正式訂正 | 旧内容を修正したい | 新snapshot + `previous_snapshot_ref` | TABLETOP_PASS |

## 5. 同日競合 — 机上試験

- test_id: `OA-20260921-05`
- 入力: 別チャットが同日ファイルへ先に追記し、手元のblob SHAが古くなったものとする。
- 期待:
  - 最新内容を再取得する。
  - 他チャットの追記を保持する。
  - 最大1回のみ再試行する。
  - force更新しない。
  - 競合未解決なら保存成功としない。
- 判定: **TABLETOP_PASS**

## 6. scope集合 — 机上試験

- test_id: `OA-20260921-06`
- 入力: `prediction_scope_count=16`、recordも16行だが、race_id Aが2回、race_id Bが欠落。
- 期待: 件数一致でも集合不一致・重複1件として `REVIEW_SCOPE_MISMATCH`。
- 判定: **TABLETOP_PASS**

## 7. Production / Shadow順序 — 机上試験

- test_id: `OA-20260921-07`
- 入力: Production予想固定後に予想Shadowを作成し、その後Production買い目、最後に買い目Shadowを作成する。
- 期待:
  - `FINAL_PRODUCTION_FIXED`
  - `PREDICTION_SHADOW_COMPLETE/PARTIAL`
  - `BETTING_AUDIT_COMPLETE`
  - `BETTING_FIXED`
  - `BETTING_SHADOW_COMPLETE/PARTIAL`
  の段階が混同されない。
- 判定: **TABLETOP_PASS**

## 8. WIN5時点監査 — 机上試験

- test_id: `OA-20260921-08`
- 入力: WIN5判断14:07、通常Production最終更新14:21以降。
- 期待: 14:21以降の確率を14:07の候補切り違反確定へ遡及利用しない。14:07時点の比較値がなければ「根拠未確認」とする。
- 判定: **TABLETOP_PASS**

## 9. 残る前向き確認

本試験は文書契約の分岐とGit上の専用試験ファイル保存を確認するものであり、実レースでの恒久効果を証明しない。PRマージ後に少なくとも次を前向きに記録する。

- `main` への発走前snapshot保存・読戻し成功
- 保存開始〜読戻し確認までの所要時間
- 再試行数
- 別チャットからのbaseline / snapshot再取得
- 回顧時のrace_id集合・重複・snapshot参照・実購入明細合計
