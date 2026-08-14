/** Loading the portal's data.
 *
 * The portal is static: the data is read from artefacts built in advance and
 * sitting beside the build. There is no live server, so a source failing does
 * not make the portal fail — it only makes the data age, which the artefact
 * reports through its build date and its staleness mark.
 */

import type {
  Candidate,
  DigestIssue,
  ResidualMechanism,
  MaturityArtifact,
  RegistryChange,
  RegistryStats,
  RegistryTechnology,
} from "./types";

const DATA = "/data";

async function loadJson<T>(name: string): Promise<T> {
  const resp = await fetch(`${DATA}/${name}`);
  if (!resp.ok) {
    throw new Error(`${resp.status}: could not load ${name}`);
  }
  return (await resp.json()) as T;
}

/** The maturity map: technologies as points with level, attention and history. */
export async function getMaturityMap(): Promise<MaturityArtifact> {
  return loadJson<MaturityArtifact>("map.json");
}

/** The whole technology registry; filtering happens in the browser. */
export async function getRegistry(): Promise<{
  count: number;
  built_at: string;
  technologies: RegistryTechnology[];
}> {
  return loadJson("registry.json");
}

/** The chronicle of registry changes. */
/**
 * One registry record as a file of its own.
 *
 * A card used to read the whole registry for a single record, that is, eight
 * hundred kilobytes for the page people most often arrive at from an outside
 * link. A separate file costs about ten kilobytes and carries exactly the same
 * record.
 */
export async function getTechnology(id: string): Promise<RegistryTechnology> {
  const payload = await loadJson<{ technology: RegistryTechnology }>(`tech/${id}.json`);
  return payload.technology;
}

export async function getChanges(): Promise<{
  built_at: string;
  changes: RegistryChange[];
}> {
  return loadJson("changes.json");
}

/** The summary: distribution by level, coverage, freshness. */
export async function getStats(): Promise<RegistryStats> {
  return loadJson<RegistryStats>("stats.json");
}

/** The digest issues, newest first. */
export async function getDigest(): Promise<{
  built_at: string;
  issues: DigestIssue[];
}> {
  return loadJson("digest.json");
}

/** The residual queue: mechanisms the schema does not express. */
/** Candidates for the registry: work found by the catalogue, awaiting a verdict. */
export async function getCandidates(): Promise<{
  built_at: string;
  candidates: Candidate[];
}> {
  return loadJson("candidates.json");
}

export async function getResiduals(): Promise<{
  built_at: string;
  candidate_threshold: number;
  mechanisms: ResidualMechanism[];
}> {
  return loadJson("residuals.json");
}
