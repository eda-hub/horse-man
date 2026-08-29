import { mkdtemp, readFile, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";

import { describe, expect, it } from "vitest";

import {
  calculateCycleSummary,
  renderCycleCsv,
  renderCycleMarkdown,
  renderRaceReport,
} from "../src/reports.js";
import { HorsemanStore } from "../src/storage.js";
import {
  dossier,
  forecast,
  purchase,
  result,
  review,
  strategy,
} from "./fixtures.js";

describe("immutable storage", () => {
  it("verifies the source rules and refuses snapshot overwrite", async () => {
    const recordsRoot = await mkdtemp(path.join(tmpdir(), "horseman-records-"));
    const store = new HorsemanStore({
      repositoryRoot: "/workspace",
      recordsRoot,
    });
    await expect(store.verifyRules()).resolves.toMatch(/^[a-f0-9]{64}$/);
    await store.saveDossier(dossier());
    await expect(store.saveDossier(dossier())).rejects.toThrow(
      "上書きできません",
    );
    const stored = await readFile(
      path.join(recordsRoot, "races", dossier().race.id, "dossier.json"),
      "utf8",
    );
    expect(stored).toContain('"kind": "race-dossier"');
  });

  it("aborts writes when the rules source hash changes", async () => {
    const root = await mkdtemp(path.join(tmpdir(), "horseman-tampered-rules-"));
    const rulesFile = path.join(root, "rules.md");
    await writeFile(rulesFile, "tampered rules");
    const store = new HorsemanStore({
      recordsRoot: path.join(root, "records"),
      rulesFile,
    });
    await expect(store.saveDossier(dossier())).rejects.toThrow(
      "SHA-256が不一致",
    );
  });

  it("stores and reads the complete race lifecycle", async () => {
    const recordsRoot = await mkdtemp(
      path.join(tmpdir(), "horseman-lifecycle-"),
    );
    const store = new HorsemanStore({
      repositoryRoot: "/workspace",
      recordsRoot,
    });
    await store.saveDossier(dossier());
    await store.saveForecast(forecast("core"));
    await store.saveForecast(forecast("final"));
    await store.saveStrategy(strategy());
    await store.saveResult(result());
    await store.savePurchase(purchase());
    await store.saveReview(review());
    expect(
      (await store.readLatestForecast(dossier().race.id, "final"))?.stage,
    ).toBe("final");
    expect(
      (await store.readResult(dossier().race.id))?.finishers[0]?.runnerNumber,
    ).toBe(1);
  });
});

describe("reports", () => {
  const entry = {
    dossier: dossier(),
    core: forecast("core"),
    final: forecast("final"),
    strategy: strategy(),
    result: result(),
    purchase: purchase(),
    review: review(),
  };

  it("renders the rule-required single race sections", () => {
    const report = renderRaceReport(entry);
    expect(report).toContain("予想を決める3大要因");
    expect(report).toContain("Coreからの変更");
    expect(report).toContain("馬依存率");
    expect(report).toContain("反実仮想");
  });

  it("aggregates prospective forecasts and omits reconstructed forecasts", () => {
    const reconstructed = {
      ...entry,
      final: forecast("final", { provenance: "reconstructed" }),
    };
    const summary = calculateCycleSummary([entry, reconstructed]);
    expect(summary.raceCount).toBe(1);
    expect(summary.coreTop1Wins).toBe(1);
    expect(summary.finalTop1Wins).toBe(1);
    expect(summary.finalTop3WinnerCoverage).toBe(1);
    expect(summary.byCategory.primary?.roi).toBe(3);
    expect(summary.diagnostics.mostLikely.wins).toBe(1);
    expect(summary.diagnostics.bestValue.wins).toBe(0);
    expect(summary.diagnostics.byTicketType.win?.roi).toBe(3);
    expect(summary.diagnostics.liveTrack.unusedRaces).toBe(1);
    expect(renderCycleMarkdown(summary, "2026-08-16", "2026-08-29")).toContain(
      "確率キャリブレーション",
    );
    expect(renderCycleCsv(summary)).toContain("summary,raceCount,1");
  });
});
