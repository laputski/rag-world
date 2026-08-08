import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import ru from "./ru.json";
import en from "./en.json";
import techRu from "./ru/tech.json";

/** Язык из хранилища браузера. Вне браузера (тесты, сборка) — язык по умолчанию. */
function savedLanguage(): "ru" | "en" | null {
  try {
    return (globalThis.localStorage?.getItem("lang") as "ru" | "en" | null) ?? null;
  } catch {
    return null;
  }
}

// Пока английская локализация неполна, языком по умолчанию остаётся русский:
// предлагать читателю наполовину переведённый портал хуже, чем один язык.
const DEFAULT_LANGUAGE: "ru" | "en" = "ru";
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
  // Английская проза добавляется отдельной работой; до тех пор карточка
  // показывает русский текст, а не пустое место.
  en: techRu as Record<string, TechProse>,
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
