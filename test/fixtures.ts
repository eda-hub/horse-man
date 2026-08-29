import { RULES_SHA256, RULES_VERSION } from "../src/constants.js";
import type {
  BetStrategy,
  ForecastSnapshot,
  PurchaseRecord,
  RaceDossier,
  RaceResult,
  Review,
} from "../src/schemas.js";

const at = "2026-08-29T02:00:00+09:00";

export function dossier(
  overrides: Partial<RaceDossier["race"]> = {},
): RaceDossier {
  return {
    schemaVersion: 1,
    kind: "race-dossier",
    createdAt: at,
    informationCutoff: at,
    race: {
      id: "2026-08-29_JRA_TKY_11",
      date: "2026-08-29",
      organizer: "JRA",
      country: "JP",
      trackCode: "TKY",
      trackName: "東京",
      raceNumber: 11,
      name: "テストステークス",
      scheduledStart: "2026-08-29T15:45:00+09:00",
      timezone: "Asia/Tokyo",
      currency: "JPY",
      mode: "morning",
      surface: "turf",
      distanceMeters: 1600,
      ...overrides,
    },
    runners: [
      { number: 1, name: "アルファ" },
      { number: 2, name: "ベータ" },
      { number: 3, name: "ガンマ" },
      { number: 4, name: "デルタ" },
    ],
    evidence: [
      {
        id: "official-card",
        fact: "出走表が公開された",
        interpretation: "出走条件を確定できる",
        prediction: "全出走馬を同一基準で評価する",
        source: { publisher: "JRA", tier: "official", retrievedAt: at },
        freshness: "strong",
        trust: "strong",
        relevance: "strong",
      },
      {
        id: "live-track-1",
        fact: "同条件で前有利だった",
        interpretation: "好位がやや有利な可能性がある",
        prediction: "位置取りシナリオを小幅補正する",
        source: { publisher: "JRA", tier: "official", retrievedAt: at },
        freshness: "medium",
        trust: "strong",
        relevance: "medium",
      },
    ],
  };
}

export function forecast(
  stage: "core" | "final" = "final",
  overrides: Partial<ForecastSnapshot> = {},
): ForecastSnapshot {
  const value: ForecastSnapshot = {
    schemaVersion: 1,
    kind: "forecast",
    raceId: "2026-08-29_JRA_TKY_11",
    stage,
    revision: 1,
    provenance: "prospective",
    savedAt: at,
    asOf: at,
    rules: { version: RULES_VERSION, sha256: RULES_SHA256 },
    keyFactors: ["現級での基礎能力", "高速巡航適性", "好位を取れる確率"],
    raceQuality: {
      summary: "平均ペースから好位差しが中心",
      expectedPace: "平均",
      expectedPositions: ["1番は好位", "2番は中団"],
    },
    scenarios: [
      {
        id: "main",
        name: "本線",
        narrative: "平均ペースで好位優勢",
        probability: 0.6,
        pace: "平均",
        positionAssumptions: ["1番が好位"],
        runnerWinProbabilities: { "1": 0.5, "2": 0.25, "3": 0.15, "4": 0.1 },
      },
      {
        id: "alternate",
        name: "代替",
        narrative: "ハイペースで差し優勢",
        probability: 0.4,
        pace: "速い",
        positionAssumptions: ["3番が差す"],
        runnerWinProbabilities: { "1": 0.25, "2": 0.375, "3": 0.275, "4": 0.1 },
      },
    ],
    horses: [
      {
        runnerNumber: 1,
        name: "アルファ",
        mark: "◎",
        winProbability: 0.4,
        top2Probability: 0.7,
        top3Probability: 0.9,
        winRange: { low: 0.35, high: 0.45 },
        strengths: ["基礎能力"],
        weaknesses: ["差し決着"],
        buyConditions: ["単勝2.8倍以上"],
        scratchConditions: ["大幅な状態悪化"],
        rationale: "本線シナリオで最上位",
        scenarioNotes: ["本線で優位"],
      },
      {
        runnerNumber: 2,
        name: "ベータ",
        mark: "○",
        winProbability: 0.3,
        top2Probability: 0.6,
        top3Probability: 0.8,
        winRange: { low: 0.25, high: 0.35 },
        strengths: ["安定性"],
        weaknesses: ["勝ち切り"],
        buyConditions: ["適正価格"],
        scratchConditions: ["なし"],
        rationale: "複数シナリオで上位",
        scenarioNotes: ["代替でも対応"],
      },
      {
        runnerNumber: 3,
        name: "ガンマ",
        mark: "▲",
        winProbability: 0.2,
        top2Probability: 0.4,
        top3Probability: 0.7,
        winRange: { low: 0.15, high: 0.25 },
        strengths: ["末脚"],
        weaknesses: ["位置取り"],
        buyConditions: ["ハイペース"],
        scratchConditions: ["前有利"],
        rationale: "代替シナリオで浮上",
        scenarioNotes: ["ハイペース向き"],
      },
      {
        runnerNumber: 4,
        name: "デルタ",
        mark: "△",
        winProbability: 0.1,
        top2Probability: 0.3,
        top3Probability: 0.6,
        winRange: { low: 0.07, high: 0.13 },
        strengths: ["展開利"],
        weaknesses: ["能力差"],
        buyConditions: ["展開利"],
        scratchConditions: ["不利な枠"],
        rationale: "条件付きで相手候補",
        scenarioNotes: ["両シナリオで低位"],
      },
    ],
    confidence: "A",
    uncertainties: ["pace"],
    modules: [],
    experimentalAdjustments: [],
  };
  return { ...value, ...overrides };
}

