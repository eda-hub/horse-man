import { calculateDependencyAnalytics, fairOdds } from "./calculations.js";
import type {
  BetStrategy,
  ForecastSnapshot,
  PurchaseRecord,
  RaceDossier,
  RaceResult,
  Review,
} from "./schemas.js";

const percentage = (value: number | undefined): string =>
  value === undefined ? "-" : `${(value * 100).toFixed(1)}%`;
const yen = (value: number | undefined): string =>
  value === undefined ? "-" : `${Math.round(value).toLocaleString("ja-JP")}円`;

export type RaceReportData = {
  dossier: RaceDossier;
  core?: ForecastSnapshot | undefined;
  final?: ForecastSnapshot | undefined;
  strategy?: BetStrategy | undefined;
  result?: RaceResult | undefined;
  purchase?: PurchaseRecord | undefined;
  review?: Review | undefined;
};

export function renderRaceReport(data: RaceReportData): string {
  const { dossier, core, final, strategy, result, purchase, review } = data;
  const forecast = final ?? core;
  const lines = [
    `# ${dossier.race.date} ${dossier.race.trackName}${dossier.race.raceNumber}R${dossier.race.name ? ` ${dossier.race.name}` : ""}`,
    "",
    `- 情報基準時刻: ${forecast?.asOf ?? dossier.informationCutoff}`,
    `- モード: ${dossier.race.mode === "live" ? "午後Live" : "午前"}`,
    `- 予想状態: ${forecast?.provenance ?? "未作成"}`,
  ];
  if (!forecast) return `${lines.join("\n")}\n`;

  lines.push("", "## 予想を決める3大要因", "");
  forecast.keyFactors.forEach((factor, index) =>
    lines.push(`${index + 1}. ${factor}`),
  );
  lines.push(
    "",
    "## レース質・シナリオ",
    "",
    forecast.raceQuality.summary,
    "",
    `想定ペース: ${forecast.raceQuality.expectedPace}`,
    "",
    "| シナリオ | 発生確率 | 内容 |",
    "|---|---:|---|",
  );
  for (const scenario of forecast.scenarios) {
    lines.push(
      `| ${scenario.name} | ${percentage(scenario.probability)} | ${scenario.narrative} |`,
    );
  }
  lines.push(
    "",
    "## 最終評価",
    "",
    "| 印 | 馬番 | 馬名 | 勝率 | 連対率 | 3着内率 | 勝率レンジ | フェア単勝 |",
    "|---:|---:|---|---:|---:|---:|---:|---:|",
  );
  for (const horse of [...forecast.horses].sort(
    (a, b) => b.winProbability - a.winProbability,
  )) {
    lines.push(
      `| ${horse.mark} | ${horse.runnerNumber} | ${horse.name} | ${percentage(horse.winProbability)} | ${percentage(horse.top2Probability)} | ${percentage(horse.top3Probability)} | ${percentage(horse.winRange.low)}–${percentage(horse.winRange.high)} | ${fairOdds(horse.winProbability)?.toFixed(2) ?? "-"} |`,
    );
  }
  lines.push(
    "",
    `- レース確信度: ${forecast.confidence}`,
    `- 不確実性: ${forecast.uncertainties.join("、") || "なし"}`,
  );

  if (core && final) {
    lines.push("", "## Coreからの変更", "");
    if (
      final.modules.length === 0 &&
      final.experimentalAdjustments.length === 0
    )
      lines.push("変更なし");
    for (const adjustment of final.modules) {
      lines.push(
        `- Module ${adjustment.module}: ${adjustment.reason}（証拠強度 ${adjustment.evidenceStrength}）`,
      );
    }
    for (const adjustment of final.experimentalAdjustments) {
      lines.push(`- Experimental ${adjustment.name}: ${adjustment.reason}`);
    }
  }

  if (strategy) {
    const analytics = calculateDependencyAnalytics(strategy);
    lines.push(
      "",
      "## 馬券戦略",
      "",
      `- 区分: ${strategy.category}`,
      `- 最も勝つと思う馬: ${strategy.mostLikelyRunnerNumber}番`,
      `- 最も買いたい馬: ${strategy.bestValueRunnerNumber ? `${strategy.bestValueRunnerNumber}番` : "なし"}`,
      `- 穴軸昇格: ${strategy.valueAxis.promoted ? "あり" : "なし"}`,
      `- 根拠: ${strategy.rationale}`,
      "",
      "| ID | 券種 | 買い目 | 配分 | 層 | 期待値 |",
      "|---|---|---|---:|---|---:|",
    );
    for (const ticket of strategy.tickets) {
      const allocation =
        ticket.stakeYen !== undefined
          ? yen(ticket.stakeYen)
          : percentage(ticket.stakeRatio);
      const ev = analytics.expectedValues[ticket.id];
      lines.push(
        `| ${ticket.id} | ${ticket.type} | ${ticket.selection} | ${allocation} | ${ticket.layer} | ${ev === undefined ? "-" : ev.toFixed(3)} |`,
      );
    }
    const horseDependency = Object.entries(analytics.byHorse)
      .sort(([, left], [, right]) => right - left)
      .map(([runner, ratio]) => `${runner}番 ${percentage(ratio)}`)
      .join("、");
    const scenarioDependency = Object.entries(analytics.byScenario)
      .sort(([, left], [, right]) => right - left)
      .map(([scenario, ratio]) => `${scenario} ${percentage(ratio)}`)
      .join("、");
    lines.push(
      "",
      `- 馬依存率: ${horseDependency || "算出不可"}`,
      `- シナリオ依存率: ${scenarioDependency || "算出不可"}`,
    );
  }

  if (result) {
    const winner = result.finishers.find((finisher) => finisher.position === 1);
    lines.push(
      "",
      "## 結果・回顧",
      "",
      `- 勝ち馬: ${winner?.runnerNumber ?? "不明"}番`,
      `- 結果出典: ${result.source}`,
    );
    if (purchase) {
      const invested = purchase.entries.reduce(
        (total, entry) => total + entry.amountYen,
        0,
      );
      const returned = purchase.entries.reduce(
        (total, entry) => total + (entry.returnedYen ?? 0),
        0,
      );
      lines.push(
        `- 購入額: ${yen(invested)}`,
        `- 払戻額: ${yen(returned)}`,
        `- 収支: ${yen(returned - invested)}`,
      );
    }
    if (review) {
      lines.push(
        `- Core採点: ${review.coreScore}`,
        `- Module影響: ${review.moduleImpact}`,
        `- Experimental影響: ${review.experimentalImpact}`,
        `- 主エラー: ${review.primaryError ?? "なし"}`,
        `- 反実仮想: ${review.counterfactual.repeatSameForecast ? "同じ予想をする" : "変更する"} — ${review.counterfactual.rationale}`,
      );
    }
  }
  return `${lines.join("\n")}\n`;
}

