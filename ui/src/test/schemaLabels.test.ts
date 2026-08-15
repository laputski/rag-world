/**
 * The guard over the labels of the dimension schema.
 *
 * The schema is declared in `core/dimensions_schema.py` and reaches the interface
 * as codes. Their labels live in the localisation and are written by hand, so they
 * fall behind the schema at the first new value. The divergence does not break the
 * page for a developer: the page simply shows the reader a bare code.
 *
 * The check compares the schema with the labels in both directions. A missing
 * label means a code on the page; a stray one means a value left the schema while
 * its label was forgotten and now outlives its dimension.
 */

import { describe, expect, it } from "vitest";
import { DIMENSIONS, STRATA } from "../schema.generated";
import ru from "../i18n/ru/schema.json";
import en from "../i18n/en/schema.json";
import ruUi from "../i18n/ru.json";
import enUi from "../i18n/en.json";

const LANGUAGES = { ru, en } as const;

describe.each(Object.entries(LANGUAGES))("the schema labels (%s)", (lang, labels) => {
  it("every dimension of the schema is named and glossed", () => {
    const missing = DIMENSIONS.filter((d) => {
      const label = (labels.dimension as Record<string, { name?: string; question?: string }>)[d.code];
      return !label?.name || !label?.question;
    }).map((d) => d.code);
    expect(missing, `${lang}: dimensions with no label reach a card as bare codes`).toEqual([]);
  });

  it("every value of every dimension is named", () => {
    const missing: string[] = [];
    for (const dim of DIMENSIONS) {
      const table = (labels.value as Record<string, Record<string, string>>)[dim.code] ?? {};
      for (const value of dim.values) {
        if (!table[value]) missing.push(`${dim.code}.${value}`);
      }
    }
    expect(missing, `${lang}: values with no label reach a card as bare codes`).toEqual([]);
  });

  it("no stray labels: a label with no value outlives its dimension", () => {
    const known = new Map(DIMENSIONS.map((d) => [d.code, new Set<string>(d.values)]));
    const stale: string[] = [];
    for (const [code, table] of Object.entries(labels.value as Record<string, Record<string, string>>)) {
      const values = known.get(code);
      if (!values) {
        stale.push(code);
        continue;
      }
      for (const value of Object.keys(table)) {
        if (!values.has(value)) stale.push(`${code}.${value}`);
      }
    }
    for (const code of Object.keys(labels.dimension)) {
      if (!known.has(code)) stale.push(code);
    }
    expect(stale, `${lang}: labels matching nothing in the schema`).toEqual([]);
  });

});

/*
  The demand that a label differ from its code makes sense only for Russian: in
  English the codes are English words, and the label `server` → "Server" is
  correct. A Russian label left in Latin, on the other hand, is precisely what the
  labels exist against: an untranslated code on the page.
*/
describe("the Russian labels are translated", () => {
  const cyrillic = /[а-яё]/i;

  it("every dimension name is written in Cyrillic", () => {
    const latin = DIMENSIONS.filter(
      (d) => !cyrillic.test(ru.dimension[d.code as keyof typeof ru.dimension].name)
    ).map((d) => d.code);
    expect(latin, "a Russian dimension name is still in Latin").toEqual([]);
  });

  it("every value name is written in Cyrillic", () => {
    const latin: string[] = [];
    for (const dim of DIMENSIONS) {
      const table = (ru.value as Record<string, Record<string, string>>)[dim.code] ?? {};
      for (const [value, label] of Object.entries(table)) {
        if (!cyrillic.test(label)) latin.push(`${dim.code}.${value}`);
      }
    }
    expect(latin, "a Russian value name is still in Latin").toEqual([]);
  });
});

describe("the strata", () => {
  it("are named in both languages", () => {
    for (const [lang, table] of Object.entries({ ru: ruUi, en: enUi })) {
      const names = (table as { stratum: Record<string, string> }).stratum;
      const missing = STRATA.filter((s) => !names[s.code]).map((s) => s.code);
      expect(missing, `${lang}: a stratum with no name`).toEqual([]);
    }
  });
});

describe("both languages describe one and the same schema", () => {
  it("the key sets coincide", () => {
    expect(Object.keys(ru.dimension).sort()).toEqual(Object.keys(en.dimension).sort());
    expect(Object.keys(ru.value).sort()).toEqual(Object.keys(en.value).sort());
    for (const code of Object.keys(ru.value)) {
      const left = ru.value as Record<string, Record<string, string>>;
      const right = en.value as Record<string, Record<string, string>>;
      expect(Object.keys(left[code]).sort(), `the values of ${code}`).toEqual(
        Object.keys(right[code]).sort()
      );
    }
  });
});

/**
 * The base configuration: the reference point has to be visible and explained.
 *
 * The portal pointed at it everywhere — "as in the base configuration", "no
 * departures from the base" — and showed it nowhere. A default without an
 * explanation is a claim with no grounds, which the portal forbids itself
 * elsewhere.
 */
describe("the base configuration", () => {
  it("every dimension explains why its value is the base one", () => {
    for (const [lang, dict] of [["ru", ruUi], ["en", enUi]] as const) {
      const why = (dict as { baseConfig: { why: Record<string, string> } }).baseConfig.why;
      const missing = DIMENSIONS.filter((d) => !why[d.code]?.trim()).map((d) => d.code);
      expect(missing, `${lang}: a base value with no explanation`).toEqual([]);
    }
  });

  it("no more explanations than dimensions: a stray one outlives its dimension", () => {
    const codes = new Set(DIMENSIONS.map((d) => d.code));
    for (const [lang, dict] of [["ru", ruUi], ["en", enUi]] as const) {
      const why = (dict as { baseConfig: { why: Record<string, string> } }).baseConfig.why;
      const stale = Object.keys(why).filter((code) => !codes.has(code));
      expect(stale, `${lang}: an explanation with no dimension`).toEqual([]);
    }
  });

  it("the base value of every dimension belongs to its own catalogue", () => {
    const broken = DIMENSIONS.filter((d) => !d.values.includes(d.default)).map((d) => d.code);
    expect(broken, "a base value outside the value catalogue").toEqual([]);
  });

  /*
    The meaning of the reference point rests on a base value denoting the absence
    of a technique. Six dimensions are excluded by name: for them "do nothing" is
    undefined, and the section says so to the reader. The list is closed, so a new
    exception has to go through an edit to this test and through review.
  */
  it("a base value means the absence of a technique, six dimensions apart", () => {
    const mustExist = new Set(["A1", "A5", "A7", "C1", "D2", "G2"]);
    const absence = new Set([
      "none", "identity", "static", "single_shot", "single_store", "flat",
      "fixed", "snapshot", "natural_order", "single_pass", "no_refusal",
      "open", "frozen",
    ]);
    const unexpected = DIMENSIONS
      .filter((d) => !mustExist.has(d.code) && !absence.has(d.default))
      .map((d) => `${d.code}=${d.default}`);
    expect(
      unexpected,
      "a value meaning a technique has become the base: the reference point flipped"
    ).toEqual([]);
  });
});
