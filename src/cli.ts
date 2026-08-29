#!/usr/bin/env node
import process from "node:process";
import { pathToFileURL } from "node:url";

import { Command } from "commander";

import {
  analyzeWin5,
  validateForecast,
  validateStrategy,
  type ValidationIssue,
} from "./calculations.js";
import {
  calculateCycleSummary,
  renderCycleCsv,
  renderCycleMarkdown,
  renderRaceReport,
  renderScreenReport,
  type CycleEntry,
} from "./reports.js";
import {
  betStrategySchema,
  forecastSnapshotSchema,
  purchaseRecordSchema,
  raceDossierSchema,
  raceResultSchema,
  reviewSchema,
  type BetStrategy,
} from "./schemas.js";
import { canonicalJson, HorsemanStore, parseJsonFile } from "./storage.js";
import { validateForecastTransition } from "./transitions.js";
import {
  readWin5PlanFile,
  readWin5ReviewFile,
  saveWin5Plan,
  saveWin5Review,
} from "./win5.js";

function printIssues(issues: ValidationIssue[]): void {
  for (const issue of issues)
    process.stderr.write(
      `[${issue.severity}] ${issue.code}: ${issue.message}\n`,
    );
  const errors = issues.filter((issue) => issue.severity === "error");
  if (errors.length)
    throw new Error(`${errors.length}件の検証エラーがあります`);
}

function integer(value: string): number {
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed < 1)
    throw new Error("1以上の整数を指定してください");
  return parsed;
}

function storeFor(program: Command): HorsemanStore {
  const options = program.opts<{ records?: string; rules?: string }>();
  return new HorsemanStore({
    ...(options.records ? { recordsRoot: options.records } : {}),
    ...(options.rules ? { rulesFile: options.rules } : {}),
  });
}

async function collectEntry(
  store: HorsemanStore,
  raceId: string,
): Promise<CycleEntry> {
  const dossier = await store.readDossier(raceId);
  const [core, final, strategy, result, purchase, review] = await Promise.all([
    store.readLatestForecast(raceId, "core"),
    store.readLatestForecast(raceId, "final"),
    store.readLatestStrategy(raceId),
    store.readResult(raceId),
    store.readLatestPurchase(raceId),
    store.readLatestReview(raceId),
  ]);
  return {
    dossier,
    ...(core ? { core } : {}),
    ...(final ? { final } : {}),
    ...(strategy ? { strategy } : {}),
    ...(result ? { result } : {}),
    ...(purchase ? { purchase } : {}),
    ...(review ? { review } : {}),
  };
}

