import { PROBABILITY_TOLERANCE } from "./constants.js";
import type {
  BetStrategy,
  ForecastSnapshot,
  RaceDossier,
  Ticket,
} from "./schemas.js";

export type ValidationIssue = {
  severity: "error" | "warning";
  code: string;
  message: string;
};

const sum = (values: readonly number[]): number =>
  values.reduce((total, value) => total + value, 0);
const nearlyEqual = (actual: number, expected: number): boolean =>
  Math.abs(actual - expected) <= PROBABILITY_TOLERANCE;

export function fairOdds(probability: number): number | undefined {
  return probability > 0 ? 1 / probability : undefined;
}

export function expectedValue(
  probability: number,
  decimalOdds: number,
): number {
  return probability * decimalOdds - 1;
}

export function validateForecast(
  forecast: ForecastSnapshot,
  dossier?: RaceDossier,
): ValidationIssue[] {
  const issues: ValidationIssue[] = [];
  if (
    forecast.stage === "core" &&
    (forecast.modules.length || forecast.experimentalAdjustments.length)
  ) {
    issues.push({
      severity: "error",
      code: "CORE_HAS_ADJUSTMENTS",
      message: "Core予想にModuleまたはExperimental補正を含めることはできません",
    });
  }
  const runnerNumbers = forecast.horses.map((horse) => horse.runnerNumber);
  const uniqueRunners = new Set(runnerNumbers);
  if (uniqueRunners.size !== runnerNumbers.length) {
    issues.push({
      severity: "error",
      code: "DUPLICATE_RUNNER",
      message: "予想内の馬番が重複しています",
    });
  }

  if (dossier) {
    const dossierRunners = new Map(
      dossier.runners.map((runner) => [runner.number, runner.name]),
    );
    if (forecast.raceId !== dossier.race.id) {
      issues.push({
        severity: "error",
        code: "RACE_MISMATCH",
        message: "予想とレース情報のraceIdが一致しません",
      });
    }
    for (const horse of forecast.horses) {
      const expectedName = dossierRunners.get(horse.runnerNumber);
      if (!expectedName) {
        issues.push({
          severity: "error",
          code: "UNKNOWN_RUNNER",
          message: `馬番${horse.runnerNumber}はレース情報に存在しません`,
        });
      } else if (expectedName !== horse.name) {
        issues.push({
          severity: "error",
          code: "RUNNER_NAME_MISMATCH",
          message: `馬番${horse.runnerNumber}の馬名がレース情報と一致しません`,
        });
      }
    }
    if (forecast.horses.length !== dossier.runners.length) {
      issues.push({
        severity: "error",
        code: "RUNNER_COUNT_MISMATCH",
        message: "予想は出走馬全頭の確率を含める必要があります",
      });
    }
    if (Date.parse(forecast.asOf) > Date.parse(dossier.race.scheduledStart)) {
      issues.push({
        severity: forecast.provenance === "prospective" ? "error" : "warning",
        code: "AFTER_START_TIME",
        message: "情報基準時刻が発走予定時刻より後です",
      });
    }
  }

  const expectedTop3Total = Math.min(3, forecast.horses.length);
  const totals = [
    ["WIN_TOTAL", sum(forecast.horses.map((horse) => horse.winProbability)), 1],
    [
      "TOP2_TOTAL",
      sum(forecast.horses.map((horse) => horse.top2Probability)),
      Math.min(2, forecast.horses.length),
    ],
    [
      "TOP3_TOTAL",
      sum(forecast.horses.map((horse) => horse.top3Probability)),
      expectedTop3Total,
    ],
  ] as const;
  for (const [code, actual, expected] of totals) {
    if (!nearlyEqual(actual, expected)) {
      issues.push({
        severity: "error",
        code,
        message: `確率合計が不整合です（実際=${actual.toFixed(4)}, 期待=${expected.toFixed(4)}）`,
      });
    }
  }

  for (const horse of forecast.horses) {
    if (!(
      horse.winProbability <= horse.top2Probability &&
      horse.top2Probability <= horse.top3Probability
    )) {
      issues.push({
        severity: "error",
        code: "PROBABILITY_ORDER",
        message: `馬番${horse.runnerNumber}は 勝率 <= 連対率 <= 3着内率 を満たしていません`,
      });
    }
    if (
      horse.winProbability < horse.winRange.low ||
      horse.winProbability > horse.winRange.high
    ) {
      issues.push({
        severity: "error",
        code: "RANGE_CENTER",
        message: `馬番${horse.runnerNumber}の中心勝率が不確実性レンジ外です`,
      });
    }
  }

  const markCounts = new Map<string, number>();
  for (const horse of forecast.horses) {
    markCounts.set(horse.mark, (markCounts.get(horse.mark) ?? 0) + 1);
  }
  for (const mark of ["◎", "○", "▲"]) {
    if ((markCounts.get(mark) ?? 0) > 1) {
      issues.push({
        severity: "error",
        code: "DUPLICATE_MARK",
        message: `${mark}は複数頭に付けられません`,
      });
    }
  }
  if ((markCounts.get("◎") ?? 0) !== 1) {
    issues.push({
      severity: "error",
      code: "MISSING_PRIMARY_MARK",
      message: "◎は必ず1頭に設定してください",
    });
  }

  const topHorse = [...forecast.horses].sort(
    (a, b) => b.winProbability - a.winProbability,
  )[0];
  if (topHorse?.mark !== "◎") {
    const hasConcern = Boolean(forecast.subjectiveConcern?.trim());
    issues.push({
      severity: hasConcern ? "warning" : "error",
      code: "MARK_WIN_RANK_MISMATCH",
      message: hasConcern
        ? "勝率1位と◎が異なります。subjectiveConcernを監査理由として記録しました"
        : "勝率1位と◎が異なる場合は、オッズ以外の理由をsubjectiveConcernに記録してください",
    });
  }

  const scenarioTotal = sum(
    forecast.scenarios.map((scenario) => scenario.probability),
  );
  if (!nearlyEqual(scenarioTotal, 1)) {
    issues.push({
      severity: "error",
      code: "SCENARIO_TOTAL",
      message: `シナリオ発生確率の合計は1である必要があります（実際=${scenarioTotal.toFixed(4)}）`,
    });
  }
  const scenarioIds = new Set<string>();
  for (const scenario of forecast.scenarios) {
    if (scenarioIds.has(scenario.id)) {
      issues.push({
        severity: "error",
        code: "DUPLICATE_SCENARIO",
        message: `シナリオID ${scenario.id} が重複しています`,
      });
    }
    scenarioIds.add(scenario.id);
    const scenarioValues = Object.values(scenario.runnerWinProbabilities);
    if (!nearlyEqual(sum(scenarioValues), 1)) {
      issues.push({
        severity: "error",
        code: "SCENARIO_RUNNER_TOTAL",
        message: `シナリオ ${scenario.id} の各馬勝率合計は1である必要があります`,
      });
    }
    for (const runner of uniqueRunners) {
      if (scenario.runnerWinProbabilities[String(runner)] === undefined) {
        issues.push({
          severity: "error",
          code: "SCENARIO_MISSING_RUNNER",
          message: `シナリオ ${scenario.id} に馬番${runner}の勝率がありません`,
        });
      }
    }
  }

  for (const horse of forecast.horses) {
    const weighted = sum(
      forecast.scenarios.map(
        (scenario) =>
          scenario.probability *
          (scenario.runnerWinProbabilities[String(horse.runnerNumber)] ?? 0),
      ),
    );
    if (!nearlyEqual(weighted, horse.winProbability)) {
      issues.push({
        severity: "warning",
        code: "SCENARIO_WEIGHT_MISMATCH",
        message: `馬番${horse.runnerNumber}のシナリオ加重勝率${weighted.toFixed(4)}と最終勝率${horse.winProbability.toFixed(4)}が異なります`,
      });
    }
  }

  const evidenceIds = new Set(
    dossier?.evidence.map((evidence) => evidence.id) ?? [],
  );
  for (const adjustment of forecast.modules) {
    if (
      adjustment.module === "live-track" &&
      adjustment.evidenceIds.length < 2
    ) {
      issues.push({
        severity: "warning",
        code: "LIVE_TRACK_EVIDENCE",
        message: "Live馬場Moduleは複数の根拠を必要とします",
      });
    }
    for (const id of adjustment.evidenceIds) {
      if (dossier && !evidenceIds.has(id)) {
        issues.push({
          severity: "error",
          code: "UNKNOWN_EVIDENCE",
          message: `根拠ID ${id} がレース情報に存在しません`,
        });
      }
    }
  }
  return issues;
}