export type ScreenEntry = {
  dossier: RaceDossier;
  forecast?: ForecastSnapshot;
  strategy?: BetStrategy | undefined;
};

export function renderScreenReport(entries: ScreenEntry[]): string {
  const lines = [
    `# 開催全体スクリーニング ${entries[0]?.dossier.race.date ?? ""}`,
    "",
    "| レース | 区分 | 確信度 | 勝率1位 | 最も買いたい馬 | 人気薄候補 | 推奨度 |",
    "|---|---|---:|---|---|---|---|",
  ];
  for (const { dossier, forecast, strategy } of entries.sort((left, right) =>
    left.dossier.race.scheduledStart.localeCompare(
      right.dossier.race.scheduledStart,
    ),
  )) {
    const top = forecast
      ? [...forecast.horses].sort(
          (a, b) => b.winProbability - a.winProbability,
        )[0]
      : undefined;
    const valueAxis = strategy?.valueAxis.candidateRunnerNumber;
    const recommendation = strategy
      ? strategy.category === "skip"
        ? "見送り"
        : strategy.valueAxis.investmentConfidence
      : "未判定";
    lines.push(
      `| ${dossier.race.trackName}${dossier.race.raceNumber}R | ${strategy?.category ?? "未判定"} | ${forecast?.confidence ?? "-"} | ${top ? `${top.runnerNumber} ${top.name} (${percentage(top.winProbability)})` : "-"} | ${strategy?.bestValueRunnerNumber ? `${strategy.bestValueRunnerNumber}番` : "-"} | ${valueAxis ? `${valueAxis}番` : "-"} | ${recommendation} |`,
    );
  }
  return `${lines.join("\n")}\n`;
}

export type CycleEntry = RaceReportData;

type CalibrationBucket = {
  label: string;
  lower: number;
  upper: number;
  predictions: number[];
  outcomes: number[];
};

