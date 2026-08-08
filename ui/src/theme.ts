import { createTheme, type Theme, type ThemeOptions } from "@mui/material/styles";

/**
 * Оформление портала.
 *
 * Подача научно-издательская, а не административная: содержание идёт сплошной
 * лентой с волосяными разделителями, а не набором карточек-коробок. Плотность
 * высокая, но воздух между строками сохраняется — читать приходится помногу.
 *
 * Три гарнитуры разведены по ролям. Засечная — заголовки и тексты статей, там
 * где читают подряд. Гротеск — интерфейс, где читают выборочно. Моноширинная —
 * коды измерений (A4, C2), уровни (L3) и числа: они сравниваются глазом по
 * колонке, и переменная ширина знаков этому мешает.
 *
 * Тем две: светлая и тёмная. Прежние четыре свелись к одной паре, потому что
 * четыре набора цветов невозможно держать согласованными, а выигрыша они не
 * давали.
 */

export type ThemeMode = "light" | "dark";

// ─── Палитра стратов ─────────────────────────────────────────────────────────
// Семь оттенков, различимых при наиболее распространённых видах дальтонизма
// (набор Окабэ и Ито). Это единственные насыщенные цвета портала: всё
// остальное нейтрально, поэтому цвет всегда означает страту и ничего больше.
//
// Уровень зрелости цветом НЕ кодируется. Он порядковый, а оттенок порядка не
// передаёт: читатель не скажет, какой из двух цветов «больше». Уровень
// показывается положением и размером.

export const STRATUM_COLORS: Record<ThemeMode, Record<string, string>> = {
  light: {
    A: "#0072B2",  // синий
    B: "#009E73",  // зелёный
    C: "#D55E00",  // киноварь
    D: "#CC79A7",  // пурпурный
    E: "#E69F00",  // оранжевый
    F: "#56B4E9",  // небесный
    G: "#8B6F00",  // тёмное золото: жёлтый на светлом фоне неразличим
  },
  dark: {
    A: "#4EA3DC",
    B: "#3DBF97",
    C: "#F07B2E",
    D: "#E29BC1",
    E: "#F0B33C",
    F: "#7FC8F0",
    G: "#E3D34B",
  },
};

export function stratumColor(stratum: string, mode: ThemeMode): string {
  return STRATUM_COLORS[mode][stratum] ?? (mode === "dark" ? "#8A8F98" : "#6B7280");
}

// ─── Роды объектов ───────────────────────────────────────────────────────────
// Род различается формой точки на карте, а не цветом: цвет уже занят стратой.
export const KIND_SYMBOLS: Record<string, string> = {
  paradigm: "circle",
  architecture: "diamond",
  technique: "triangle",
  tool: "rect",
  artifact: "pin",
};

// ─── Гарнитуры ───────────────────────────────────────────────────────────────

const SANS = '"Inter Variable", "Inter", system-ui, -apple-system, "Segoe UI", sans-serif';
const SERIF = '"Source Serif 4 Variable", "Source Serif 4", Georgia, "Times New Roman", serif';
export const MONO = '"JetBrains Mono Variable", "JetBrains Mono", ui-monospace, "SF Mono", monospace';

const NEUTRAL = {
  light: {
    bg: "#FCFCFD",
    paper: "#FFFFFF",
    text: "#16181D",
    muted: "#5B616E",
    line: "#E4E6EB",
    accent: "#1A56B0",
  },
  dark: {
    bg: "#0E1013",
    paper: "#15181D",
    text: "#E8EAED",
    muted: "#9BA1AC",
    line: "#262A31",
    accent: "#6FA8DC",
  },
} as const;

function baseOptions(mode: ThemeMode): ThemeOptions {
  const c = NEUTRAL[mode];
  return {
    shape: { borderRadius: 6 },
    typography: {
      fontFamily: SANS,
      // Заголовки засечные: они открывают материал, который читают подряд.
      h1: { fontFamily: SERIF, fontWeight: 600, letterSpacing: "-0.02em", fontSize: "2.6rem" },
      h2: { fontFamily: SERIF, fontWeight: 600, letterSpacing: "-0.015em", fontSize: "2rem" },
      h3: { fontFamily: SERIF, fontWeight: 600, fontSize: "1.6rem" },
      h4: { fontFamily: SERIF, fontWeight: 600, fontSize: "1.35rem" },
      h5: { fontFamily: SERIF, fontWeight: 600, fontSize: "1.15rem" },
      h6: { fontFamily: SANS, fontWeight: 600, fontSize: "0.95rem" },
      subtitle2: { fontWeight: 600, fontSize: "0.82rem", letterSpacing: "0.01em" },
      body1: { fontSize: "0.95rem", lineHeight: 1.65 },
      body2: { fontSize: "0.875rem", lineHeight: 1.6 },
      caption: { fontSize: "0.78rem", color: c.muted },
      button: { textTransform: "none", fontWeight: 500 },
    },
    palette: {
      mode,
      primary: { main: c.accent },
      background: { default: c.bg, paper: c.paper },
      text: { primary: c.text, secondary: c.muted },
      divider: c.line,
    },
    components: {
      // Разделители волосяные: содержание отделяется линией, а не тенью.
      MuiPaper: {
        defaultProps: { elevation: 0 },
        styleOverrides: {
          root: { backgroundImage: "none" },
          outlined: { borderColor: c.line },
        },
      },
      MuiCard: { styleOverrides: { root: { boxShadow: "none", border: `1px solid ${c.line}` } } },
      MuiDivider: { styleOverrides: { root: { borderColor: c.line } } },
      MuiTableCell: {
        styleOverrides: {
          root: { borderBottomColor: c.line, paddingTop: 10, paddingBottom: 10 },
          head: {
            fontWeight: 600,
            fontSize: "0.78rem",
            letterSpacing: "0.04em",
            textTransform: "uppercase",
            color: c.muted,
          },
        },
      },
      MuiChip: {
        styleOverrides: {
          root: { fontWeight: 500 },
          sizeSmall: { height: 22, fontSize: "0.75rem" },
        },
      },
      MuiLink: { defaultProps: { underline: "hover" } },
      MuiTooltip: {
        styleOverrides: {
          tooltip: { fontSize: "0.78rem", lineHeight: 1.5, maxWidth: 340 },
        },
      },
      MuiCssBaseline: {
        styleOverrides: {
          // Числа выравниваются по колонке: иначе таблицы нечитаемы.
          "code, kbd, samp, pre": { fontFamily: MONO },
          ".tabular": { fontVariantNumeric: "tabular-nums" },
        },
      },
    },
  };
}

const themes: Record<ThemeMode, Theme> = {
  light: createTheme(baseOptions("light")),
  dark: createTheme(baseOptions("dark")),
};

export function getTheme(mode: ThemeMode): Theme {
  return themes[mode];
}

/** Засечная гарнитура для длинных текстов статьи. */
export const SERIF_FAMILY = SERIF;
