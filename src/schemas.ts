import { z } from "zod";

import {
  ERROR_CODES,
  RULES_SHA256,
  RULES_VERSION,
  SCHEMA_VERSION,
  WIN5_ERROR_CODES,
} from "./constants.js";

const timestamp = z.string().datetime({ offset: true });
const date = z
  .string()
  .regex(/^\d{4}-\d{2}-\d{2}$/, "YYYY-MM-DD形式で指定してください");
const raceId = z
  .string()
  .min(1)
  .max(120)
  .regex(
    /^[A-Za-z0-9][A-Za-z0-9_-]*$/,
    "raceIdには英数字、_、-だけを使用できます",
  );
const probability = z.number().min(0).max(1);
const nonEmpty = z.string().trim().min(1);

export const evidenceStrengthSchema = z.enum(["strong", "medium", "weak"]);
export const uncertaintyTypeSchema = z.enum([
  "ability",
  "pace",
  "track",
  "condition",
  "information",
  "handling",
]);
export const moduleNameSchema = z.enum([
  "young-horse-handling",
  "class-rise-unknown",
  "live-track",
  "information-quality",
  "high-payout",
  "win5",
  "pace-control-position",
]);

export const rulesReferenceSchema = z.object({
  version: z.literal(RULES_VERSION),
  sha256: z.literal(RULES_SHA256),
});

export const evidenceSchema = z.object({
  id: nonEmpty,
  runnerNumber: z.number().int().positive().optional(),
  fact: nonEmpty,
  interpretation: nonEmpty,
  prediction: nonEmpty,
  source: z.object({
    url: z.string().url().optional(),
    publisher: nonEmpty,
    tier: z.enum(["official", "secondary", "user-provided"]),
    retrievedAt: timestamp,
    informationAt: timestamp.optional(),
  }),
  freshness: evidenceStrengthSchema,
  trust: evidenceStrengthSchema,
  relevance: evidenceStrengthSchema,
});

export const runnerSchema = z.object({
  number: z.number().int().positive(),
  name: nonEmpty,
  horseId: nonEmpty.optional(),
});

export const raceDossierSchema = z.object({
  schemaVersion: z.literal(SCHEMA_VERSION),
  kind: z.literal("race-dossier"),
  createdAt: timestamp,
  informationCutoff: timestamp,
  race: z.object({
    id: raceId,
    date,
    organizer: nonEmpty,
    country: z.string().length(2).default("JP"),
    trackCode: nonEmpty,
    trackName: nonEmpty,
    raceNumber: z.number().int().positive(),
    name: nonEmpty.optional(),
    scheduledStart: timestamp,
    timezone: nonEmpty,
    currency: z.string().length(3).default("JPY"),
    mode: z.enum(["morning", "live"]),
    surface: z.enum(["turf", "dirt", "synthetic", "other"]),
    distanceMeters: z.number().int().positive(),
    win5Leg: z.number().int().min(1).max(5).optional(),
  }),
  runners: z.array(runnerSchema).min(2),
  evidence: z.array(evidenceSchema),
});

export const scenarioSchema = z.object({
  id: nonEmpty,
  name: nonEmpty,
  narrative: nonEmpty,
  probability,
  pace: nonEmpty,
  positionAssumptions: z.array(nonEmpty),
  runnerWinProbabilities: z.record(z.string(), probability),
});

export const probabilityRangeSchema = z
  .object({ low: probability, high: probability })
  .refine(
    ({ low, high }) => low <= high,
    "確率レンジはlow <= highである必要があります",
  );

export const horseForecastSchema = z.object({
  runnerNumber: z.number().int().positive(),
  name: nonEmpty,
  mark: z.enum(["◎", "○", "▲", "△", "☆", "無"]),
  winProbability: probability,
  top2Probability: probability,
  top3Probability: probability,
  winRange: probabilityRangeSchema,
  strengths: z.array(nonEmpty),
  weaknesses: z.array(nonEmpty),
  buyConditions: z.array(nonEmpty),
  scratchConditions: z.array(nonEmpty),
  rationale: nonEmpty,
  scenarioNotes: z.array(nonEmpty),
});

const adjustmentDeltaSchema = z.object({
  runnerNumber: z.number().int().positive(),
  metric: z.enum(["winProbability", "top2Probability", "top3Probability"]),
  delta: z.number().min(-1).max(1),
});

export const moduleAdjustmentSchema = z.object({
  module: moduleNameSchema,
  maturity: z.enum(["established", "experimental"]),
  reason: nonEmpty,
  evidenceStrength: evidenceStrengthSchema,
  evidenceIds: z.array(nonEmpty),
  deltas: z.array(adjustmentDeltaSchema),
});

export const experimentalAdjustmentSchema = z.object({
  hypothesisId: nonEmpty,
  name: nonEmpty,
  reason: nonEmpty,
  evidenceIds: z.array(nonEmpty),
  deltas: z.array(adjustmentDeltaSchema),
});

export const forecastSnapshotSchema = z.object({
  schemaVersion: z.literal(SCHEMA_VERSION),
  kind: z.literal("forecast"),
  raceId,
  stage: z.enum(["core", "final"]),
  revision: z.number().int().positive(),
  provenance: z.enum(["prospective", "reconstructed"]),
  savedAt: timestamp,
  asOf: timestamp,
  rules: rulesReferenceSchema,
  keyFactors: z.array(nonEmpty).length(3),
  raceQuality: z.object({
    summary: nonEmpty,
    expectedPace: nonEmpty,
    expectedPositions: z.array(nonEmpty),
  }),
  scenarios: z.array(scenarioSchema).min(2),
  horses: z.array(horseForecastSchema).min(2),
  confidence: z.enum(["A", "B", "C"]),
  uncertainties: z.array(uncertaintyTypeSchema),
  modules: z.array(moduleAdjustmentSchema),
  experimentalAdjustments: z.array(experimentalAdjustmentSchema),
  subjectiveConcern: nonEmpty.optional(),
});

