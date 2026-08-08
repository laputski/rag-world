import { describe, expect, it } from "vitest";
import ru from "../i18n/ru.json";
import en from "../i18n/en.json";
import techRu from "../i18n/ru/tech.json";

/** Плоский список ключей вложенного словаря: "registry.title" и т. п. */
function flatten(obj: Record<string, unknown>, prefix = ""): string[] {
  return Object.entries(obj).flatMap(([key, value]) => {
    const path = prefix ? `${prefix}.${key}` : key;
    return value && typeof value === "object" && !Array.isArray(value)
      ? flatten(value as Record<string, unknown>, path)
      : [path];
  });
}

describe("локализация", () => {
  it("русский и английский словари имеют одинаковый состав ключей", () => {
    const ruKeys = flatten(ru).sort();
    const enKeys = flatten(en).sort();
    const missingInEn = ruKeys.filter((k) => !enKeys.includes(k));
    const missingInRu = enKeys.filter((k) => !ruKeys.includes(k));
    expect({ missingInEn, missingInRu }).toEqual({ missingInEn: [], missingInRu: [] });
  });

  it("ни одно значение не пустое", () => {
    for (const [locale, dict] of [["ru", ru], ["en", en]] as const) {
      for (const key of flatten(dict)) {
        const value = key
          .split(".")
          .reduce<unknown>((acc, part) => (acc as Record<string, unknown>)[part], dict);
        expect(String(value).trim(), `${locale}: ${key}`).not.toBe("");
      }
    }
  });

  it("шкала зрелости описана целиком", () => {
    for (const level of ["L0", "L1", "L2", "L3", "L4", "L5", "L6", "unknown"]) {
      expect(ru.level).toHaveProperty(level);
    }
  });

  it("страты описаны целиком", () => {
    for (const stratum of ["A", "B", "C", "D", "E", "F", "G"]) {
      expect(ru.stratum).toHaveProperty(stratum);
    }
  });
});

describe("проза карточек", () => {
  const prose = techRu as Record<string, Record<string, string>>;

  it("непуста", () => {
    expect(Object.keys(prose).length).toBeGreaterThan(0);
  });

  it("каждая запись несёт хотя бы один текст", () => {
    const empty = Object.entries(prose)
      .filter(([, value]) => Object.values(value).every((v) => !v || !v.trim()))
      .map(([key]) => key);
    expect(empty).toEqual([]);
  });

  it("использует только известные поля", () => {
    const allowed = new Set([
      "short", "full", "problem", "barriers", "solutions", "maturityNote",
    ]);
    const unexpected = Object.entries(prose).flatMap(([id, value]) =>
      Object.keys(value).filter((k) => !allowed.has(k)).map((k) => `${id}.${k}`)
    );
    expect(unexpected).toEqual([]);
  });
});
