import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { ThemeProvider, CssBaseline } from "@mui/material";
import { createBrowserRouter, RouterProvider, useNavigate } from "react-router-dom";

// Шрифты подключаются пакетами и попадают в сборку: портал не обращается к
// внешним источникам и одинаково выглядит без сети.
import "@fontsource-variable/inter";
import "@fontsource-variable/source-serif-4";
import "@fontsource-variable/jetbrains-mono";

import "./i18n/index";
import { getTheme, type ThemeMode } from "./theme";
import { AppLayout } from "./layouts/AppLayout";
import { HomePage } from "./pages/HomePage";
import { RegistryPage } from "./pages/RegistryPage";
import { TechCardPage } from "./pages/TechCardPage";
import { ChangesPage } from "./pages/ChangesPage";
import { AboutPage } from "./pages/AboutPage";
import { GeneralizedArticlePage } from "./pages/GeneralizedArticlePage";
import { CommandPalette } from "./components/CommandPalette";
import { getRegistry } from "./api/client";
import type { FeedItem } from "./components/FeedRow";
import { useTranslation } from "react-i18next";

const MODE_KEY = "themeMode";
const LANG_KEY = "lang";

function initialMode(): ThemeMode {
  const saved = localStorage.getItem(MODE_KEY) as ThemeMode | null;
  if (saved) return saved;
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function initialLang(): "ru" | "en" {
  return (localStorage.getItem(LANG_KEY) as "ru" | "en" | null) ?? "ru";
}

/** Оболочка приложения: тема, язык и общий для всех страниц быстрый поиск. */
function Shell() {
  const [mode, setMode] = useState<ThemeMode>(initialMode);
  const [lang, setLang] = useState<"ru" | "en">(initialLang);
  const [items, setItems] = useState<(FeedItem & { aliases?: string[] })[]>([]);
  const navigate = useNavigate();
  const { i18n } = useTranslation();
  const openSearch = useRef<() => void>(() => {});

  useEffect(() => { localStorage.setItem(MODE_KEY, mode); }, [mode]);
  useEffect(() => {
    localStorage.setItem(LANG_KEY, lang);
    i18n.changeLanguage(lang);
  }, [lang, i18n]);

  // Реестр загружается один раз и обслуживает поиск на всех страницах.
  useEffect(() => {
    getRegistry()
      .then((r) => setItems(r.technologies as unknown as FeedItem[]))
      .catch(() => setItems([]));
  }, []);

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
      <CommandPalette
        items={items}
        onOpen={(id) => navigate(`/tech/${id}`)}
        registerOpener={(fn) => { openSearch.current = fn; }}
      />
    </ThemeProvider>
  );
}

const router = createBrowserRouter([
  {
    element: <Shell />,
    children: [
      { path: "/", element: <HomePage /> },
      { path: "/registry", element: <RegistryPage /> },
      { path: "/tech/:id", element: <TechCardPage /> },
      { path: "/changes", element: <ChangesPage /> },
      { path: "/article", element: <GeneralizedArticlePage /> },
      { path: "/about", element: <AboutPage /> },
    ],
  },
]);

createRoot(document.getElementById("root")!).render(<RouterProvider router={router} />);
