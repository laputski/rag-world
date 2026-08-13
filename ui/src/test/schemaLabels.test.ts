/**
 * Сторож подписей к схеме измерений.
 *
 * Схема задана в `core/dimensions_schema.py` и приходит в интерфейс кодами.
 * Подписи к ним лежат в локализации и пишутся руками, поэтому расходятся с
 * схемой при первом же новом значении. Расхождение не ломает сборку и не видно
 * разработчику: страница просто показывает читателю голый код вместо названия.
 *
 * Проверка сверяет схему с подписями в обе стороны. Недостающая подпись
 * означает код на странице; лишняя означает, что значение из схемы убрали, а
 * подпись забыли, и она переживёт своё измерение.
 */

import { describe, expect, it } from "vitest";
import { DIMENSIONS, STRATA } from "../schema.generated";
import ru from "../i18n/ru/schema.json";
import en from "../i18n/en/schema.json";
import ruUi from "../i18n/ru.json";
import enUi from "../i18n/en.json";

const LANGUAGES = { ru, en } as const;

describe.each(Object.entries(LANGUAGES))("подписи схемы (%s)", (lang, labels) => {
  it("каждое измерение схемы названо и пояснено", () => {
    const missing = DIMENSIONS.filter((d) => {
      const label = (labels.dimension as Record<string, { name?: string; question?: string }>)[d.code];
      return !label?.name || !label?.question;
    }).map((d) => d.code);
    expect(missing, `${lang}: измерения без подписи выйдут на карточку кодом`).toEqual([]);
  });

  it("каждое значение каждого измерения названо", () => {
    const missing: string[] = [];
    for (const dim of DIMENSIONS) {
      const table = (labels.value as Record<string, Record<string, string>>)[dim.code] ?? {};
      for (const value of dim.values) {
        if (!table[value]) missing.push(`${dim.code}.${value}`);
      }
    }
    expect(missing, `${lang}: значения без подписи выйдут на карточку кодом`).toEqual([]);
  });

  it("лишних подписей нет: подпись без значения в схеме переживает своё измерение", () => {
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
    expect(stale, `${lang}: подписи, которым в схеме ничего не соответствует`).toEqual([]);
  });

});

/*
  Требование «подпись отличается от кода» осмысленно только по-русски. В
  английском коды и есть английские слова, и подпись `server` → «Server»
  правильна. Русская же подпись, оставшаяся латиницей, означает ровно то, от
  чего подписи и заведены: непереведённый код на странице.
*/
describe("русские подписи переведены", () => {
  const cyrillic = /[а-яё]/i;

  it("каждое имя измерения написано кириллицей", () => {
    const latin = DIMENSIONS.filter(
      (d) => !cyrillic.test(ru.dimension[d.code as keyof typeof ru.dimension].name)
    ).map((d) => d.code);
    expect(latin, "русское имя измерения осталось латиницей").toEqual([]);
  });

  it("каждое название значения написано кириллицей", () => {
    const latin: string[] = [];
    for (const dim of DIMENSIONS) {
      const table = (ru.value as Record<string, Record<string, string>>)[dim.code] ?? {};
      for (const [value, label] of Object.entries(table)) {
        if (!cyrillic.test(label)) latin.push(`${dim.code}.${value}`);
      }
    }
    expect(latin, "русское название значения осталось латиницей").toEqual([]);
  });
});

describe("страты", () => {
  it("названы в обоих языках", () => {
    for (const [lang, table] of Object.entries({ ru: ruUi, en: enUi })) {
      const names = (table as { stratum: Record<string, string> }).stratum;
      const missing = STRATA.filter((s) => !names[s.code]).map((s) => s.code);
      expect(missing, `${lang}: страта без названия`).toEqual([]);
    }
  });
});

describe("оба языка описывают одну и ту же схему", () => {
  it("наборы ключей совпадают", () => {
    expect(Object.keys(ru.dimension).sort()).toEqual(Object.keys(en.dimension).sort());
    expect(Object.keys(ru.value).sort()).toEqual(Object.keys(en.value).sort());
    for (const code of Object.keys(ru.value)) {
      const left = ru.value as Record<string, Record<string, string>>;
      const right = en.value as Record<string, Record<string, string>>;
      expect(Object.keys(left[code]).sort(), `значения ${code}`).toEqual(
        Object.keys(right[code]).sort()
      );
    }
  });
});
