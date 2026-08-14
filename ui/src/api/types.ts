/** The data types of the portal.
 *
 * The portal is static: every structure below arrives from artefacts built in
 * advance (`public/data/*.json`) rather than from a live server.
 *
 * An absent quantity is `null` everywhere and never a zero. A zero would say the
 * quantity was measured and came out zero; for "not measured" that is untrue,
 * and the views are obliged to show the difference.
 */

/** A record of the technology registry. */
export interface RegistryTechnology {
  id: string;
  name: string;
  aliases: string[];
  /** The kind: paradigm | architecture | technique | tool | artifact | attack. */
  kind: string;
  family: string | null;
  /** The strata A–G the technology's contribution belongs to. */
  groups: string[];
  /** The identifier of the localised prose of the card. */
  prose_id: string | null;
  /**
   * The prose laid into the artefact in both languages.
   *
   * The portal takes its texts from the localisation resources; these fields
   * exist for a consumer of the published data. The registry, read without the
   * portal, consisted of codes and levels without a single sentence saying what
   * a technology was.
   */
  summary?: string | null;
  summary_en?: string | null;
  description?: string | null;
  description_en?: string | null;
  first_published: string | null;
  /** The dimension values: the field two technologies are compared by. */
  configuration: Record<string, string>;
  /** Mechanisms the schema does not express, worded from the vocabulary. */
  residual: string[];
  residual_en: string[];
  /** Dimensions whose value is chosen at run time or by mode. */
  configuration_variable: string[];
  /** Dimensions inapplicable to the object: they hold no value at all. */
  configuration_inapplicable: string[];
  /**
   * When the configuration was read out of the primary sources; null means it
   * never was. It tells a value checked against a source from a base one: the
   * two look alike and assert different things.
   */
  configuration_reviewed: string | null;
  /** The justification: why a dimension holds the value it does. */
  parse_notes: ParseNote[];
  links: RegistryLink[];
  /** The computed maturity level; null means it was never computed. */
  level: string | null;
  confidence: number | null;
  /** `computed` by the rule, `manual` when a person entered it. */
  evidence_basis: string | null;
  attention: number | null;
  attention_raw: number | null;
  attention_cohort: string | null;
  evidence_count: number;
  evidence: EvidenceRecord[];
  /** The output of the rule: which levels are satisfied and which are not. */
  level_reason: LevelReason | null;
}

export interface EvidenceRecord {
  type: string;
  value: string | null;
  source: string;
  fetched_at: string;
  /** `auto` when a collector gathered it, `manual` when a person entered it. */
  obtained_by: string;
}

export interface LevelReason {
  satisfied: string[];
  missing: string[];
  confidence: number;
  evidence_basis: string;
}

export interface RegistryLink {
  url: string;
  kind: string;
  label: string | null;
  status: string;
  verified_at: string | null;
}

/** One point of a level change in time. */
export interface LevelChangePoint {
  level: string;
  at: string;
}

/** A technology as a point on the maturity map. */
export interface MaturityPoint {
  id: string;
  name: string;
  kind: string;
  /** The primary stratum: it sets the colour of the point. */
  group: string | null;
  groups: string[];
  level: string | null;
  confidence: number | null;
  evidence_basis: string | null;
  /** Attention: the citation velocity against the median of its own year;
   *  null when there is no data. */
  attention: number | null;
  /** The measured citation velocity, before normalisation. */
  attention_raw: number | null;
  /** The year of the subgroup it was normalised by; null when there was none. */
  attention_cohort: string | null;
  /* Spread is deliberately absent. The field existed and set the size of a
     point, and no record had a quantity behind it. The detail, and the reason
     there is nothing to fill it with, sits in scripts/build_artifacts.py beside
     ATTENTION_METRIC. */
  first_published: string | null;
  prose_id: string | null;
  history: LevelChangePoint[];
}

/** The maturity map artefact. */
export interface MaturityArtifact {
  /** When the artefact was built, in ISO form. */
  built_at: string;
  /** The version of the rule that derives a level. */
  rule_version: string;
  levels: string[];
  strata: { code: string; name: string }[];
  points: MaturityPoint[];
  count: number;
  /** Whether the data counts as stale. */
  stale: boolean;
}

