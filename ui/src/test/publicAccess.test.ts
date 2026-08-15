// @vitest-environment jsdom
/**
 * Defaults that were set twice and therefore did not work.
 *
 * The default language was declared in the localisation setup and again in the
 * application shell. The shell won, so what was declared affected nothing: the
 * portal opened in Russian whatever stood in the setting. A defect of this kind
 * is visible neither to the types nor to the view tests, because each entry is
 * correct on its own.
 */

import { describe, expect, it } from "vitest";
import { DEFAULT_LANGUAGE, savedLanguage } from "../i18n/index";
// The sources are read through the bundler rather than the file system: the
// project has no node typings, and `?raw` gives the same thing and works in the
// build as well.
import MAIN from "../main.tsx?raw";
import REGISTRY_PAGE from "../pages/RegistryPage.tsx?raw";
import registry from "../../public/data/registry.json";
import ru from "../i18n/ru.json";
import en from "../i18n/en.json";

describe("the default language", () => {
  it("is English", () => {
    expect(DEFAULT_LANGUAGE).toBe("en");
  });

  it("is declared once: the shell takes it rather than setting its own", () => {
    expect(MAIN, "the shell has to import the default from i18n").toContain("DEFAULT_LANGUAGE");
    const ownDefault = /localStorage\.getItem\(LANG_KEY\)[^;]*\?\?\s*["'](ru|en)["']/.test(MAIN);
    expect(ownDefault, "the shell sets a default of its own and would override i18n").toBe(false);
  });

  /*
    Storage is substituted rather than taken from the environment: in the test
    environment it is empty, and without a substitution the only thing checked
    would be that reading does not crash. What is checked here is different: a
    saved choice is genuinely read, and its absence yields an empty answer rather
    than an invented language.
  */
  it("a reader\u2019s choice overrides the default", () => {
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
      expect(savedLanguage(), "empty storage must yield no language").toBeNull();
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
 * Filtering the registry by kind of object.
 *
 * The set of kinds was written by hand and diverged from the data in both
 * directions: "evaluation artefact" stood in the filter with no records at all,
 * while "attack" fell out of the filter although records exist. The check demands
 * that the set be derived from the data.
 */
describe("filtering by kind of object", () => {
  it("the set of kinds is derived from the records, not written by hand", () => {
    expect(
      REGISTRY_PAGE.includes("new Set(all.map((it) => it.kind)"),
      "the kinds have to come from the loaded registry"
    ).toBe(true);
  });

  it("every kind occurring in the data has a label in both languages", () => {
    const kinds = [...new Set(
      registry.technologies.map((t: { kind: string }) => t.kind).filter(Boolean)
    )] as string[];
    expect(kinds.length).toBeGreaterThan(0);
    for (const kind of kinds) {
      expect(ru.kind, `ru: the kind ${kind}`).toHaveProperty(kind);
      expect(en.kind, `en: the kind ${kind}`).toHaveProperty(kind);
    }
  });
});
