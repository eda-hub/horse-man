import { describe, expect, it } from "vitest";

import {
  assertDossierIntegrity,
  assertResultIntegrity,
  assertReviewIntegrity,
} from "../src/integrity.js";
import { raceDossierSchema } from "../src/schemas.js";
import { dossier, result, review } from "./fixtures.js";

describe("record integrity", () => {
  it("rejects duplicate runner and evidence identifiers", () => {
    const duplicateRunner = dossier();
    duplicateRunner.runners[1]!.number = duplicateRunner.runners[0]!.number;
    expect(() => assertDossierIntegrity(duplicateRunner)).toThrow("馬番が重複");

    const duplicateEvidence = dossier();
    duplicateEvidence.evidence[1]!.id = duplicateEvidence.evidence[0]!.id;
    expect(() => assertDossierIntegrity(duplicateEvidence)).toThrow(
      "Evidence IDが重複",
    );
  });

  it("accepts overseas venue, timezone, and currency data", () => {
    const overseas = dossier({
      id: "2026-08-29_BHA_ASC_4",
      organizer: "BHA",
      country: "GB",
      trackCode: "ASC",
      trackName: "Ascot",
      raceNumber: 4,
      scheduledStart: "2026-08-29T15:00:00+01:00",
      timezone: "Europe/London",
      currency: "GBP",
    });
    expect(raceDossierSchema.parse(overseas).race.currency).toBe("GBP");
    expect(() => assertDossierIntegrity(overseas)).not.toThrow();
  });

  it("rejects duplicate result rows unless a dead heat is explicit", () => {
    const invalid = result();
    invalid.finishers[1]!.position = 1;
    expect(() => assertResultIntegrity(invalid)).toThrow(
      "同着指定のない着順が重複",
    );
    invalid.finishers[1]!.deadHeat = true;
    expect(() => assertResultIntegrity(invalid)).not.toThrow();
  });

  it("keeps experimental hypotheses attached to the reviewed race", () => {
    const invalid = review();
    invalid.hypothesis = {
      id: "hypothesis-1",
      name: "テスト",
      raceId: "different-race",
      targetDecision: "展開判断",
      applicationConditions: ["平均ペース"],
      expectedEffect: "精度改善",
      coreDifference: "補正なし",
      sampleCount: 1,
      status: "candidate",
    };
    expect(() => assertReviewIntegrity(invalid)).toThrow(
      "raceIdが一致しません",
    );
  });
});