/** One change in the chronicle. */
export interface RegistryChange {
  technology_id: string;
  name: string;
  kind: "level_up" | "level_down" | "added";
  level_before: string | null;
  level_after: string;
  evidence: { type?: string; source?: string }[];
  changed_at: string;
}

/** The summary of the registry's state. */
export interface RegistryStats {
  built_at: string;
  total: number;
  by_level: Record<string, number>;
  by_kind: Record<string, number>;
  by_stratum: Record<string, number>;
  with_evidence: number;
  with_level: number;
  with_attention: number;
  evidence_total: number;
  freshest_evidence: string | null;
  stale: boolean;
}

/**
 * A digest issue.
 *
 * Generated from a template over the registry data, with no language model: it
 * retells what has already been computed, and there is nothing in it to invent.
 * That is why it is published without review by a person.
 *
 * An issue is never rebuilt: it asserts what was true on the day it came out.
 */
export interface DigestIssue {
  issued_at: string;
  /** The start of the period; null for the first issue, which covers everything. */
  since: string | null;
  text: string;
  /** The same issue in English. Empty for issues published before the localisation. */
  text_en?: string;
  added: DigestMove[];
  promoted: DigestMove[];
  demoted: DigestMove[];
  evidence_added: number;
  evidence_by_type: Record<string, number>;
  links_checked: number;
  links_broken: number;
  by_level: Record<string, number>;
  total: number;
}

export interface DigestMove {
  technology_id: string;
  name: string;
  level_before: string | null;
  level_after: string;
}

/**
 * The justification of one decision of the reading.
 *
 * The split is deliberate: `did` is checked against the source and `why` against
 * the dimension schema. Merged into one phrase they read as a claim about the
 * technology, whereas half of it is a claim about how the schema describes it.
 */
export interface ParseNote {
  code?: string;
  residual?: string;
  residual_term?: string | null;
  residual_term_en?: string | null;
  to?: string;
  variable?: boolean;
  inapplicable?: boolean;
  /** What the system does, checked against the source. */
  did: string;
  did_en?: string;
  /** Why the value follows from that, checked against the schema. */
  why: string;
  why_en?: string;
  /** Which value did not fit, and why. */
  instead?: string;
  instead_en?: string;
  /** A place where the source admits another reading. */
  question?: string;
  question_en?: string;
  source: string;
  source_en?: string;
}

/**
 * A mechanism the schema does not express.
 *
 * The residual queue is how the schema grows from observation rather than from
 * imagination. A mechanism that has to be written down again and again marks a
 * place where the schema is too small; one met once is a particularity of a
 * single work.
 */
export interface ResidualMechanism {
  id: string;
  term: string;
  term_en: string;
  /** Why the schema does not express it. */
  note: string;
  note_en: string;
  count: number;
  technologies: { id: string; name: string }[];
  /** It reached the threshold of mentions and is proposed as a dimension. */
  candidate: boolean;
}

/**
 * A work found by the catalogue and awaiting a verdict.
 *
 * A candidate is a supposition about a technology, not a technology. The
 * decision that this is a new architecture rather than an application of an
 * existing one belongs to a person: a rule errs here, and the price of the error
 * is a registry record about something that does not exist.
 */
/**
 * How well a candidate fits the registry.
 *
 * An order of review rather than a claim about the work. The terms are shown
 * beside the number: the score without them would ask to be believed.
 */
export interface CandidateSignal {
  /** The code of a signal; the phrase is assembled by the localisation. */
  code: string;
  tasks?: string[];
  count?: number;
}

export interface CandidateFit {
  score: number;
  signals: CandidateSignal[];
}

export interface Candidate {
  arxiv_id: string;
  fit: CandidateFit;
  title: string;
  /** The abstract as the catalogue gives it, cut for display. */
  abstract: string;
  published: string | null;
  source: string;
  citations: number | null;
  repositories: string[];
  found_at: string;
  /** Empty until a verdict is entered. */
  verdict: string | null;
}