export const oddsSnapshotSchema = z.object({
  runnerNumber: z.number().int().positive(),
  decimalOdds: z.number().positive(),
  source: nonEmpty,
  retrievedAt: timestamp,
  isFinal: z.boolean().default(false),
});

export const ticketSchema = z.object({
  id: nonEmpty,
  type: z.enum([
    "win",
    "place",
    "quinella",
    "wide",
    "exacta",
    "trio",
    "trifecta",
    "win5",
    "other",
  ]),
  selection: nonEmpty,
  stakeRatio: probability.optional(),
  stakeYen: z.number().int().positive().optional(),
  origin: z.enum(["recommended", "user", "discretionary"]),
  layer: z.enum(["core", "overlay", "direct"]),
  horseDependencies: z.array(z.number().int().positive()),
  scenarioDependencies: z.array(nonEmpty),
  estimatedHitProbability: probability.optional(),
  decimalOdds: z.number().positive().optional(),
});

export const betStrategySchema = z.object({
  schemaVersion: z.literal(SCHEMA_VERSION),
  kind: z.literal("bet-strategy"),
  raceId,
  revision: z.number().int().positive(),
  savedAt: timestamp,
  category: z.enum(["primary", "high-payout", "combined", "skip"]),
  mostLikelyRunnerNumber: z.number().int().positive(),
  bestValueRunnerNumber: z.number().int().positive().optional(),
  valueAxis: z.object({
    candidateRunnerNumber: z.number().int().positive().optional(),
    promoted: z.boolean(),
    reasons: z.array(nonEmpty),
    independentEvidenceCount: z.number().int().nonnegative(),
    investmentConfidence: z.enum(["high", "medium", "low"]),
  }),
  odds: z.array(oddsSnapshotSchema),
  conditions: z.array(nonEmpty),
  budgetYen: z.number().int().positive().optional(),
  tickets: z.array(ticketSchema),
  rationale: nonEmpty,
});

export const raceResultSchema = z.object({
  schemaVersion: z.literal(SCHEMA_VERSION),
  kind: z.literal("race-result"),
  raceId,
  finalizedAt: timestamp,
  source: nonEmpty,
  finishers: z
    .array(
      z.object({
        position: z.number().int().positive(),
        runnerNumber: z.number().int().positive(),
        deadHeat: z.boolean().default(false),
      }),
    )
    .min(1),
  payouts: z.array(
    z.object({
      type: nonEmpty,
      selection: nonEmpty,
      payoutPer100Yen: z.number().nonnegative(),
    }),
  ),
  actualScenarioId: nonEmpty.optional(),
});

export const purchaseRecordSchema = z.object({
  schemaVersion: z.literal(SCHEMA_VERSION),
  kind: z.literal("purchase-record"),
  raceId,
  revision: z.number().int().positive(),
  purchasedAt: timestamp,
  entries: z.array(
    z.object({
      ticketId: nonEmpty.optional(),
      type: nonEmpty,
      selection: nonEmpty,
      origin: z.enum(["recommended", "user", "discretionary"]),
      amountYen: z.number().int().positive(),
      purchaseOdds: z.number().positive().optional(),
      returnedYen: z.number().int().nonnegative().optional(),
    }),
  ),
});

export const experimentalHypothesisSchema = z.object({
  id: nonEmpty,
  name: nonEmpty,
  raceId,
  errorCode: z.enum(ERROR_CODES).optional(),
  targetDecision: nonEmpty,
  applicationConditions: z.array(nonEmpty),
  expectedEffect: nonEmpty,
  coreDifference: nonEmpty,
  outcome: nonEmpty.optional(),
  sampleCount: z.number().int().nonnegative(),
  status: z.enum(["candidate", "testing", "adopted", "rejected"]),
});

export const reviewSchema = z.object({
  schemaVersion: z.literal(SCHEMA_VERSION),
  kind: z.literal("review"),
  raceId,
  revision: z.number().int().positive(),
  savedAt: timestamp,
  coreScore: z.enum(["good", "neutral", "bad"]),
  moduleImpact: z.enum(["improved", "neutral", "worsened", "not-used"]),
  experimentalImpact: z.enum(["improved", "neutral", "worsened", "not-used"]),
  priceScore: z.enum(["good", "neutral", "bad", "not-applicable"]),
  ticketStructureScore: z.enum(["good", "neutral", "bad", "not-applicable"]),
  primaryError: z.enum(ERROR_CODES).optional(),
  secondaryErrors: z.array(z.enum(ERROR_CODES)),
  win5Errors: z.array(z.enum(WIN5_ERROR_CODES)),
  counterfactual: z.object({
    repeatSameForecast: z.boolean(),
    rationale: nonEmpty,
  }),
  notes: nonEmpty,
  hypothesis: experimentalHypothesisSchema.optional(),
});

export type RaceDossier = z.infer<typeof raceDossierSchema>;
export type ForecastSnapshot = z.infer<typeof forecastSnapshotSchema>;
export type BetStrategy = z.infer<typeof betStrategySchema>;
export type RaceResult = z.infer<typeof raceResultSchema>;
export type PurchaseRecord = z.infer<typeof purchaseRecordSchema>;
export type Review = z.infer<typeof reviewSchema>;
export type Ticket = z.infer<typeof ticketSchema>;
