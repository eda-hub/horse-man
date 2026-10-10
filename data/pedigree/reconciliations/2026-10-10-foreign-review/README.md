# 海外4レースの個体・5代血統照合

全42登録行（38出走・4取消）の本人同定と必要5代血統をRegistryへ保存し、2,604祖先位置を保存後に読み戻して照合した。batch-01〜12.jsonに原文・取得時刻・hash・CAS receipt・過去cutoffの証跡を保存した。残り0行。

最初の3レースは既存公式原票の生年・父母母父と別サイト血統表を照合。YorkはJBIS本人プロフィール・5代表で同定し、収録がある8頭はnetkeiba表を使用、Devil’s AdvocateはJBIS表を使用した。同名Saddadの別個体候補を棄却した記録と、Bravour / Bravour II、Hat Trick / ハットトリックの独立ID・生年による表記照合も保持する。

既存の個体・revision・結果原票を保持。REPLAY専用で、海外結果を含む全条件集計・Production採用の完了は意味しない。検証はscripts/check_foreign_pedigree_review.py。

## 先頭5行完了時の履歴

先頭5登録行（Daryz、Bay City Roller、Diamond Necklace、Friendly Soul、Kalpana）を公式の生年・父母母父と本人名・別サイト独立IDで照合し、各62位置を既存Registryへ追記した。36個体を追加、58親子revisionを追加、310位置を保存後にreadback確認。既存個体・親子関係は保持し、同名祖先の既存別IDは検証済み子の親と本人名・生年が一致する場合にcrosswalkだけで既存正本へ対応付けた。旧IDを削除・付け替えない。

全42登録行＝38出走＋4取消の原票と母数は不変。残37行は未照合。原HTML応答bytes/hash・取得時刻、公式根拠、対応表、Writer receipt、過去cutoffをbatch-01.jsonとsources-batch-01.json.gzへ保存。REPLAY専用。全海外coverage・全条件再集計・Production利用可能を主張しない。
