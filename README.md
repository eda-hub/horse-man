# horse-man

JRA-VAN Data Lab を利用し、個人のMacからWeb UIで操作するローカル競馬予想・記録・回顧システムです。

現在は実装前の設計フェーズです。競馬判断の正本は `競馬予想ルール原本_v1.4.1.md`、システム設計の正本は `DECISIONS.md` と `docs/jravan/` です。

## 目標

- Windows 11 VM上のJV-LinkからJRA-VANデータを取得
- DuckDB + Parquetへ蓄積
- MacのブラウザからPRE / DAY / FINAL予想を確認
- 最終オッズを予測して馬連・ワイド中心の買い目候補を生成
- ユーザーが購入 / 見送りを判断
- 見送りを含む全FINAL予想を保存・結果精算・回顧
- AIは回顧、仮説生成、ルール改善候補の作成に使用
- バックアップと結果記録を自動化

## 設計書

`docs/jravan/README.md` から参照してください。

## 実装

Codexは `AGENTS.md` と `docs/jravan/phases/` を読み、Phase 0から順番に実装します。

`.agents/` と `.devcontainer/` はCodex利用のため維持します。

自動投票、PAT連携、銀行情報の保存、公開Webサービス化は対象外です。
