import { describe, expect, it } from "vitest";

import {
  analyzeWin5,
  calculateDependencyAnalytics,
  expectedValue,
  fairOdds,
  validateForecast,
  validateStrategy,
} from "../src/calculations.js";
import { dossier, forecast, strategy } from "./fixtures.js";

describe("forecast validation", () => {
  it("accepts a coherent race-wide forecast", () => {
    expect(validateForecast(forecast(), dossier())).toEqual([]);
  });

  it("rejects inconsistent totals and unexplained mark ordering", () => {
    const value = forecast();
    value.horses[0]!.winProbability = 0.35;
    value.horses[0]!.mark = "○";
    value.horses[1]!.mark = "◎";
    const codes = validateForecast(value, dossier()).map((issue) => issue.code);
    expect(codes).toContain("WIN_TOTAL");
    expect(codes).toContain("MARK_WIN_RANK_MISMATCH");
  });

  it("keeps scenario mismatch as an audit warning", () => {
    const value = forecast();
    value.scenarios[0]!.runnerWinProbabilities = {
      "1": 0.45,
      "2": 0.3,
      "3": 0.15,
      "4": 0.1,
    };
    const issue = validateForecast(value, dossier()).find(
      (candidate) => candidate.code === "SCENARIO_WEIGHT_MISMATCH",
    );
    expect(issue?.severity).toBe("warning");
  });
});

describe("bet calculations", () => {
  it("calculates fair odds and expected value", () => {
    expect(fairOdds(0.25)).toBe(4);
    expect(fairOdds(0)).toBeUndefined();
    expect(expectedValue(0.4, 3)).toBeCloseTo(0.2);
  });

  it("calculates correlated horse and scenario dependency", () => {
    const analytics = calculateDependencyAnalytics(strategy());
    expect(analytics.byHorse["1"]).toBe(1);
    expect(analytics.byHorse["2"]).toBe(0.5);
    expect(analytics.byScenario.main).toBe(1);
    expect(
      validateStrategy(strategy(), forecast()).map((issue) => issue.code),
    ).toContain("FULL_HORSE_DEPENDENCY");
  });

  it("does not permit a skip strategy with tickets", () => {
    const issues = validateStrategy(strategy({ category: "skip" }), forecast());
    expect(
      issues.some(
        (issue) =>
          issue.code === "SKIP_WITH_TICKETS" && issue.severity === "error",
      ),
    ).toBe(true);
  });
});

describe("WIN5 analysis", () => {
  it("returns non-dominated combinations within the point cap", () => {
    const races = Array.from({ length: 5 }, (_, index) => ({
      raceId: `race-${index + 1}`,
      horses: [
        { runnerNumber: 1, name: "A", winProbability: 0.5 },
        { runnerNumber: 2, name: "B", winProbability: 0.3 },
        { runnerNumber: 3, name: "C", winProbability: 0.2 },
      ],
    }));
    const result = analyzeWin5(races, 8);
    expect(result.length).toBeGreaterThan(0);
    expect(result.every((candidate) => candidate.points <= 8)).toBe(true);
    expect(result[0]?.points).toBe(1);
    expect(result.at(-1)?.coverProbability).toBeGreaterThan(
      result[0]!.coverProbability,
    );
  });
});