function ticketWeight(ticket: Ticket, mode: "yen" | "ratio"): number {
  return mode === "yen" ? (ticket.stakeYen ?? 0) : (ticket.stakeRatio ?? 0);
}

export type DependencyAnalytics = {
  mode: "yen" | "ratio" | "unavailable";
  total: number;
  byHorse: Record<string, number>;
  byScenario: Record<string, number>;
  expectedValues: Record<string, number>;
};

export function calculateDependencyAnalytics(
  strategy: BetStrategy,
): DependencyAnalytics {
  const withYen = strategy.tickets.filter(
    (ticket) => ticket.stakeYen !== undefined,
  ).length;
  const withRatio = strategy.tickets.filter(
    (ticket) => ticket.stakeRatio !== undefined,
  ).length;
  const mode =
    strategy.tickets.length > 0 && withYen === strategy.tickets.length
      ? "yen"
      : strategy.tickets.length > 0 && withRatio === strategy.tickets.length
        ? "ratio"
        : "unavailable";
  const weights =
    mode === "unavailable"
      ? []
      : strategy.tickets.map((ticket) => ticketWeight(ticket, mode));
  const total = sum(weights);
  const byHorse: Record<string, number> = {};
  const byScenario: Record<string, number> = {};
  const expectedValues: Record<string, number> = {};

  if (total > 0 && mode !== "unavailable") {
    for (const ticket of strategy.tickets) {
      const weight = ticketWeight(ticket, mode);
      for (const runner of new Set(ticket.horseDependencies)) {
        byHorse[String(runner)] =
          (byHorse[String(runner)] ?? 0) + weight / total;
      }
      for (const scenario of new Set(ticket.scenarioDependencies)) {
        byScenario[scenario] = (byScenario[scenario] ?? 0) + weight / total;
      }
      if (
        ticket.estimatedHitProbability !== undefined &&
        ticket.decimalOdds !== undefined
      ) {
        expectedValues[ticket.id] = expectedValue(
          ticket.estimatedHitProbability,
          ticket.decimalOdds,
        );
      }
    }
  }
  return { mode, total, byHorse, byScenario, expectedValues };
}

