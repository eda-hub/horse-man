import { mkdtemp } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";

import { describe, expect, it } from "vitest";

import { RULES_SHA256, RULES_VERSION } from "../src/constants.js";
import { HorsemanStore } from "../src/storage.js";
import { validateForecastTransition } from "../src/transitions.js";
import {
  saveWin5Plan,
  saveWin5Review,
  type Win5Plan,
  type Win5Review,
} from "../src/win5.js";
import { forecast } from "./fixtures.js";

describe("Core to Final transition", () => {
  it("accepts unchanged final probabilities without adjustments", () => {
    expect(
      validateForecastTransition(forecast("core"), forecast("final")),
    ).toEqual([]);
  });

  it("rejects a probability change without a recorded delta", () => {
    const final = forecast("final");
    final.horses[0]!.winProbability += 0.01;
    final.horses[1]!.winProbability -= 0.01;
    const issues = validateForecastTransition(forecast("core"), final);
    expect(
      issues.filter((issue) => issue.code === "UNRECORDED_ADJUSTMENT"),
    ).toHaveLength(2);
  });

  it("warns when weak Live evidence reverses the top rank", () => {
    const final = forecast("final");
    final.horses[0]!.winProbability = 0.29;
    final.horses[1]!.winProbability = 0.41;
    final.modules = [
      {
        module: "live-track",
        maturity: "established",
        reason: "弱い当日傾向",
        evidenceStrength: "weak",
        evidenceIds: ["live-1", "live-2"],
        deltas: [
          { runnerNumber: 1, metric: "winProbability", delta: -0.11 },
          { runnerNumber: 2, metric: "winProbability", delta: 0.11 },
        ],
      },
    ];
    const issues = validateForecastTransition(forecast("core"), final);
    expect(
      issues.some(
        (issue) =>
          issue.code === "WEAK_EVIDENCE_RANK_REVERSAL" &&
          issue.severity === "warning",
      ),
    ).toBe(true);
    expect(issues.some((issue) => issue.severity === "error")).toBe(false);
  });

  it("rejects Module data in Core", () => {
    const core = forecast("core");
    core.modules.push({
      module: "live-track",
      maturity: "established",
      reason: "誤ったCore補正",
      evidenceStrength: "weak",
      evidenceIds: [],
      deltas: [],
    });
    expect(
      validateForecastTransition(core, forecast("final")).map(
        (issue) => issue.code,
      ),
    ).toContain("CORE_HAS_ADJUSTMENTS");
  });
});

describe("WIN5 immutable records", () => {
  const plan: Win5Plan = {
    schemaVersion: 1,
    kind: "win5-plan",
    date: "2026-08-29",
    revision: 1,
    savedAt: "2026-08-29T12:00:00+09:00",
    rules: { version: RULES_VERSION, sha256: RULES_SHA256 },
    participation: "buy",
    maxPoints: 32,
    unitYen: 100,
    totalPoints: 1,
    overallCoverProbability: 0.4 ** 5,
    legs: Array.from({ length: 5 }, (_, index) => ({
      leg: index + 1,
      raceId: `race-${index + 1}`,
      selectedRunnerNumbers: [1],
      coverProbability: 0.4,
      confidence: "A" as const,
      fixedRunnerNumber: 1,
      cuts: [
        {
          runnerNumber: 2,
          reasonType: "point-constraint" as const,
          reason: "点数配分を優先",
        },
      ],
      rationale: "勝率レンジ下側とシナリオ優位を確認",
    })),
    rationale: "全5レースのカバー率と点数を比較して採用",
  };

  const review: Win5Review = {
    schemaVersion: 1,
    kind: "win5-review",
    date: "2026-08-29",
    revision: 1,
    savedAt: "2026-08-29T17:00:00+09:00",
    planRevision: 1,
    coveredLegs: 4,
    legs: Array.from({ length: 5 }, (_, index) => ({
      leg: index + 1,
      raceId: `race-${index + 1}`,
      winnerRunnerNumber: index === 4 ? 2 : 1,
      winnerForecastRank: index === 4 ? 2 : 1,
      winnerWinProbability: index === 4 ? 0.3 : 0.4,
      selected: index !== 4,
      selectedCount: 1,
      preRaceCoverProbability: 0.4,
      ...(index === 4
        ? { exclusionReason: "点数制約切り", primaryError: "W-B" as const }
        : {}),
      secondaryErrors: [],
    })),
    notes: "全5レースを個別採点",
  };

  it("stores plans and all-five-leg reviews without overwrite", async () => {
    const recordsRoot = await mkdtemp(path.join(tmpdir(), "horseman-win5-"));
    const store = new HorsemanStore({
      repositoryRoot: "/workspace",
      recordsRoot,
    });
    await expect(saveWin5Plan(store, plan)).resolves.toContain("plan-v1.json");
    await expect(saveWin5Review(store, review)).resolves.toContain(
      "review-v1.json",
    );
    await expect(saveWin5Plan(store, plan)).rejects.toThrow("上書きできません");
  });

  it("rejects inconsistent point totals", async () => {
    const recordsRoot = await mkdtemp(
      path.join(tmpdir(), "horseman-win5-invalid-"),
    );
    const store = new HorsemanStore({
      repositoryRoot: "/workspace",
      recordsRoot,
    });
    await expect(
      saveWin5Plan(store, { ...plan, totalPoints: 2 }),
    ).rejects.toThrow("選択頭数の積");
  });
});
