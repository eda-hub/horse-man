import type { RaceDossier, RaceResult, Review } from "./schemas.js";

function duplicates<T>(values: T[]): T[] {
  const seen = new Set<T>();
  const duplicateValues = new Set<T>();
  for (const value of values) {
    if (seen.has(value)) duplicateValues.add(value);
    seen.add(value);
  }
  return [...duplicateValues];
}

export function assertDossierIntegrity(dossier: RaceDossier): void {
  const duplicateRunners = duplicates(
    dossier.runners.map((runner) => runner.number),
  );
  if (duplicateRunners.length)
    throw new Error(
      `出走馬の馬番が重複しています: ${duplicateRunners.join(", ")}`,
    );
  const duplicateEvidence = duplicates(
    dossier.evidence.map((evidence) => evidence.id),
  );
  if (duplicateEvidence.length)
    throw new Error(
      `Evidence IDが重複しています: ${duplicateEvidence.join(", ")}`,
    );
  if (
    Date.parse(dossier.informationCutoff) >
    Date.parse(dossier.race.scheduledStart)
  ) {
    throw new Error(
      "レース情報のinformationCutoffは発走予定時刻以前である必要があります",
    );
  }
}

export function assertResultIntegrity(result: RaceResult): void {
  const duplicateRunners = duplicates(
    result.finishers.map((finisher) => finisher.runnerNumber),
  );
  if (duplicateRunners.length)
    throw new Error(
      `結果の馬番が重複しています: ${duplicateRunners.join(", ")}`,
    );
  const duplicatePositions = duplicates(
    result.finishers
      .filter((finisher) => !finisher.deadHeat)
      .map((finisher) => finisher.position),
  );
  if (duplicatePositions.length)
    throw new Error(
      `同着指定のない着順が重複しています: ${duplicatePositions.join(", ")}`,
    );
  if (!result.finishers.some((finisher) => finisher.position === 1))
    throw new Error("結果に1着馬がありません");
}

export function assertReviewIntegrity(review: Review): void {
  if (review.hypothesis && review.hypothesis.raceId !== review.raceId) {
    throw new Error("Experimental仮説と回顧のraceIdが一致しません");
  }
  if (
    review.primaryError &&
    review.secondaryErrors.includes(review.primaryError)
  ) {
    throw new Error("同じエラーを主因と副因へ重複指定できません");
  }
}
