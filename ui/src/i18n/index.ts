import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import ru from "./ru.json";
import en from "./en.json";
import techRu from "./ru/tech.json";
import techEn from "./en/tech.json";
import schemaRu from "./ru/schema.json";
import schemaEn from "./en/schema.json";

/** The language from browser storage. Outside a browser (tests, build) the default. */
export function savedLanguage(): "ru" | "en" | null {
  try {
    return (globalThis.localStorage?.getItem("lang") as "ru" | "en" | null) ?? null;
  } catch {
    return null;
  }
}

/**
 * The default language is English, whatever the browser is set to.
 *
 * The primary literature of this field is in English, citations are made to
 * English works, and outside consumers of the data read English. Guessing from
 * the browser language opened the Russian version for a reader who merely has a
 * Russian keyboard layout while working from English sources.
 *
 * A reader's own choice, once made, outranks the default: a saved language wins.
 * The language switch stands in the header of every page.
 *
 * The value is exported because the application shell decides the initial state
 * and has to start from the same one. While the default was written in two
 * places, the shell won, the setting here affected nothing, and the browser
 * language was never taken into account although the code for it was written.
 */
export const DEFAULT_LANGUAGE: "ru" | "en" = "en";
const saved = savedLanguage();

/** The prose of a technology card. The key is a registry `prose_id`. */
export interface TechProse {
  short?: string;
  full?: string;
  problem?: string;
  barriers?: string;
  solutions?: string;
  maturityNote?: string;
}

const PROSE: Record<string, Record<string, TechProse>> = {
  ru: techRu as Record<string, TechProse>,
  en: techEn as Record<string, TechProse>,
};

/** The prose for a record; an empty object when no source has any. */
export function getTechProse(proseId: string | null, lang: string): TechProse {
  if (!proseId) return {};
  const table = PROSE[lang] ?? PROSE.ru;
  return table[proseId] ?? {};
}

/**
 * The labels of the dimension schema: the names `A1..G3` and readable names for
 * their values.
 *
 * The schema lives in `core/dimensions_schema.py` and reaches the interface as
 * codes (`A1`, `passage`, `dense_multi_late_interaction`). Codes are stable and
 * therefore right for data, but they tell the reader of a card nothing: a column
 * of Latin looks like machine residue rather than a description of a system. The
 * labels live apart from the schema because they are translated and the codes
 * are not.
 *
 * `src/test/schemaLabels.test.ts` guards their completeness: a dimension or a
 * value without a label in either language stops the build. Otherwise a new
 * value in the schema would quietly reach the page as a bare code.
 */
export interface DimensionLabel {
  /** The short name of the dimension. */
  name: string;
  /** One sentence on what this dimension decides. */
  question: string;
}

interface SchemaLabels {
  dimension: Record<string, DimensionLabel>;
  value: Record<string, Record<string, string>>;
}

const SCHEMA_LABELS: Record<string, SchemaLabels> = {
  ru: schemaRu as SchemaLabels,
  en: schemaEn as SchemaLabels,
};

function labels(lang: string): SchemaLabels {
  return SCHEMA_LABELS[lang] ?? SCHEMA_LABELS.ru;
}

/** The name and gloss of a dimension; `null` when there is no label. */
export function getDimensionLabel(code: string, lang: string): DimensionLabel | null {
  return labels(lang).dimension[code] ?? null;
}

/** The readable name of a dimension value; `null` when there is no label. */
export function getValueLabel(code: string, value: string, lang: string): string | null {
  return labels(lang).value[code]?.[value] ?? null;
}

i18n.use(initReactI18next).init({
  resources: {
    ru: { translation: ru },
    en: { translation: en },
  },
  lng: saved ?? DEFAULT_LANGUAGE,
  fallbackLng: "en",
  interpolation: { escapeValue: false },
});

export default i18n;
