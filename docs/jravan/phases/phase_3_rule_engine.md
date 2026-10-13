# Phase 3 — v1.7.0 Feature / Production / Recommendation / Shadow

## 目的・依存

正式manualの非価格Predictionを維持し、順位由来印・価格不要Recommendation・固定後Shadowを実装する。Phase4の画面を前提にしない。PR79のチャット/Git/非UI運用とWindows/JRA-VANのAI非依存engine接続は別の実装受入。

## 対象と受入

全頭の根拠・確率・順位、cutoff、基準ID、旧新schema dispatch、個別保存と推奨を接続する。全Owner release一致、未来値拒否、Shadow/市場逆流禁止、オッズだけの基準再発行禁止、旧履歴不変を検査する。30_bettingの推奨は具体的組合せ・点数・状態・シナリオを持ち、実購入/予算を含めない。実DB/feature実行の接続・同一入力の再現性はPhase2受入後に独立検証する。
