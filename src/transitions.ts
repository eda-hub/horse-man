import { PROBABILITY_TOLERANCE } from "./constants.js";
import type { ForecastSnapshot } from "./schemas.js";
import type { ValidationIssue } from "./calculations.js";

const metrics = [
  "winProbability",
  "top2Probability",
  "top3Probability",
] as const;

export function validateForecastTransition(
  core: ForecastSnapshot,
  final: ForecastSnapshot,
): ValidationIssue[] {
  const issues: ValidationIssue[] = [];
  if (core.stage !== "core" || final.stage !== "final") {
    return [
      {
        severity: "error",
        code: "INVALID_TRANSITION",
        message: "CoreからFinalへの遷移だけを検証できます",
      },
    ];
  }
  if (core.raceId !== final.raceId) {
    issues.push({
      severity: "error",
      code: "TRANSITION_RACE_MISMATCH",
      message: "CoreとFinalのraceIdが一致しません",
    });
    return issues;
  }
  if (Date.parse(final.asOf) < Date.parse(core.asOf)) {
    issues.push({
      severity: "error",
      code: "TRANSITION_TIME",
      message: "Finalの情報基準時刻はCoreより前にできません",
    });
  }
  if (core.modules.length || core.experimentalAdjustments.length) {
    issues.push({
      severity: "error",
      code: "CORE_HAS_ADJUSTMENTS",
      message: "Core予想にModuleまたはExperimental補正を含めることはできません",
    });
  }

  const coreByRunner = new Map(
    core.horses.map((horse) => [horse.runnerNumber, horse]),
  );
  const recorded = new Map<string, number>();
  for (const adjustment of [
    ...final.modules,
    ...final.experimentalAdjustments,
  ]) {
    for (const delta of adjustment.deltas) {
      const key = `${delta.runnerNumber}:${delta.metric}`;
      recorded.set(key, (recorded.get(key) ?? 0) + delta.delta);
    }
  }
  for (const horse of final.horses) {
    const original = coreByRunner.get(horse.runnerNumber);
    if (!original) {
      issues.push({
        severity: "error",
        code: "TRANSITION_UNKNOWN_RUNNER",
        message: `Finalの馬番${horse.runnerNumber}がCoreに存在しません`,
      });
      continue;
    }
    for (const metric of metrics) {
      const actual = horse[metric] - original[metric];
      const declared = recorded.get(`${horse.runnerNumber}:${metric}`) ?? 0;
      if (Math.abs(actual - declared) > PROBABILITY_TOLERANCE) {
        issues.push({
          severity: "error",
          code: "UNRECORDED_ADJUSTMENT",
          message: `馬番${horse.runnerNumber}の${metric}変更${actual.toFixed(4)}と記録差分${declared.toFixed(4)}が一致しません`,
        });
      }
    }
  }
  const coreTop = [...core.horses].sort(
    (a, b) => b.winProbability - a.winProbability,
  )[0]?.runnerNumber;
  const finalTop = [...final.horses].sort(
    (a, b) => b.winProbability - a.winProbability,
  )[0]?.runnerNumber;
  if (
    coreTop !== finalTop &&
    final.modules.some((module) => module.evidenceStrength === "weak")
  ) {
    issues.push({
      severity: "warning",
      code: "WEAK_EVIDENCE_RANK_REVERSAL",
      message:
        "弱い証拠を含む補正で勝率1位が反転しています。変更根拠を再確認してください",
    });
  }
  return issues;
}
