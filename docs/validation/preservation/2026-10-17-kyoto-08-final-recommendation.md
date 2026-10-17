# 2026-10-17 京都8R（もみじステークス）最終予想に付随する推奨メモ

- 予想時点: 2026-10-17 13:34 JST（対象の発走予定13:45）。
- 正式Production原本: `docs/validation/snapshots/2026-10-17/20261017-KYOTO-08-FINAL-S01.json`
- 独立FIX: `docs/validation/fix-manifests/2026-10-17/20261017-KYOTO-08-FINAL-S01.json`
- 予想原本SHA-256: `10f9021d1746e795e5534323046a55d7b2f2a7e6083f05028fddfe30cec05064`
- 発走前保存: 本体・独立FIX・receiptは同日branchで保存・読戻し済み。
- 本体実行ゲート: `docs/validation/execution-gates/2026-10-17/2026-10-17-KYOTO-08.json`。正式KPIは未認証・保留。

## 購入候補としてユーザーに提示した案
- **ワイド 3 アンムート－6 カレンハウ、1点**。
- 3と6は2026-08-08ダリア賞の2着・3着で、芝1400mオープンの直接実走比較が存在する。
- 確信度はC。3の1着固定はしない。両馬が同時に3着内から外れるケース、7の良馬場での巻き返し、先行勢の競り合いが失敗条件。
- オッズは能力順位・印の決定に使用しない。最終確定値や期待値に応じた券面増減は行っていない。
- 実投票・実購入・購入金額は未確認。自動投票は行っていない。

## 保存契約上の境界
このファイルは推奨について会話時に提示した内容を保全する補助メモであり、正式`odds-free-recommendation-v1`本体や独立保存・推奨gateを**代替しない**。当該Prediction事前宣言に別推奨scopeを含めていなかったため、正式推奨としての`recommendation.py --prepare/--generate/--seal`は未実施。後から事前宣言を改ざん・遡及作成せず、推奨KPIは保留にする。

## 追加の未完了
- `run_release_readiness.py --require-main`の手元実行
- 公式scopeのCLI登録および第4サイクル日別台帳への接続
- `verify_prediction_persistence.py --task-complete --intent-id ... --fixed-content-sha256 ...`と`task_completion.py`の機械照合
- 適用Shadowの前向き固定・正規判断
- 推奨原本の独立記録・機械照合
GitHub保存と読戻しが成立したことを、これらの受入完了・正式KPI適格へ転用しない。

## 直接出所
- JRA公式出馬表: https://app.jra.jp/JRADB/accessD.html?CNAME=sw01dde0108202604060820261017%2F2E
- 追い切り: https://race.sp.netkeiba.com/?pid=oikiri&race_id=202608040608&rf=multimenu
