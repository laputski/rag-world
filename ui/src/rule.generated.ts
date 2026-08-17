// GENERATED from core/maturity.py by `make artifacts`.
// Do not edit by hand: the edit would be lost and the rule would end up
// described twice, once where it is run and once where it is shown.

/** One sufficient way to reach a level. */
export interface RoadSpec {
  /** The type of evidence the road asks for. */
  evidence: string;
  /** For a publication, the least class of venue that counts. */
  venue: string | null;
  /** The level that must already hold; null where the road skips it. */
  requires: string | null;
}

export interface LevelSpec {
  level: string;
  /** Any one road suffices. An empty list means the level asks for nothing. */
  roads: RoadSpec[];
  basis: "computed" | "manual";
}

export const RULE_VERSION = "1.0.0";

export const LEVEL_RULES: LevelSpec[] = [
  { level: "L0", basis: "computed", roads: [] },
  { level: "L1", basis: "computed", roads: [{ evidence: "publication", venue: "workshop_preprint", requires: null }] },
  { level: "L2", basis: "computed", roads: [{ evidence: "publication", venue: "peer_reviewed", requires: "L1" }, { evidence: "independent_reproduction", venue: null, requires: null }, { evidence: "industrial_use", venue: null, requires: null }] },
  { level: "L3", basis: "computed", roads: [{ evidence: "repository", venue: null, requires: "L2" }, { evidence: "build_run", venue: null, requires: "L2" }] },
  { level: "L4", basis: "computed", roads: [{ evidence: "independent_reproduction", venue: null, requires: "L3" }, { evidence: "framework_presence", venue: null, requires: "L3" }, { evidence: "package_downloads", venue: null, requires: "L3" }] },
  { level: "L5", basis: "manual", roads: [{ evidence: "industrial_use", venue: null, requires: "L4" }] },
  { level: "L6", basis: "manual", roads: [{ evidence: "provider_count", venue: null, requires: "L5" }] },
];

/** How long evidence of each type stays current, in days. */
export const FRESHNESS_DAYS: Record<string, number> = {
  "publication": 1095,
  "independent_reproduction": 1095,
  "repository": 180,
  "build_run": 90,
  "framework_presence": 365,
  "package_downloads": 90,
  "industrial_use": 730,
  "provider_count": 730,
};