export type CycleSummary = {
  raceCount: number;
  coreTop1Wins: number;
  finalTop1Wins: number;
  finalTop3WinnerCoverage: number;
  marketFavoriteWins: number;
  diagnostics: {
    mostLikely: { races: number; wins: number };
    bestValue: { races: number; wins: number };
    liveTrack: {
      usedRaces: number;
      usedTop1Wins: number;
      unusedRaces: number;
      unusedTop1Wins: number;
    };
    byTicketType: Record<
      string,
      {
        tickets: number;
        hits: number;
        investedYen: number;
        returnedYen: number;
        roi: number | null;
      }
    >;
    experimentalImpact: Record<string, number>;
    win5ErrorCounts: Record<string, number>;
    priceEdge: Record<string, { horses: number; wins: number }>;
  };
  sharpness: { averageTop1Top2Gap: number; averageTop3Concentration: number };
  byCategory: Record<
    string,
    {
      races: number;
      investedYen: number;
      returnedYen: number;
      roi: number | null;
    }
  >;
  byConfidence: Record<string, { races: number; finalTop1Wins: number }>;
  byMode: Record<
    string,
    {
      races: number;
      finalTop1Wins: number;
      investedYen: number;
      returnedYen: number;
    }
  >;
  moduleImpact: Record<string, number>;
  uncertaintyErrors: Record<string, number>;
  errorCounts: Record<string, number>;
  calibration: Array<{
    label: string;
    predictions: number;
    averagePredicted: number;
    actualRate: number;
  }>;
};

