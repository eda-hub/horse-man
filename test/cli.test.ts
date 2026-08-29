import { mkdtemp, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";

import { afterEach, describe, expect, it, vi } from "vitest";

import { main } from "../src/cli.js";
import { canonicalJson } from "../src/storage.js";
import {
  dossier,
  forecast,
  purchase,
  result,
  review,
  strategy,
} from "./fixtures.js";

describe("CLI lifecycle", () => {
  afterEach(() => vi.restoreAllMocks());

  it("records, reports, and aggregates a complete prospective race", async () => {
    const root = await mkdtemp(path.join(tmpdir(), "horseman-cli-"));
    const records = path.join(root, "records");
    const files = {
      dossier: path.join(root, "dossier.json"),
      core: path.join(root, "core.json"),
      final: path.join(root, "final.json"),
      strategy: path.join(root, "strategy.json"),
      result: path.join(root, "result.json"),
      purchase: path.join(root, "purchase.json"),
      review: path.join(root, "review.json"),
    };
    await Promise.all([
      writeFile(files.dossier, canonicalJson(dossier())),
      writeFile(files.core, canonicalJson(forecast("core"))),
      writeFile(files.final, canonicalJson(forecast("final"))),
      writeFile(files.strategy, canonicalJson(strategy())),
      writeFile(files.result, canonicalJson(result())),
      writeFile(files.purchase, canonicalJson(purchase())),
      writeFile(files.review, canonicalJson(review())),
    ]);
    const output: string[] = [];
    vi.spyOn(process.stdout, "write").mockImplementation((chunk) => {
      output.push(String(chunk));
      return true;
    });
    vi.spyOn(process.stderr, "write").mockImplementation(() => true);
    const invoke = (...args: string[]) =>
      main(["node", "horseman", "--records", records, ...args]);
    const raceId = dossier().race.id;

    await invoke("rules", "verify");
    await invoke("race", "import", files.dossier);
    await invoke(
      "forecast",
      "save",
      "--race",
      raceId,
      "--stage",
      "core",
      "--input",
      files.core,
    );
    await invoke(
      "forecast",
      "save",
      "--race",
      raceId,
      "--stage",
      "final",
      "--input",
      files.final,
    );
    await invoke(
      "strategy",
      "save",
      "--race",
      raceId,
      "--input",
      files.strategy,
    );
    await invoke("result", "import", files.result);
    await invoke(
      "purchase",
      "save",
      "--race",
      raceId,
      "--input",
      files.purchase,
    );
    await invoke("review", "save", "--race", raceId, "--input", files.review);
    await invoke("report", "race", "--race", raceId);
    await invoke("screen", "report", "--date", "2026-08-29");
    await invoke(
      "cycle",
      "report",
      "--from",
      "2026-08-16",
      "--to",
      "2026-08-29",
      "--format",
      "json",
    );

    const combined = output.join("");
    expect(combined).toContain("rules ok");
    expect(combined).toContain("予想を決める3大要因");
    expect(combined).toContain("開催全体スクリーニング");
    expect(combined).toContain('"raceCount": 1');
  });
});
