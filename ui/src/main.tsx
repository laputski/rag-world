import { lazy, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { ThemeProvider, CssBaseline } from "@mui/material";
import { createBrowserRouter, RouterProvider, useNavigate } from "react-router-dom";

// The fonts arrive as packages and enter the build: the portal reaches no
// external source and looks the same without a network.
import "@fontsource-variable/inter";
import "@fontsource-variable/source-serif-4";
import "@fontsource-variable/jetbrains-mono";

// The import configures the localisation as a side effect, and the default
// language comes from the same place so that it stays written down once.
import { DEFAULT_LANGUAGE, savedLanguage } from "./i18n/index";
import { getTheme, type ThemeMode } from "./theme";
import { AppLayout } from "./layouts/AppLayout";
import { CommandPalette } from "./components/CommandPalette";
import { useTranslation } from "react-i18next";

/*
  The pages load on demand rather than in one lump.

  The whole portal used to sit in one file of two and seven tenths of a
  megabyte, and whoever opened a technology card received a diagram renderer and
  a map builder meant for entirely different pages. Compression does not help
  here, because what costs time is parsing and execution rather than transfer.

  The frame stays in the first chunk: the header, the theme and the language are
  needed immediately, or instead of a portal the reader sees an empty screen.
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
 * The language the portal opens in.
 *
 * The default lives in one place, in the localisation setup, and is taken from
 * there rather than restated here. While it was written down twice, this
 * function quietly overrode the setting: the language always came out Russian,
 * whatever i18n declared.
 */
function initialLang(): "ru" | "en" {
  return savedLanguage() ?? DEFAULT_LANGUAGE;
}

/** The application shell: theme, language and the search shared by all pages. */
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
        The registry is read by the search itself, and read when it is first
        opened rather than on page load. Eight hundred kilobytes used to be
        pulled on every page for a search the reader might never use once.
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
    // An error inside any page must not show the reader the router's own
    // screen: it addresses a developer and reads as a broken portal.
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
      // The rewrite rule serves index.html for any address, so every typo
      // reaches here and has to receive an intelligible answer.
      { path: "*", element: <NotFoundPage /> },
    ],
  },
]);

createRoot(document.getElementById("root")!).render(<RouterProvider router={router} />);
