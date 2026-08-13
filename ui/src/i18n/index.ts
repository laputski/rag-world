import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import ru from "./ru.json";
import en from "./en.json";
import techRu from "./ru/tech.json";
import techEn from "./en/tech.json";
import schemaRu from "./ru/schema.json";
import schemaEn from "./en/schema.json";

/** Язык из хранилища браузера. Вне браузера (тесты, сборка) — язык по умолчанию. */
export function savedLanguage(): "ru" | "en" | null {
  try {
    return (globalThis.localStorage?.getItem("lang") as "ru" | "en" | null) ?? null;
  } catch {
    return null;
  }
}

/**
 * Язык по умолчанию — английский, независимо от настроек браузера.
 *
 * Первичная литература по этой области английская, ссылаются на портал в
 * английских работах, и внешние потребители данных читают английские поля.
 * Догадка по языку браузера открывала русскую версию читателю с русской
 * раскладкой, хотя работает он с английскими источниками.
 *
 * Выбор читателя, однажды сделанный, важнее умолчания: сохранённый язык
 * перекрывает его. Переключатель языка стоит в шапке всех страниц.
 *
 * Значение вывозится наружу, потому что оболочка приложения держит язык
 * состоянием и должна начинать с того же. Пока умолчание было записано в двух
 * местах, побеждала оболочка, а настройка здесь ни на что не влияла: язык
 * браузера не учитывался никогда, хотя код для этого был написан.
 */
export const DEFAULT_LANGUAGE: "ru" | "en" = "en";
const saved = savedLanguage();

/** Проза карточки технологии. Ключ — идентификатор записи реестра (prose_id). */
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

/** Проза для записи реестра; пустой объект, если её нет ни в одном источнике. */
export function getTechProse(proseId: string | null, lang: string): TechProse {
  if (!proseId) return {};
  const table = PROSE[lang] ?? PROSE.ru;
  return table[proseId] ?? {};
}

/**
 * Подписи к схеме измерений: имена `A1..G3` и читаемые названия их значений.
 *
 * Схема живёт в `core/dimensions_schema.py` и попадает в интерфейс кодами
 * (`A1`, `passage`, `dense_multi_late_interaction`). Коды устойчивы и потому
 * годятся для данных, но читателю карточки они не говорят ничего: две колонки
 * латиницы выглядят машинным следом, а не описанием системы. Подписи держатся
 * отдельно от схемы, потому что переводятся, а коды не переводятся никогда.
 *
 * Полноту подписей стережёт `src/test/schemaLabels.test.ts`: измерение или
 * значение без подписи в любом из языков останавливает сборку. Без сторожа
 * новое значение в схеме молча вышло бы на страницу голым кодом.
 */
export interface DimensionLabel {
  /** Короткое имя измерения. */
  name: string;
  /** Одно предложение о том, что это измерение решает. */
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

/** Имя и пояснение измерения; `null`, если подписи нет. */
export function getDimensionLabel(code: string, lang: string): DimensionLabel | null {
  return labels(lang).dimension[code] ?? null;
}

/** Читаемое название значения измерения; `null`, если подписи нет. */
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