export function calculateCycleSummary(entries: CycleEntry[]): CycleSummary {
  const eligible = entries.filter(
    (entry) => entry.final?.provenance === "prospective" && entry.result,
  );
  let coreTop1Wins = 0;
  let finalTop1Wins = 0;
  let finalTop3WinnerCoverage = 0;
  let marketFavoriteWins = 0;
  let gapTotal = 0;
  let concentrationTotal = 0;
  const byCategory: CycleSummary["byCategory"] = {};
  const byConfidence: CycleSummary["byConfidence"] = {};
  const byMode: CycleSummary["byMode"] = {};
  const moduleImpact: Record<string, number> = {};
  const uncertaintyErrors: Record<string, number> = {};
  const errorCounts: Record<string, number> = {};
  const diagnostics: CycleSummary["diagnostics"] = {
    mostLikely: { races: 0, wins: 0 },
    bestValue: { races: 0, wins: 0 },
    liveTrack: {
      usedRaces: 0,
      usedTop1Wins: 0,
      unusedRaces: 0,
      unusedTop1Wins: 0,
    },
    byTicketType: {},
    experimentalImpact: {},
    win5ErrorCounts: {},
    priceEdge: {
      negative: { horses: 0, wins: 0 },
      "0-10%": { horses: 0, wins: 0 },
      "10-25%": { horses: 0, wins: 0 },
      "25%+": { horses: 0, wins: 0 },
    },
  };
  const buckets: CalibrationBucket[] = [
    { label: "0–10%", lower: 0, upper: 0.1, predictions: [], outcomes: [] },
    { label: "10–20%", lower: 0.1, upper: 0.2, predictions: [], outcomes: [] },
    { label: "20–30%", lower: 0.2, upper: 0.3, predictions: [], outcomes: [] },
    {
      label: "30%以上",
      lower: 0.3,
      upper: 1.000001,
      predictions: [],
      outcomes: [],
    },
  ];

  for (const entry of eligible) {
    const final = entry.final;
    const result = entry.result;
    if (!final || !result) continue;
    const winner = result.finishers.find(
      (finisher) => finisher.position === 1,
    )?.runnerNumber;
    if (!winner) continue;
    const sortedFinal = [...final.horses].sort(
      (a, b) => b.winProbability - a.winProbability,
    );
    const sortedCore = entry.core
      ? [...entry.core.horses].sort(
          (a, b) => b.winProbability - a.winProbability,
        )
      : [];
    if (sortedCore[0]?.runnerNumber === winner) coreTop1Wins += 1;
    if (sortedFinal[0]?.runnerNumber === winner) finalTop1Wins += 1;
    if (sortedFinal.slice(0, 3).some((horse) => horse.runnerNumber === winner))
      finalTop3WinnerCoverage += 1;
    gapTotal +=
      (sortedFinal[0]?.winProbability ?? 0) -
      (sortedFinal[1]?.winProbability ?? 0);
    concentrationTotal += sortedFinal
      .slice(0, 3)
      .reduce((total, horse) => total + horse.winProbability, 0);

    const latestOdds = new Map<number, { odds: number; at: string }>();
    for (const odds of entry.strategy?.odds ?? []) {
      const current = latestOdds.get(odds.runnerNumber);
      if (!current || current.at < odds.retrievedAt || odds.isFinal)
        latestOdds.set(odds.runnerNumber, {
          odds: odds.decimalOdds,
          at: odds.retrievedAt,
        });
    }
    const marketFavorite = [...latestOdds.entries()].sort(
      ([, left], [, right]) => left.odds - right.odds,
    )[0]?.[0];
    if (marketFavorite === winner) marketFavoriteWins += 1;

    if (entry.strategy) {
      diagnostics.mostLikely.races += 1;
      diagnostics.mostLikely.wins +=
        entry.strategy.mostLikelyRunnerNumber === winner ? 1 : 0;
      if (entry.strategy.bestValueRunnerNumber !== undefined) {
        diagnostics.bestValue.races += 1;
        diagnostics.bestValue.wins +=
          entry.strategy.bestValueRunnerNumber === winner ? 1 : 0;
        const valueHorse = final.horses.find(
          (horse) =>
            horse.runnerNumber === entry.strategy?.bestValueRunnerNumber,
        );
        const valueOdds = latestOdds.get(
          entry.strategy.bestValueRunnerNumber,
        )?.odds;
        if (valueHorse && valueOdds) {
          const edge = valueHorse.winProbability * valueOdds - 1;
          const edgeKey =
            edge < 0
              ? "negative"
              : edge < 0.1
                ? "0-10%"
                : edge < 0.25
                  ? "10-25%"
                  : "25%+";
          const edgeData = diagnostics.priceEdge[edgeKey];
          if (edgeData) {
            edgeData.horses += 1;
            edgeData.wins += valueHorse.runnerNumber === winner ? 1 : 0;
          }
        }
      }
    }
    const usedLive = final.modules.some(
      (module) => module.module === "live-track",
    );
    if (usedLive) {
      diagnostics.liveTrack.usedRaces += 1;
      diagnostics.liveTrack.usedTop1Wins +=
        sortedFinal[0]?.runnerNumber === winner ? 1 : 0;
    } else {
      diagnostics.liveTrack.unusedRaces += 1;
      diagnostics.liveTrack.unusedTop1Wins +=
        sortedFinal[0]?.runnerNumber === winner ? 1 : 0;
    }
    for (const purchaseEntry of entry.purchase?.entries ?? []) {
      const ticketData = (diagnostics.byTicketType[purchaseEntry.type] ??= {
        tickets: 0,
        hits: 0,
        investedYen: 0,
        returnedYen: 0,
        roi: null,
      });
      ticketData.tickets += 1;
      ticketData.hits += (purchaseEntry.returnedYen ?? 0) > 0 ? 1 : 0;
      ticketData.investedYen += purchaseEntry.amountYen;
      ticketData.returnedYen += purchaseEntry.returnedYen ?? 0;
    }

    for (const horse of final.horses) {
      const bucket = buckets.find(
        (candidate) =>
          horse.winProbability >= candidate.lower &&
          horse.winProbability < candidate.upper,
      );
      bucket?.predictions.push(horse.winProbability);
      bucket?.outcomes.push(horse.runnerNumber === winner ? 1 : 0);
    }

    const category = entry.strategy?.category ?? "unclassified";
    byCategory[category] ??= {
      races: 0,
      investedYen: 0,
      returnedYen: 0,
      roi: null,
    };
    const categoryData = byCategory[category];
    categoryData.races += 1;
    const invested =
      entry.purchase?.entries.reduce(
        (total, item) => total + item.amountYen,
        0,
      ) ?? 0;
    const returned =
      entry.purchase?.entries.reduce(
        (total, item) => total + (item.returnedYen ?? 0),
        0,
      ) ?? 0;
    categoryData.investedYen += invested;
    categoryData.returnedYen += returned;

    const confidenceData = (byConfidence[final.confidence] ??= {
      races: 0,
      finalTop1Wins: 0,
    });
    confidenceData.races += 1;
    confidenceData.finalTop1Wins +=
      sortedFinal[0]?.runnerNumber === winner ? 1 : 0;

    const mode = entry.dossier.race.mode;
    const modeData = (byMode[mode] ??= {
      races: 0,
      finalTop1Wins: 0,
      investedYen: 0,
      returnedYen: 0,
    });
    modeData.races += 1;
    modeData.finalTop1Wins += sortedFinal[0]?.runnerNumber === winner ? 1 : 0;
    modeData.investedYen += invested;
    modeData.returnedYen += returned;

    if (entry.review) {
      moduleImpact[entry.review.moduleImpact] =
        (moduleImpact[entry.review.moduleImpact] ?? 0) + 1;
      diagnostics.experimentalImpact[entry.review.experimentalImpact] =
        (diagnostics.experimentalImpact[entry.review.experimentalImpact] ?? 0) +
        1;
      for (const code of entry.review.win5Errors)
        diagnostics.win5ErrorCounts[code] =
          (diagnostics.win5ErrorCounts[code] ?? 0) + 1;
      if (entry.review.primaryError)
        errorCounts[entry.review.primaryError] =
          (errorCounts[entry.review.primaryError] ?? 0) + 1;
      for (const uncertainty of final.uncertainties) {
        if (entry.review.primaryError)
          uncertaintyErrors[uncertainty] =
            (uncertaintyErrors[uncertainty] ?? 0) + 1;
      }
    }
  }
  for (const data of Object.values(byCategory)) {
    data.roi =
      data.investedYen > 0 ? data.returnedYen / data.investedYen : null;
  }
  for (const data of Object.values(diagnostics.byTicketType)) {
    data.roi =
      data.investedYen > 0 ? data.returnedYen / data.investedYen : null;
  }
  const count = eligible.length;
  return {
    raceCount: count,
    coreTop1Wins,
    finalTop1Wins,
    finalTop3WinnerCoverage,
    marketFavoriteWins,
    diagnostics,
    sharpness: {
      averageTop1Top2Gap: count ? gapTotal / count : 0,
      averageTop3Concentration: count ? concentrationTotal / count : 0,
    },
    byCategory,
    byConfidence,
    byMode,
    moduleImpact,
    uncertaintyErrors,
    errorCounts,
    calibration: buckets.map((bucket) => ({
      label: bucket.label,
      predictions: bucket.predictions.length,
      averagePredicted: bucket.predictions.length
        ? bucket.predictions.reduce((total, value) => total + value, 0) /
          bucket.predictions.length
        : 0,
      actualRate: bucket.outcomes.length
        ? bucket.outcomes.reduce((total, value) => total + value, 0) /
          bucket.outcomes.length
        : 0,
    })),
  };
}

