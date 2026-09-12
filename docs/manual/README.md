# 競馬予想ルール — モジュールマニフェスト

- **現行リリース**: `v1.6.1`
- **正本ディレクトリ**: `docs/manual/`
- **履歴管理**: Git の commit / pull request / tag を正本とし、`docs/manual/old/` は作成しない
- **入口**: ルールを利用・編集するときは、最初に必ず本 `README.md` を読む

## 1. 基本原則

このディレクトリの複数ファイルは、独立した文書ではなく**1つの競馬予想ルールシステム**として扱う。

1. 同じ概念を複数ファイルで定義しない。各概念には唯一の Owner を置く。
2. 他モジュールの定義を再掲せず、ルール番号・出力名・モジュール名で参照する。
3. Production は `00_core → 10_prediction → 20_conditional → 30_betting` の一方向で処理する。
4. `40_shadow` は Production 固定後に分岐し、Production へ逆流してはならない。
5. `50_review` は結果後の評価・昇格/降格・変更管理を担当し、当該レースの確定済み Production を遡及変更しない。
6. 必須モジュール間で `manual_release` が一致しない場合、予想・編集を開始しない。

## 2. モジュール一覧と Owner

| ファイル | Owner / 唯一の責務 | 主な出力 |
|---|---|---|
| `00_core.md` | 共通用語、実行モード、Production/Shadow境界、優先順位、標準フロー | 実行契約、基準予想ID運用、モード |
| `10_prediction.md` | オッズを見る前の能力・近走・展開・適性・確率・基準予想 | Production基準予想 |
| `20_conditional.md` | 当日補正・重賞51Aなど正式な条件別情報拡張 | Productionへ渡す正式補正・直接事実 |
| `30_betting.md` | 市場評価、①/②、券種、買い目、資金配分、購入前監査 | Production基準買い目 / 検証用固定資金案 |
| `40_shadow.md` | 51B、E系など未採用仮説の比較予想・比較買い目 | Shadow比較予想 / 比較買い目 |
| `50_review.md` | 回顧、誤差分類、検証サイクル、昇格/降格、変更履歴 | 回顧記録、改訂判断、KPI集計 |

## 3. 依存方向

```text
README
  ↓
00_core
  ↓
10_prediction
  ↓
20_conditional（該当時のみ）
  ↓
30_betting（購入判断時のみ）

Production固定後のみ
10_prediction / 20_conditional ──→ 40_shadow

結果確定後
Production + Shadow + 実購入 ──→ 50_review
```

**逆流禁止**：`30_betting → 10_prediction`、`40_shadow → Production`、`50_review → 過去のProduction` の書き戻しは禁止する。ルール自体の正式昇格は、`50_review` の審査を経た次回PRでのみ行う。

## 4. 依頼別の読み込み規約

| 依頼 | 必須 | 条件付き |
|---|---|---|
| 単一レースの事前予想 | `README`, `00_core`, `10_prediction` | 重賞・当日補正等なら `20_conditional` |
| 資金・券種を含む購入案 | 上記 + `30_betting` | 検証比較を行う場合のみ `40_shadow` |
| 今日の全レース選別 | `README`, `00_core`, `10_prediction`, `30_betting` | 条件該当レースのみ `20_conditional`; Shadow比較時のみ `40_shadow` |
| JRA重賞予想 | `README`, `00_core`, `10_prediction`, `20_conditional`, `docs/yosou/jra_racing/README.md` | 当該重賞記録があれば参照。購入なら `30_betting`; 51B比較なら `40_shadow` |
| レース後の回顧 | `README`, `00_core`, `50_review` | 元のProduction/買い目/Shadow記録を参照 |

毎回すべてのモジュールを読む必要はない。**依頼に必要なモジュールだけ読む**。

### JRA重賞の記録運用

JRA重賞は原則として全レースを予想対象とし、「見送り」は購入判断として扱う。

JRA重賞の保存・年度切替・チャット単位に関する詳細規約は `docs/yosou/jra_racing/README.md` を唯一のOwnerとする。

### 検証データの保存場所

進行中の検証サイクルで生成するShadow比較結果・検証集計は、ルール定義とは分離して `docs/validation/` に保存する。`docs/validation/` は**現行サイクル専用の一時領域**であり、ルールの正本ではない。サイクル終了時に必要な昇格・降格判断を `50_review.md` の手順で確定した後、当該サイクルの検証ファイルは削除し、過去状態はGit commit / pull request / tagから参照する。

## 5. 編集時の読み込み規約

変更対象モジュールの内部ロジックだけを変更し、`produces` / `depends_on` / `must_not_modify` を変えない場合は、原則として次だけ確認する。

- `README.md`
- 対象モジュール
- 対象モジュールが依存する上流モジュール

一方、モジュール間インターフェース、出力名、Production/Shadow境界、優先順位を変更する場合は、**直接依存する下流モジュールも必ず確認する**。

変更PRでは最低限、次を確認する。

- 同一概念の重複定義を追加していないか
- Ownerが変わる場合、旧Owner側の定義を削除したか
- ルール番号を不用意に変更していないか
- ProductionとShadowの逆流が発生していないか
- 必須モジュールの`manual_release`が一致しているか
- 良好部分保全 / 非劣化ガードに反していないか

## 6. 共通受け渡しキー

モジュール間では、少なくとも次を同一レースの共通キーとして扱う。

- `baseline_forecast_id`（基準予想ID）
- レースID / 開催日 / 競馬場 / R
- 情報取得時刻
- Production基準順位・確率・予想確信度
- 使用オッズ時刻（買い目作成時）

同じレースに既存のProduction基準予想IDがある場合、強い非価格情報による正式更新条件を満たさない限り、新しいProductionをゼロから作らない。

## 7. ルール番号と履歴

分割後も既存の `0.x`、`1〜51`、`E-xx` の番号を維持する。過去の予想・回顧から追跡できることを優先する。

旧版をファイルコピーで残さず、過去状態はGitのcommit / PR / tagから取得する。

## 8. GitHub運用

- 現行ルールの参照は原則として `main` の `docs/manual/README.md` から開始する。
- JRA重賞の記録運用は `docs/yosou/jra_racing/README.md` を正本とする。
- 改訂は作業ブランチで行い、pull requestの差分レビュー後に `main` へ統合する。
- 旧版確認はGitのcommit / PR / tagから行い、`old/`への複製保存はしない。
- ルールの意味を変更しない構造整理・記録運用整理では `manual_release` を維持できる。予想判断・閾値・決定権を変更する場合はリリース更新対象として `50_review.md` の更新規約に従う。