export async function main(argv = process.argv): Promise<void> {
  const program = new Command();
  program
    .name("horseman")
    .description("競馬予想ルール原本 v1.4.1 準拠の予想記録・監査CLI")
    .version("1.0.0")
    .option("--records <path>", "記録ディレクトリ（既定: ./records）")
    .option("--rules <path>", "ルール原本のパス");

  const rules = program.command("rules").description("ルール原本を検証する");
  rules.command("verify").action(async () => {
    const store = storeFor(program);
    const hash = await store.verifyRules();
    process.stdout.write(`rules ok ${hash}\n`);
  });

  const race = program.command("race").description("レース情報を管理する");
  race
    .command("import")
    .argument("<json>")
    .action(async (filename: string) => {
      const store = storeFor(program);
      const dossier = await parseJsonFile(filename, raceDossierSchema);
      const saved = await store.saveDossier(dossier);
      process.stdout.write(`${saved}\n`);
    });

  const forecast = program
    .command("forecast")
    .description("Core/Final予想を保存する");
  forecast
    .command("save")
    .requiredOption("--race <id>")
    .requiredOption("--stage <stage>", "core または final")
    .requiredOption("--input <json>")
    .action(async (options: { race: string; stage: string; input: string }) => {
      if (options.stage !== "core" && options.stage !== "final")
        throw new Error("stageはcoreまたはfinalです");
      const store = storeFor(program);
      const dossier = await store.readDossier(options.race);
      const snapshot = await parseJsonFile(
        options.input,
        forecastSnapshotSchema,
      );
      if (snapshot.raceId !== options.race || snapshot.stage !== options.stage)
        throw new Error("CLI引数と予想JSONが一致しません");
      const coreSnapshot =
        snapshot.stage === "final"
          ? await store.readLatestForecast(options.race, "core")
          : undefined;
      if (snapshot.stage === "final" && !coreSnapshot) {
        throw new Error("Final予想の前にCore予想を保存してください");
      }
      printIssues(validateForecast(snapshot, dossier));
      if (coreSnapshot)
        printIssues(validateForecastTransition(coreSnapshot, snapshot));
      process.stdout.write(`${await store.saveForecast(snapshot)}\n`);
    });

  const strategy = program
    .command("strategy")
    .description("馬券戦略を保存する");
  strategy
    .command("save")
    .requiredOption("--race <id>")
    .requiredOption("--input <json>")
    .option("--budget-yen <yen>")
    .action(
      async (options: { race: string; input: string; budgetYen?: string }) => {
        const store = storeFor(program);
        const final = await store.readLatestForecast(options.race, "final");
        if (!final)
          throw new Error("馬券戦略の前にFinal予想を保存してください");
        const parsed = await parseJsonFile(options.input, betStrategySchema);
        const value: BetStrategy = options.budgetYen
          ? { ...parsed, budgetYen: integer(options.budgetYen) }
          : parsed;
        if (value.raceId !== options.race)
          throw new Error("CLI引数と戦略JSONのraceIdが一致しません");
        printIssues(validateStrategy(value, final));
        process.stdout.write(`${await store.saveStrategy(value)}\n`);
      },
    );

  const screen = program.command("screen").description("開催全体を比較する");
  screen
    .command("report")
    .requiredOption("--date <date>")
    .action(async (options: { date: string }) => {
      const store = storeFor(program);
      const dossiers = await store.listDossiersByDate(options.date);
      const entries = await Promise.all(
        dossiers.map(async (dossier) => {
          const currentForecast = await store.readLatestForecast(
            dossier.race.id,
            "final",
          );
          const currentStrategy = await store.readLatestStrategy(
            dossier.race.id,
          );
          return {
            dossier,
            ...(currentForecast ? { forecast: currentForecast } : {}),
            ...(currentStrategy ? { strategy: currentStrategy } : {}),
          };
        }),
      );
      process.stdout.write(renderScreenReport(entries));
    });

  const win5 = program
    .command("win5")
    .description("WIN5カバー率と点数を分析する");
  win5
    .command("analyze")
    .requiredOption("--date <date>")
    .requiredOption("--max-points <points>")
    .option("--unit-yen <yen>", "1点の金額", "100")
    .action(
      async (options: { date: string; maxPoints: string; unitYen: string }) => {
        const store = storeFor(program);
        const dossiers = (await store.listDossiersByDate(options.date))
          .filter((dossier) => dossier.race.win5Leg !== undefined)
          .sort(
            (left, right) =>
              (left.race.win5Leg ?? 0) - (right.race.win5Leg ?? 0),
          );
        if (dossiers.length !== 5)
          throw new Error("対象日にwin5Leg 1〜5のレース情報が5件必要です");
        const inputs = await Promise.all(
          dossiers.map(async (dossier) => {
            const final = await store.readLatestForecast(
              dossier.race.id,
              "final",
            );
            if (!final)
              throw new Error(`${dossier.race.id}のFinal予想がありません`);
            return {
              raceId: dossier.race.id,
              horses: final.horses.map((horse) => ({
                runnerNumber: horse.runnerNumber,
                name: horse.name,
                winProbability: horse.winProbability,
              })),
            };
          }),
        );
        const unitYen = integer(options.unitYen);
        const combinations = analyzeWin5(inputs, integer(options.maxPoints));
        process.stdout.write(
          canonicalJson(
            combinations.map((combination) => ({
              ...combination,
              investmentYen: combination.points * unitYen,
            })),
          ),
        );
      },
    );

  win5
    .command("save")
    .requiredOption("--input <json>")
    .action(async (options: { input: string }) => {
      const store = storeFor(program);
      const plan = await readWin5PlanFile(options.input);
      process.stdout.write((await saveWin5Plan(store, plan)) + "\n");
    });
  win5
    .command("review")
    .requiredOption("--input <json>")
    .action(async (options: { input: string }) => {
      const store = storeFor(program);
      const win5Review = await readWin5ReviewFile(options.input);
      process.stdout.write((await saveWin5Review(store, win5Review)) + "\n");
    });

  const result = program.command("result").description("確定結果を保存する");
  result
    .command("import")
    .argument("<json>")
    .action(async (filename: string) => {
      const store = storeFor(program);
      const value = await parseJsonFile(filename, raceResultSchema);
      const dossier = await store.readDossier(value.raceId);
      const runners = new Set(dossier.runners.map((runner) => runner.number));
      if (
        value.finishers.some((finisher) => !runners.has(finisher.runnerNumber))
      )
        throw new Error("結果に未知の馬番があります");
      process.stdout.write(`${await store.saveResult(value)}\n`);
    });

  const purchase = program
    .command("purchase")
    .description("手動購入記録を保存する");
  purchase
    .command("save")
    .requiredOption("--race <id>")
    .requiredOption("--input <json>")
    .action(async (options: { race: string; input: string }) => {
      const store = storeFor(program);
      if (!(await store.readLatestStrategy(options.race)))
        throw new Error("購入記録の前に戦略を保存してください");
      const value = await parseJsonFile(options.input, purchaseRecordSchema);
      if (value.raceId !== options.race)
        throw new Error("CLI引数と購入JSONのraceIdが一致しません");
      process.stdout.write(`${await store.savePurchase(value)}\n`);
    });

  const review = program.command("review").description("回顧を保存する");
  review
    .command("save")
    .requiredOption("--race <id>")
    .requiredOption("--input <json>")
    .action(async (options: { race: string; input: string }) => {
      const store = storeFor(program);
      if (!(await store.readResult(options.race)))
        throw new Error("回顧の前に結果を保存してください");
      const value = await parseJsonFile(options.input, reviewSchema);
      if (value.raceId !== options.race)
        throw new Error("CLI引数と回顧JSONのraceIdが一致しません");
      process.stdout.write(`${await store.saveReview(value)}\n`);
    });

  const report = program
    .command("report")
    .description("記録からレポートを生成する");
  report
    .command("race")
    .requiredOption("--race <id>")
    .action(async (options: { race: string }) => {
      process.stdout.write(
        renderRaceReport(await collectEntry(storeFor(program), options.race)),
      );
    });

  const cycle = program.command("cycle").description("検証サイクルを集計する");
  cycle
    .command("report")
    .requiredOption("--from <date>")
    .requiredOption("--to <date>")
    .option("--format <format>", "markdown, json, csv", "markdown")
    .action(async (options: { from: string; to: string; format: string }) => {
      const store = storeFor(program);
      const entries = await Promise.all(
        (await store.listRaceIds()).map((id) => collectEntry(store, id)),
      );
      const inRange = entries.filter(
        (entry) =>
          entry.dossier.race.date >= options.from &&
          entry.dossier.race.date <= options.to,
      );
      const summary = calculateCycleSummary(inRange);
      if (options.format === "json")
        process.stdout.write(canonicalJson(summary));
      else if (options.format === "csv")
        process.stdout.write(renderCycleCsv(summary));
      else if (options.format === "markdown")
        process.stdout.write(
          renderCycleMarkdown(summary, options.from, options.to),
        );
      else throw new Error("formatはmarkdown、json、csvのいずれかです");
    });

  await program.parseAsync(argv);
}

if (
  process.argv[1] &&
  import.meta.url === pathToFileURL(process.argv[1]).href
) {
  main().catch((error: unknown) => {
    const message = error instanceof Error ? error.message : String(error);
    process.stderr.write("horseman: " + message + "\n");
    process.exitCode = 1;
  });
}