export function renderCycleMarkdown(
  summary: CycleSummary,
  from: string,
  to: string,
): string {
  const lines = [
    `# 検証サイクル ${from}〜${to}`,
    "",
    `- 正式サンプル数: ${summary.raceCount}`,
    `- Core勝率1位の勝利: ${summary.coreTop1Wins}/${summary.raceCount}`,
    `- 最終勝率1位の勝利: ${summary.finalTop1Wins}/${summary.raceCount}`,
    `- 最終上位3頭内の勝ち馬: ${summary.finalTop3WinnerCoverage}/${summary.raceCount}`,
    "- 市場1番人気の勝利: " +
      summary.marketFavoriteWins +
      "/" +
      summary.raceCount,
    "- 最も勝つと思う馬の勝利: " +
      summary.diagnostics.mostLikely.wins +
      "/" +
      summary.diagnostics.mostLikely.races,
    "- 最も買いたい馬の勝利: " +
      summary.diagnostics.bestValue.wins +
      "/" +
      summary.diagnostics.bestValue.races,
    `- 平均1位–2位勝率差: ${percentage(summary.sharpness.averageTop1Top2Gap)}`,
    `- 平均上位3頭集中度: ${percentage(summary.sharpness.averageTop3Concentration)}`,
    "",
    "## 確率キャリブレーション",
    "",
    "| 勝率帯 | 予測数 | 平均予測 | 実勝率 |",
    "|---|---:|---:|---:|",
  ];
  for (const bucket of summary.calibration) {
    lines.push(
      `| ${bucket.label} | ${bucket.predictions} | ${percentage(bucket.averagePredicted)} | ${percentage(bucket.actualRate)} |`,
    );
  }
  lines.push(
    "",
    "## レース選別・回収",
    "",
    "| 区分 | レース数 | 投資 | 払戻 | 回収率 |",
    "|---|---:|---:|---:|---:|",
  );
  for (const [category, data] of Object.entries(summary.byCategory)) {
    lines.push(
      `| ${category} | ${data.races} | ${yen(data.investedYen)} | ${yen(data.returnedYen)} | ${percentage(data.roi ?? undefined)} |`,
    );
  }
  lines.push(
    "",
    "## 券種別成績",
    "",
    "| 券種 | 件数 | 的中 | 投資 | 払戻 | 回収率 |",
    "|---|---:|---:|---:|---:|---:|",
  );
  for (const [ticketType, data] of Object.entries(
    summary.diagnostics.byTicketType,
  ))
    lines.push(
      "| " +
        ticketType +
        " | " +
        data.tickets +
        " | " +
        data.hits +
        " | " +
        yen(data.investedYen) +
        " | " +
        yen(data.returnedYen) +
        " | " +
        percentage(data.roi ?? undefined) +
        " |",
    );
  lines.push(
    "",
    "## 午前・午後",
    "",
    "| モード | レース | 勝率1位勝利 | 投資 | 払戻 |",
    "|---|---:|---:|---:|---:|",
  );
  for (const [mode, data] of Object.entries(summary.byMode))
    lines.push(
      "| " +
        mode +
        " | " +
        data.races +
        " | " +
        data.finalTop1Wins +
        " | " +
        yen(data.investedYen) +
        " | " +
        yen(data.returnedYen) +
        " |",
    );
  lines.push(
    "",
    "## 確信度別",
    "",
    "| 確信度 | レース | 勝率1位勝利 |",
    "|---|---:|---:|",
  );
  for (const [confidence, data] of Object.entries(summary.byConfidence))
    lines.push(
      "| " +
        confidence +
        " | " +
        data.races +
        " | " +
        data.finalTop1Wins +
        " |",
    );
  lines.push(
    "",
    "## 価格・補正診断",
    "",
    "- Live馬場使用比較: " + JSON.stringify(summary.diagnostics.liveTrack),
    "- 価格乖離別: " + JSON.stringify(summary.diagnostics.priceEdge),
    "- Experimental影響: " +
      JSON.stringify(summary.diagnostics.experimentalImpact),
    "- WIN5エラー: " + JSON.stringify(summary.diagnostics.win5ErrorCounts),
  );
  lines.push(
    "",
    "## 補正・不確実性",
    "",
    `- Module影響: ${JSON.stringify(summary.moduleImpact)}`,
    `- エラー分類: ${JSON.stringify(summary.errorCounts)}`,
    `- 不確実性別エラー: ${JSON.stringify(summary.uncertaintyErrors)}`,
  );
  return `${lines.join("\n")}\n`;
}