export function validateStrategy(
  strategy: BetStrategy,
  forecast: ForecastSnapshot,
): ValidationIssue[] {
  const issues: ValidationIssue[] = [];
  const runners = new Set(forecast.horses.map((horse) => horse.runnerNumber));
  const scenarios = new Set(forecast.scenarios.map((scenario) => scenario.id));
  const topHorse = [...forecast.horses].sort(
    (a, b) => b.winProbability - a.winProbability,
  )[0];
  if (topHorse && strategy.mostLikelyRunnerNumber !== topHorse.runnerNumber) {
    issues.push({
      severity: "error",
      code: "MOST_LIKELY_MISMATCH",
      message: "最も勝つと思う馬は最終勝率1位と一致する必要があります",
    });
  }
  for (const runner of [
    strategy.mostLikelyRunnerNumber,
    strategy.bestValueRunnerNumber,
    strategy.valueAxis.candidateRunnerNumber,
  ]) {
    if (runner !== undefined && !runners.has(runner)) {
      issues.push({
        severity: "error",
        code: "UNKNOWN_STRATEGY_RUNNER",
        message: `馬番${runner}は最終予想に存在しません`,
      });
    }
  }
  if (strategy.category === "skip" && strategy.tickets.length > 0) {
    issues.push({
      severity: "error",
      code: "SKIP_WITH_TICKETS",
      message: "見送り時に買い目は保存できません",
    });
  }
  if (
    strategy.valueAxis.promoted &&
    strategy.valueAxis.independentEvidenceCount < 1
  ) {
    issues.push({
      severity: "error",
      code: "VALUE_AXIS_EVIDENCE",
      message: "穴軸昇格には独立根拠が必要です",
    });
  }
  const ticketIds = strategy.tickets.map((ticket) => ticket.id);
  if (new Set(ticketIds).size !== ticketIds.length)
    issues.push({
      severity: "error",
      code: "DUPLICATE_TICKET",
      message: "買い目IDが重複しています",
    });
  for (const ticket of strategy.tickets) {
    for (const runner of ticket.horseDependencies) {
      if (!runners.has(runner)) {
        issues.push({
          severity: "error",
          code: "UNKNOWN_TICKET_RUNNER",
          message: `買い目 ${ticket.id} の依存馬が不正です`,
        });
      }
    }
    for (const scenario of ticket.scenarioDependencies) {
      if (!scenarios.has(scenario)) {
        issues.push({
          severity: "error",
          code: "UNKNOWN_TICKET_SCENARIO",
          message: `買い目 ${ticket.id} の依存シナリオが不正です`,
        });
      }
    }
    if (
      ticket.type !== "win" &&
      ticket.estimatedHitProbability === undefined &&
      ticket.decimalOdds !== undefined
    ) {
      issues.push({
        severity: "warning",
        code: "EXOTIC_EV_UNAVAILABLE",
        message: `買い目 ${ticket.id} は組合せ的中確率がないため期待値を算出しません`,
      });
    }
  }
  const analytics = calculateDependencyAnalytics(strategy);
  if (analytics.mode === "ratio" && !nearlyEqual(analytics.total, 1)) {
    issues.push({
      severity: "error",
      code: "STAKE_RATIO_TOTAL",
      message: "資金配分比率の合計は1である必要があります",
    });
  }
  if (analytics.mode === "unavailable" && strategy.tickets.length > 0) {
    issues.push({
      severity: "error",
      code: "MIXED_STAKE_MODE",
      message:
        "全買い目でstakeYenまたはstakeRatioのどちらか一方を統一して指定してください",
    });
  }
  for (const [runner, ratio] of Object.entries(analytics.byHorse)) {
    if (nearlyEqual(ratio, 1)) {
      issues.push({
        severity: "warning",
        code: "FULL_HORSE_DEPENDENCY",
        message: `投資の100%が馬番${runner}に依存しています。例外運用の再確認が必要です`,
      });
    }
  }
  return issues;
}

