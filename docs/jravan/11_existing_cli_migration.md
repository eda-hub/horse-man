# Existing TypeScript CLI compatibility and migration

現在の `horse-man` はNode.js/TypeScript CLIとして、予想、strategy、purchase、result、review、cycle等をJSON記録している。この資産を新システム移行時の比較基準として使う。

## 原則
- Phase 0-2で既存CLIのコマンドやrecords契約を壊さない。
- `競馬予想ルール原本_v1.4.1.md` のSHA検証思想を新システムでも継承する。
- FINAL revisionの上書き拒否思想をDuckDBのprediction historyにも継承する。
- Web UI完成までは既存CLIをfallbackとして利用可能にする。

## 段階移行
1. Python Coreをside-by-side追加。
2. 同じfixtureをTypeScript CLIとPython側へ流し、主要項目を比較。
3. DB側のFINAL snapshot exportから既存JSON相当を生成できるようにする。
4. Web UIが安定後、CLIを管理/diagnostic用途として残すか統合するか判断。

## 禁止
- 初期Phaseで`src/`を全面書換えしない。
- 既存recordsをmigration検証なしでDuckDBへ一括変換しない。
- 原本ルールを機械変換結果で上書きしない。
