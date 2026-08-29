import { createHash } from "node:crypto";
import { constants as fsConstants } from "node:fs";
import {
  access,
  mkdir,
  readFile,
  readdir,
  rename,
  writeFile,
} from "node:fs/promises";
import path from "node:path";

import type { z } from "zod";

import { RULES_FILENAME, RULES_SHA256 } from "./constants.js";
import {
  assertDossierIntegrity,
  assertResultIntegrity,
  assertReviewIntegrity,
} from "./integrity.js";
import {
  betStrategySchema,
  forecastSnapshotSchema,
  purchaseRecordSchema,
  raceDossierSchema,
  raceResultSchema,
  reviewSchema,
  type BetStrategy,
  type ForecastSnapshot,
  type PurchaseRecord,
  type RaceDossier,
  type RaceResult,
  type Review,
} from "./schemas.js";

function canonicalize(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(canonicalize);
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>)
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([key, item]) => [key, canonicalize(item)]),
    );
  }
  return value;
}

export function canonicalJson(value: unknown): string {
  return `${JSON.stringify(canonicalize(value), null, 2)}\n`;
}

async function exists(filename: string): Promise<boolean> {
  try {
    await access(filename, fsConstants.F_OK);
    return true;
  } catch {
    return false;
  }
}

export async function parseJsonFile<TSchema extends z.ZodTypeAny>(
  filename: string,
  schema: TSchema,
): Promise<z.output<TSchema>> {
  const content = await readFile(filename, "utf8");
  let parsed: unknown;
  try {
    parsed = JSON.parse(content);
  } catch (error) {
    throw new Error(`${filename}は有効なJSONではありません`, { cause: error });
  }
  const result = schema.safeParse(parsed);
  if (!result.success) {
    const details = result.error.issues
      .map((issue) => `${issue.path.join(".")}: ${issue.message}`)
      .join("\n");
    throw new Error(`${filename}のスキーマ検証に失敗しました\n${details}`);
  }
  return result.data;
}

export class HorsemanStore {
  readonly repositoryRoot: string;
  readonly recordsRoot: string;
  readonly rulesFile: string;

  constructor(
    options: {
      repositoryRoot?: string;
      recordsRoot?: string;
      rulesFile?: string;
    } = {},
  ) {
    this.repositoryRoot = path.resolve(options.repositoryRoot ?? process.cwd());
    this.recordsRoot = path.resolve(
      options.recordsRoot ??
        process.env.HORSEMAN_DATA_DIR ??
        path.join(this.repositoryRoot, "records"),
    );
    this.rulesFile = path.resolve(
      options.rulesFile ??
        process.env.HORSEMAN_RULES_FILE ??
        path.join(this.repositoryRoot, RULES_FILENAME),
    );
  }

  async verifyRules(): Promise<string> {
    const content = await readFile(this.rulesFile);
    const actual = createHash("sha256").update(content).digest("hex");
    if (actual !== RULES_SHA256) {
      throw new Error(
        `原本のSHA-256が不一致です。書き込みを停止します（actual=${actual}）`,
      );
    }
    return actual;
  }

  raceDirectory(raceId: string): string {
    if (!/^[A-Za-z0-9][A-Za-z0-9_-]*$/.test(raceId))
      throw new Error("不正なraceIdです");
    return path.join(this.recordsRoot, "races", raceId);
  }

  private async writeImmutable(
    filename: string,
    value: unknown,
  ): Promise<void> {
    await this.verifyRules();
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
  }

  async saveDossier(dossier: RaceDossier): Promise<string> {
    const parsed = raceDossierSchema.parse(dossier);
    assertDossierIntegrity(parsed);
    const filename = path.join(
      this.raceDirectory(parsed.race.id),
      "dossier.json",
    );
    await this.writeImmutable(filename, parsed);
    return filename;
  }

  async readDossier(raceId: string): Promise<RaceDossier> {
    return parseJsonFile(
      path.join(this.raceDirectory(raceId), "dossier.json"),
      raceDossierSchema,
    );
  }

  async saveForecast(forecast: ForecastSnapshot): Promise<string> {
    const parsed = forecastSnapshotSchema.parse(forecast);
    const filename = path.join(
      this.raceDirectory(parsed.raceId),
      "forecasts",
      `${parsed.stage}-v${parsed.revision}.json`,
    );
    await this.writeImmutable(filename, parsed);
    return filename;
  }

