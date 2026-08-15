import { describe, expect, it } from "vitest";
import ru from "../i18n/ru.json";
import en from "../i18n/en.json";
import techRu from "../i18n/ru/tech.json";

/** A flat list of the keys of a nested dictionary: "registry.title" and so on. */
function flatten(obj: Record<string, unknown>, prefix = ""): string[] {
  return Object.entries(obj).flatMap(([key, value]) => {
    const path = prefix ? `${prefix}.${key}` : key;
    return value && typeof value === "object" && !Array.isArray(value)
      ? flatten(value as Record<string, unknown>, path)
      : [path];
  });
}

describe("the localisation", () => {
  /*
    The keys are compared by stem, without the plural suffix. Grammar sets the
    forms and languages differ: Russian needs `_one`, `_few` and `_many`, English
    needs `_one` and `_other`. A direct comparison would declare that difference a
    missing translation when nothing is missing.
  */
  const PLURAL_SUFFIX = /_(zero|one|two|few|many|other)$/;
  const base = (key: string) => key.replace(PLURAL_SUFFIX, "");

  it("the Russian and English dictionaries cover the same messages", () => {
    const ruKeys = [...new Set(flatten(ru).map(base))].sort();
    const enKeys = [...new Set(flatten(en).map(base))].sort();
    const missingInEn = ruKeys.filter((k) => !enKeys.includes(k));
    const missingInRu = enKeys.filter((k) => !ruKeys.includes(k));
    expect({ missingInEn, missingInRu }).toEqual({ missingInEn: [], missingInRu: [] });
  });

  it("a counted message carries every plural form its language needs", () => {
    const required = { ru: ["one", "few", "many"], en: ["one", "other"] } as const;
    for (const [locale, dict] of [["ru", ru], ["en", en]] as const) {
      const keys = flatten(dict);
      const plural = [...new Set(keys.filter((k) => PLURAL_SUFFIX.test(k)).map(base))];
      for (const stem of plural) {
        const missing = required[locale].filter((form) => !keys.includes(`${stem}_${form}`));
        expect(missing, `${locale}: ${stem}`).toEqual([]);
      }
    }
  });

  it("no value is empty", () => {
    for (const [locale, dict] of [["ru", ru], ["en", en]] as const) {
      for (const key of flatten(dict)) {
        const value = key
          .split(".")
          .reduce<unknown>((acc, part) => (acc as Record<string, unknown>)[part], dict);
        expect(String(value).trim(), `${locale}: ${key}`).not.toBe("");
      }
    }
  });

  it("the maturity scale is described in full", () => {
    for (const level of ["L0", "L1", "L2", "L3", "L4", "L5", "L6", "unknown"]) {
      expect(ru.level).toHaveProperty(level);
    }
  });

  it("the strata are described in full", () => {
    for (const stratum of ["A", "B", "C", "D", "E", "F", "G"]) {
      expect(ru.stratum).toHaveProperty(stratum);
    }
  });
});

describe("the prose of the cards", () => {
  const prose = techRu as Record<string, Record<string, string>>;

  it("is not empty", () => {
    expect(Object.keys(prose).length).toBeGreaterThan(0);
  });

  it("every record carries at least one text", () => {
    const empty = Object.entries(prose)
      .filter(([, value]) => Object.values(value).every((v) => !v || !v.trim()))
      .map(([key]) => key);
    expect(empty).toEqual([]);
  });

  it("uses only known fields", () => {
    const allowed = new Set([
      "short", "full", "problem", "barriers", "solutions", "maturityNote",
    ]);
    const unexpected = Object.entries(prose).flatMap(([id, value]) =>
      Object.keys(value).filter((k) => !allowed.has(k)).map((k) => `${id}.${k}`)
    );
    expect(unexpected).toEqual([]);
  });
});