export function renderCycleCsv(summary: CycleSummary): string {
  const rows = [
    "metric,key,value",
    `summary,raceCount,${summary.raceCount}`,
    `summary,coreTop1Wins,${summary.coreTop1Wins}`,
    `summary,finalTop1Wins,${summary.finalTop1Wins}`,
    `summary,finalTop3WinnerCoverage,${summary.finalTop3WinnerCoverage}`,
    "summary,marketFavoriteWins," + summary.marketFavoriteWins,
    "summary,mostLikelyWins," + summary.diagnostics.mostLikely.wins,
    "summary,bestValueWins," + summary.diagnostics.bestValue.wins,
  ];
  for (const bucket of summary.calibration) {
    rows.push(
      `calibration,${bucket.label},${bucket.predictions}|${bucket.averagePredicted}|${bucket.actualRate}`,
    );
  }
  for (const [category, data] of Object.entries(summary.byCategory)) {
    rows.push(
      "category," +
        category +
        "," +
        data.races +
        "|" +
        data.investedYen +
        "|" +
        data.returnedYen +
        "|" +
        (data.roi ?? ""),
    );
  }
  for (const [ticketType, data] of Object.entries(
    summary.diagnostics.byTicketType,
  )) {
    rows.push(
      "ticketType," +
        ticketType +
        "," +
        data.tickets +
        "|" +
        data.hits +
        "|" +
        data.investedYen +
        "|" +
        data.returnedYen +
        "|" +
        (data.roi ?? ""),
    );
  }
  return `${rows.join("\n")}\n`;
}
