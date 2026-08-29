import { constants as fsConstants } from "node:fs";
import { access, mkdir, rename, writeFile } from "node:fs/promises";
import path from "node:path";

import { z } from "zod";

import {
  RULES_SHA256,
  RULES_VERSION,
  SCHEMA_VERSION,
  WIN5_ERROR_CODES,
} from "./constants.js";
import { canonicalJson, parseJsonFile } from "./storage.js";
import type { HorsemanStore } from "./storage.js";

const nonEmpty = z.string().trim().min(1);
const probability = z.number().min(0).max(1);
const timestamp = z.string().datetime({ offset: true });

export const win5PlanSchema = z
  .object({
    schemaVersion: z.literal(SCHEMA_VERSION),
    kind: z.literal("win5-plan"),
    date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/),
    revision: z.number().int().positive(),
    savedAt: timestamp,
    rules: z.object({
      version: z.literal(RULES_VERSION),
      sha256: z.literal(RULES_SHA256),
    }),
    participation: z.enum(["buy", "skip"]),
    maxPoints: z.number().int().positive(),
    unitYen: z.number().int().positive(),
    totalPoints: z.number().int().nonnegative(),
    overallCoverProbability: probability,
    legs: z
      .array(
        z.object({
          leg: z.number().int().min(1).max(5),
          raceId: nonEmpty,
          selectedRunnerNumbers: z.array(z.number().int().positive()),
          coverProbability: probability,
          confidence: z.enum(["A", "B", "C"]),
          fixedRunnerNumber: z.number().int().positive().optional(),
          cuts: z.array(
            z.object({
              runnerNumber: z.number().int().positive(),
              reasonType: z.enum([
                "low-rating",
                "point-constraint",
                "strategic-popularity",
              ]),
              reason: nonEmpty,
            }),
          ),
          rationale: nonEmpty,
        }),
      )
      .length(5),
    rationale: nonEmpty,
  })
  .superRefine((plan, context) => {
    const legs = new Set(plan.legs.map((leg) => leg.leg));
    if (legs.size !== 5)
      context.addIssue({
        code: z.ZodIssueCode.custom,
        message: "leg 1〜5を一度ずつ指定してください",
        path: ["legs"],
      });
    const calculatedPoints = plan.legs.reduce(
      (product, leg) => product * leg.selectedRunnerNumbers.length,
      1,
    );
    const calculatedCover = plan.legs.reduce(
      (product, leg) => product * leg.coverProbability,
      1,
    );
    if (plan.participation === "skip") {
      if (plan.totalPoints !== 0)
        context.addIssue({
          code: z.ZodIssueCode.custom,
          message: "見送り時のtotalPointsは0です",
          path: ["totalPoints"],
        });
    } else {
      if (calculatedPoints !== plan.totalPoints)
        context.addIssue({
          code: z.ZodIssueCode.custom,
          message: "選択頭数の積とtotalPointsが一致しません",
          path: ["totalPoints"],
        });
      if (plan.totalPoints > plan.maxPoints)
        context.addIssue({
          code: z.ZodIssueCode.custom,
          message: "totalPointsがmaxPointsを超えています",
          path: ["totalPoints"],
        });
      if (Math.abs(calculatedCover - plan.overallCoverProbability) > 0.005)
        context.addIssue({
          code: z.ZodIssueCode.custom,
          message: "各レースの積とoverallCoverProbabilityが一致しません",
          path: ["overallCoverProbability"],
        });
    }
  });

export const win5ReviewSchema = z.object({
  schemaVersion: z.literal(SCHEMA_VERSION),
  kind: z.literal("win5-review"),
  date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/),
  revision: z.number().int().positive(),
  savedAt: timestamp,
  planRevision: z.number().int().positive(),
  coveredLegs: z.number().int().min(0).max(5),
  legs: z
    .array(
      z.object({
        leg: z.number().int().min(1).max(5),
        raceId: nonEmpty,
        winnerRunnerNumber: z.number().int().positive(),
        winnerForecastRank: z.number().int().positive(),
        winnerWinProbability: probability,
        selected: z.boolean(),
        selectedCount: z.number().int().nonnegative(),
        preRaceCoverProbability: probability,
        exclusionReason: nonEmpty.optional(),
        actualScenarioId: nonEmpty.optional(),
        primaryError: z.enum(WIN5_ERROR_CODES).optional(),
        secondaryErrors: z.array(z.enum(WIN5_ERROR_CODES)),
      }),
    )
    .length(5),
  notes: nonEmpty,
});

export type Win5Plan = z.infer<typeof win5PlanSchema>;
export type Win5Review = z.infer<typeof win5ReviewSchema>;

async function exists(filename: string): Promise<boolean> {
  try {
    await access(filename, fsConstants.F_OK);
    return true;
  } catch {
    return false;
  }
}

async function saveImmutable(
  store: HorsemanStore,
  filename: string,
  value: unknown,
): Promise<string> {
  await store.verifyRules();
  if (await exists(filename))
    throw new Error(
      `${filename}は既に存在します。不変スナップショットは上書きできません`,
    );
  await mkdir(path.dirname(filename), { recursive: true });
  const temporary = `${filename}.${process.pid}.tmp`;
  await writeFile(temporary, canonicalJson(value), {
    encoding: "utf8",
    flag: "wx",
  });
  await rename(temporary, filename);
  return filename;
}

export async function saveWin5Plan(
  store: HorsemanStore,
  plan: Win5Plan,
): Promise<string> {
  const parsed = win5PlanSchema.parse(plan);
  return saveImmutable(
    store,
    path.join(
      store.recordsRoot,
      "win5",
      parsed.date,
      `plan-v${parsed.revision}.json`,
    ),
    parsed,
  );
}

export async function saveWin5Review(
  store: HorsemanStore,
  review: Win5Review,
): Promise<string> {
  const parsed = win5ReviewSchema.parse(review);
  return saveImmutable(
    store,
    path.join(
      store.recordsRoot,
      "win5",
      parsed.date,
      `review-v${parsed.revision}.json`,
    ),
    parsed,
  );
}

export async function readWin5PlanFile(filename: string): Promise<Win5Plan> {
  return parseJsonFile(filename, win5PlanSchema);
}

export async function readWin5ReviewFile(
  filename: string,
): Promise<Win5Review> {
  return parseJsonFile(filename, win5ReviewSchema);
}
