import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import ru from "./ru.json";
import en from "./en.json";
import techRu from "./ru/tech.json";
import techEn from "./en/tech.json";

/** Язык из хранилища браузера. Вне браузера (тесты, сборка) — язык по умолчанию. */
function savedLanguage(): "ru" | "en" | null {
  try {
    return (globalThis.localStorage?.getItem("lang") as "ru" | "en" | null) ?? null;
  } catch {
    return null;
  }
}

/**
 * Язык по умолчанию — по языку браузера.
 *
 * Русский остаётся для тех, у кого он в настройках; остальным открывается
 * английский. Первичная литература по этой области английская, и читатель,
 * который её читает, читает по-английски по определению.
 *
 * Выбор читателя, однажды сделанный, важнее догадки: сохранённый язык
 * перекрывает язык браузера.
 */
function browserLanguage(): "ru" | "en" {
  try {
    const tags = globalThis.navigator?.languages ?? [];
    return tags.some((tag) => tag.toLowerCase().startsWith("ru")) ? "ru" : "en";
  } catch {
    return "ru";
  }
}

const DEFAULT_LANGUAGE: "ru" | "en" = browserLanguage();
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

i18n.use(initReactI18next).init({
  resources: {
    ru: { translation: ru },
    en: { translation: en },
  },
  lng: saved ?? DEFAULT_LANGUAGE,
  fallbackLng: "ru",
  interpolation: { escapeValue: false },
});

export default i18n;