  async saveStrategy(strategy: BetStrategy): Promise<string> {
    const parsed = betStrategySchema.parse(strategy);
    const filename = path.join(
      this.raceDirectory(parsed.raceId),
      "strategies",
      `strategy-v${parsed.revision}.json`,
    );
    await this.writeImmutable(filename, parsed);
    return filename;
  }

  async saveResult(result: RaceResult): Promise<string> {
    const parsed = raceResultSchema.parse(result);
    assertResultIntegrity(parsed);
    const filename = path.join(
      this.raceDirectory(parsed.raceId),
      "result.json",
    );
    await this.writeImmutable(filename, parsed);
    return filename;
  }

  async savePurchase(purchase: PurchaseRecord): Promise<string> {
    const parsed = purchaseRecordSchema.parse(purchase);
    const filename = path.join(
      this.raceDirectory(parsed.raceId),
      "purchases",
      `purchase-v${parsed.revision}.json`,
    );
    await this.writeImmutable(filename, parsed);
    return filename;
  }

  async saveReview(review: Review): Promise<string> {
    const parsed = reviewSchema.parse(review);
    assertReviewIntegrity(parsed);
    const filename = path.join(
      this.raceDirectory(parsed.raceId),
      "reviews",
      `review-v${parsed.revision}.json`,
    );
    await this.writeImmutable(filename, parsed);
    if (parsed.hypothesis) {
      const hypothesisFilename = path.join(
        this.recordsRoot,
        "experimental",
        parsed.hypothesis.id,
        parsed.raceId + "-v" + parsed.revision + ".json",
      );
      await this.writeImmutable(hypothesisFilename, parsed.hypothesis);
    }
    return filename;
  }

  private async readLatest<TSchema extends z.ZodTypeAny>(
    directory: string,
    prefix: string,
    schema: TSchema,
  ): Promise<z.output<TSchema> | undefined> {
    if (!(await exists(directory))) return undefined;
    const files = (await readdir(directory))
      .filter(
        (filename) => filename.startsWith(prefix) && filename.endsWith(".json"),
      )
      .sort((left, right) => {
        const leftRevision = Number(left.match(/v(\d+)\.json$/)?.[1] ?? 0);
        const rightRevision = Number(right.match(/v(\d+)\.json$/)?.[1] ?? 0);
        return rightRevision - leftRevision;
      });
    const latest = files[0];
    return latest
      ? parseJsonFile(path.join(directory, latest), schema)
      : undefined;
  }

  async readLatestForecast(
    raceId: string,
    stage: "core" | "final",
  ): Promise<ForecastSnapshot | undefined> {
    return this.readLatest(
      path.join(this.raceDirectory(raceId), "forecasts"),
      `${stage}-v`,
      forecastSnapshotSchema,
    );
  }

  async readLatestStrategy(raceId: string): Promise<BetStrategy | undefined> {
    return this.readLatest(
      path.join(this.raceDirectory(raceId), "strategies"),
      "strategy-v",
      betStrategySchema,
    );
  }

  async readResult(raceId: string): Promise<RaceResult | undefined> {
    const filename = path.join(this.raceDirectory(raceId), "result.json");
    return (await exists(filename))
      ? parseJsonFile(filename, raceResultSchema)
      : undefined;
  }

  async readLatestPurchase(
    raceId: string,
  ): Promise<PurchaseRecord | undefined> {
    return this.readLatest(
      path.join(this.raceDirectory(raceId), "purchases"),
      "purchase-v",
      purchaseRecordSchema,
    );
  }

  async readLatestReview(raceId: string): Promise<Review | undefined> {
    return this.readLatest(
      path.join(this.raceDirectory(raceId), "reviews"),
      "review-v",
      reviewSchema,
    );
  }

  async listRaceIds(): Promise<string[]> {
    const directory = path.join(this.recordsRoot, "races");
    if (!(await exists(directory))) return [];
    const entries = await readdir(directory, { withFileTypes: true });
    return entries
      .filter((entry) => entry.isDirectory())
      .map((entry) => entry.name)
      .sort();
  }

  async listDossiersByDate(targetDate: string): Promise<RaceDossier[]> {
    const dossiers = await Promise.all(
      (await this.listRaceIds()).map(async (id) => {
        try {
          return await this.readDossier(id);
        } catch {
          return undefined;
        }
      }),
    );
    return dossiers.filter(
      (dossier): dossier is RaceDossier => dossier?.race.date === targetDate,
    );
  }
}
