import { lazy, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { ThemeProvider, CssBaseline } from "@mui/material";
import { createBrowserRouter, RouterProvider, useNavigate } from "react-router-dom";

// Шрифты подключаются пакетами и попадают в сборку: портал не обращается к
// внешним источникам и одинаково выглядит без сети.
import "@fontsource-variable/inter";
import "@fontsource-variable/source-serif-4";
import "@fontsource-variable/jetbrains-mono";

// Ввоз настраивает локализацию побочным действием; отсюда же берётся
// умолчание языка, чтобы оно оставалось записанным в одном месте.
import { DEFAULT_LANGUAGE, savedLanguage } from "./i18n/index";
import { getTheme, type ThemeMode } from "./theme";
import { AppLayout } from "./layouts/AppLayout";
import { CommandPalette } from "./components/CommandPalette";
import { useTranslation } from "react-i18next";

/*
  Страницы грузятся по требованию, а не одним куском.

  Прежде весь портал лежал в одном файле на два и семь десятых мегабайта:
  открывший карточку технологии получал заодно разрисовщик диаграмм и
  построитель карты, нужные совсем другим страницам. Сжатие тут не помогает,
  потому что время съедают разбор и исполнение, а не передача.

  Каркас остаётся в первом куске: шапка, тема и язык нужны немедленно, иначе
  вместо портала читатель увидит пустой экран.
*/
const HomePage = lazy(() => import("./pages/HomePage").then((m) => ({ default: m.HomePage })));
const RegistryPage = lazy(() => import("./pages/RegistryPage").then((m) => ({ default: m.RegistryPage })));
const TechCardPage = lazy(() => import("./pages/TechCardPage").then((m) => ({ default: m.TechCardPage })));
const ChangesPage = lazy(() => import("./pages/ChangesPage").then((m) => ({ default: m.ChangesPage })));
const DigestPage = lazy(() => import("./pages/DigestPage").then((m) => ({ default: m.DigestPage })));
const ResidualsPage = lazy(() => import("./pages/ResidualsPage").then((m) => ({ default: m.ResidualsPage })));
const AboutPage = lazy(() => import("./pages/AboutPage").then((m) => ({ default: m.AboutPage })));
const GeneralizedArticlePage = lazy(() => import("./pages/GeneralizedArticlePage").then((m) => ({ default: m.GeneralizedArticlePage })));
const NotFoundPage = lazy(() => import("./pages/NotFoundPage").then((m) => ({ default: m.NotFoundPage })));

const MODE_KEY = "themeMode";
const LANG_KEY = "lang";

function initialMode(): ThemeMode {
  const saved = localStorage.getItem(MODE_KEY) as ThemeMode | null;
  if (saved) return saved;
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

/**
 * Язык, с которого открывается портал.
 *
 * Умолчание живёт в одном месте, в настройке локализации, и берётся
 * оттуда, а не переписывается здесь. Пока оно было записано дважды, эта
 * функция молча перекрывала настройку: язык всегда получался русским
 * независимо от того, что было объявлено в i18n.
 */
function initialLang(): "ru" | "en" {
  return savedLanguage() ?? DEFAULT_LANGUAGE;
}

/** Оболочка приложения: тема, язык и общий для всех страниц быстрый поиск. */
function Shell() {
  const [mode, setMode] = useState<ThemeMode>(initialMode);
  const [lang, setLang] = useState<"ru" | "en">(initialLang);
  const navigate = useNavigate();
  const { i18n } = useTranslation();
  const openSearch = useRef<() => void>(() => {});

  useEffect(() => { localStorage.setItem(MODE_KEY, mode); }, [mode]);
  useEffect(() => {
    localStorage.setItem(LANG_KEY, lang);
    i18n.changeLanguage(lang);
  }, [lang, i18n]);

  const toggleMode = useCallback(
    () => setMode((m) => (m === "light" ? "dark" : "light")), []
  );
  const theme = useMemo(() => getTheme(mode), [mode]);

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <AppLayout
        mode={mode}
        onToggleMode={toggleMode}
        lang={lang}
        onSetLang={setLang}
        onOpenSearch={() => openSearch.current()}
      />
      {/*
        Реестр читает сам быстрый поиск, и читает при первом открытии, а не при
        загрузке страницы. Прежде восемьсот килобайт тянулись на каждой
        странице ради поиска, которым читатель мог ни разу не воспользоваться.
      */}
      <CommandPalette
        onOpen={(id) => navigate(`/tech/${id}`)}
        registerOpener={(fn) => { openSearch.current = fn; }}
      />
    </ThemeProvider>
  );
}

const router = createBrowserRouter([
  {
    element: <Shell />,
    // Ошибка внутри любой страницы не должна показывать читателю отладочный
    // экран маршрутизатора: он обращается к разработчику и читается как
    // сломанный портал.
    errorElement: <Shell />,
    children: [
      { path: "/", element: <HomePage /> },
      { path: "/registry", element: <RegistryPage /> },
      { path: "/tech/:id", element: <TechCardPage /> },
      { path: "/changes", element: <ChangesPage /> },
      { path: "/digest", element: <DigestPage /> },
      { path: "/residuals", element: <ResidualsPage /> },
      { path: "/article", element: <GeneralizedArticlePage /> },
      { path: "/about", element: <AboutPage /> },
      // Правило переписывания отдаёт index.html на любой адрес, поэтому
      // опечатка доходит сюда и обязана получить внятный ответ.
      { path: "*", element: <NotFoundPage /> },
    ],
  },
]);

createRoot(document.getElementById("root")!).render(<RouterProvider router={router} />);