export type Win5RaceInput = {
  raceId: string;
  horses: Array<{ runnerNumber: number; name: string; winProbability: number }>;
};

export type Win5Combination = {
  counts: [number, number, number, number, number];
  points: number;
  coverProbability: number;
  legs: Array<{
    raceId: string;
    selected: Array<{
      runnerNumber: number;
      name: string;
      winProbability: number;
    }>;
    coverProbability: number;
  }>;
};

export function analyzeWin5(
  races: Win5RaceInput[],
  maxPoints: number,
): Win5Combination[] {
  if (races.length !== 5) throw new Error("WIN5解析には5レースが必要です");
  if (!Number.isInteger(maxPoints) || maxPoints < 1)
    throw new Error("maxPointsは1以上の整数で指定してください");
  const sorted = races.map((race) => ({
    ...race,
    horses: [...race.horses].sort(
      (a, b) => b.winProbability - a.winProbability,
    ),
  }));
  const combinations: Win5Combination[] = [];

  const walk = (leg: number, counts: number[]): void => {
    if (leg === 5) {
      const typedCounts = counts as [number, number, number, number, number];
      const points = typedCounts.reduce((product, count) => product * count, 1);
      if (points > maxPoints) return;
      const legs = sorted.map((race, index) => {
        const selected = race.horses.slice(0, typedCounts[index]);
        return {
          raceId: race.raceId,
          selected,
          coverProbability: sum(selected.map((horse) => horse.winProbability)),
        };
      });
      combinations.push({
        counts: typedCounts,
        points,
        coverProbability: legs.reduce(
          (product, current) => product * current.coverProbability,
          1,
        ),
        legs,
      });
      return;
    }
    const race = sorted[leg];
    if (!race) return;
    for (let count = 1; count <= race.horses.length; count += 1) {
      const pointsSoFar = [...counts, count].reduce(
        (product, current) => product * current,
        1,
      );
      if (pointsSoFar > maxPoints) break;
      walk(leg + 1, [...counts, count]);
    }
  };
  walk(0, []);

  return combinations
    .filter(
      (candidate) =>
        !combinations.some(
          (other) =>
            other !== candidate &&
            other.points <= candidate.points &&
            other.coverProbability >= candidate.coverProbability &&
            (other.points < candidate.points ||
              other.coverProbability > candidate.coverProbability),
        ),
    )
    .sort(
      (a, b) => a.points - b.points || b.coverProbability - a.coverProbability,
    );
}