export function strategy(overrides: Partial<BetStrategy> = {}): BetStrategy {
  return {
    schemaVersion: 1,
    kind: "bet-strategy",
    raceId: "2026-08-29_JRA_TKY_11",
    revision: 1,
    savedAt: at,
    category: "primary",
    mostLikelyRunnerNumber: 1,
    bestValueRunnerNumber: 2,
    valueAxis: {
      candidateRunnerNumber: 2,
      promoted: false,
      reasons: ["市場との価格差"],
      independentEvidenceCount: 2,
      investmentConfidence: "medium",
    },
    odds: [
      {
        runnerNumber: 1,
        decimalOdds: 3,
        source: "JRA",
        retrievedAt: at,
        isFinal: false,
      },
      {
        runnerNumber: 2,
        decimalOdds: 4,
        source: "JRA",
        retrievedAt: at,
        isFinal: false,
      },
    ],
    conditions: ["オッズ条件を満たす"],
    tickets: [
      {
        id: "t1",
        type: "win",
        selection: "1",
        stakeRatio: 0.5,
        origin: "recommended",
        layer: "core",
        horseDependencies: [1],
        scenarioDependencies: ["main"],
        estimatedHitProbability: 0.4,
        decimalOdds: 3,
      },
      {
        id: "t2",
        type: "wide",
        selection: "1-2",
        stakeRatio: 0.5,
        origin: "recommended",
        layer: "core",
        horseDependencies: [1, 2],
        scenarioDependencies: ["main", "alternate"],
        estimatedHitProbability: 0.35,
        decimalOdds: 3.5,
      },
    ],
    rationale: "本線シナリオを少数買い目で表現する",
    ...overrides,
  };
}

export function result(): RaceResult {
  return {
    schemaVersion: 1,
    kind: "race-result",
    raceId: "2026-08-29_JRA_TKY_11",
    finalizedAt: "2026-08-29T16:00:00+09:00",
    source: "JRA",
    finishers: [
      { position: 1, runnerNumber: 1, deadHeat: false },
      { position: 2, runnerNumber: 2, deadHeat: false },
      { position: 3, runnerNumber: 3, deadHeat: false },
      { position: 4, runnerNumber: 4, deadHeat: false },
    ],
    payouts: [{ type: "win", selection: "1", payoutPer100Yen: 300 }],
    actualScenarioId: "main",
  };
}

export function purchase(): PurchaseRecord {
  return {
    schemaVersion: 1,
    kind: "purchase-record",
    raceId: "2026-08-29_JRA_TKY_11",
    revision: 1,
    purchasedAt: "2026-08-29T15:40:00+09:00",
    entries: [
      {
        ticketId: "t1",
        type: "win",
        selection: "1",
        origin: "recommended",
        amountYen: 1000,
        returnedYen: 3000,
      },
    ],
  };
}

export function review(): Review {
  return {
    schemaVersion: 1,
    kind: "review",
    raceId: "2026-08-29_JRA_TKY_11",
    revision: 1,
    savedAt: "2026-08-29T17:00:00+09:00",
    coreScore: "good",
    moduleImpact: "not-used",
    experimentalImpact: "not-used",
    priceScore: "good",
    ticketStructureScore: "good",
    secondaryErrors: [],
    win5Errors: [],
    counterfactual: {
      repeatSameForecast: true,
      rationale: "事前根拠と結果が整合した",
    },
    notes: "確率的にも妥当",
  };
}
