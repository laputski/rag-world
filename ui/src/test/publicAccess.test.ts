// @vitest-environment jsdom
/**
 * Умолчания, которые задавались дважды и потому не работали.
 *
 * Язык по умолчанию был объявлен в настройке локализации и тут же переписан в
 * оболочке приложения. Побеждала оболочка, поэтому объявленное значение не
 * влияло ни на что: портал открывался русским, что бы ни стояло в i18n. Отказ
 * такого рода не виден ни по типам, ни по тестам представления, потому что обе
 * записи по отдельности верны.
 */

import { describe, expect, it } from "vitest";
import { DEFAULT_LANGUAGE, savedLanguage } from "../i18n/index";
// Исходники читаются средствами сборщика, а не файловой системы: типов
// node в проекте нет, а `?raw` даёт то же самое и работает и в сборке.
import MAIN from "../main.tsx?raw";
import REGISTRY_PAGE from "../pages/RegistryPage.tsx?raw";
import registry from "../../public/data/registry.json";
import ru from "../i18n/ru.json";
import en from "../i18n/en.json";

describe("язык по умолчанию", () => {
  it("английский", () => {
    expect(DEFAULT_LANGUAGE).toBe("en");
  });

  it("объявлен один раз: оболочка берёт его, а не назначает свой", () => {
    expect(MAIN, "оболочка должна ввозить умолчание из i18n").toContain("DEFAULT_LANGUAGE");
    const ownDefault = /localStorage\.getItem\(LANG_KEY\)[^;]*\?\?\s*["'](ru|en)["']/.test(MAIN);
    expect(ownDefault, "оболочка задаёт собственное умолчание языка и перекроет i18n").toBe(false);
  });

  /*
    Хранилище подставляется, а не берётся у среды: в тестовой среде его нет,
    и без подстановки проверялось бы только то, что чтение не роняет портал.
    Проверяется здесь другое: сохранённый выбор действительно читается, а его
    отсутствие даёт пустой ответ, а не выдуманный язык.
  */
  it("выбор читателя перекрывает умолчание", () => {
    const store = new Map<string, string>();
    const stub = {
      getItem: (key: string) => store.get(key) ?? null,
      setItem: (key: string, value: string) => void store.set(key, value),
      removeItem: (key: string) => void store.delete(key),
    };
    const holder = globalThis as { localStorage?: unknown };
    const original = holder.localStorage;
    holder.localStorage = stub;
    try {
      expect(savedLanguage(), "пустое хранилище не должно давать язык").toBeNull();
      stub.setItem("lang", "ru");
      expect(savedLanguage()).toBe("ru");
      stub.removeItem("lang");
      expect(savedLanguage()).toBeNull();
    } finally {
      holder.localStorage = original;
    }
  });
});

/**
 * Отбор по роду объекта в реестре.
 *
 * Перечень родов был записан руками и разошёлся с данными в обе стороны:
 * «артефакт оценки» стоял в отборе, не имея ни одной записи, а «атака» из
 * отбора выпала, хотя записи есть. Проверка требует, чтобы перечень выводился
 * из данных.
 */
describe("отбор по роду объекта", () => {
  it("перечень родов выводится из записей, а не записан руками", () => {
    expect(
      REGISTRY_PAGE.includes("new Set(all.map((it) => it.kind)"),
      "роды должны браться из загруженного реестра"
    ).toBe(true);
  });

  it("у каждого рода, встречающегося в данных, есть подпись в обоих языках", () => {
    const kinds = [...new Set(
      registry.technologies.map((t: { kind: string }) => t.kind).filter(Boolean)
    )] as string[];
    expect(kinds.length).toBeGreaterThan(0);
    for (const kind of kinds) {
      expect(ru.kind, `ru: род ${kind}`).toHaveProperty(kind);
      expect(en.kind, `en: род ${kind}`).toHaveProperty(kind);
    }
  });
});
