import { createTheme, type Theme, type ThemeOptions } from "@mui/material/styles";

/**
 * The look of the portal.
 *
 * The manner is that of scholarly publishing rather than of an admin panel:
 * content goes as a ribbon with hairline rules, not as a set of boxed cards.
 * Density is high, but the air between lines stays — this is read, not scanned.
 *
 * Three typefaces are kept to separate roles. The serif takes headings and the
 * texts of articles, where reading runs straight through. The sans takes the
 * interface, which is read selectively. The monospace takes dimension codes
 * (A4, C2), levels (L3) and numbers: those are compared by eye down a column,
 * and variable letter widths get in the way.
 *
 * There are two themes, light and dark. The former four came down to one pair,
 * because four sets of colours cannot be kept consistent and gave nothing in
 * return.
 */

export type ThemeMode = "light" | "dark";

// ─── The stratum palette ─────────────────────────────────────────────────────
// Seven hues distinguishable under the most common forms of colour blindness
// (the Okabe and Ito set). These are the only saturated colours on the portal:
// everything else is neutral, so colour always means a stratum and nothing else.
//
// A maturity level is NOT encoded by colour. It is ordinal, and a hue carries
// no order: a reader cannot say which of two colours is the greater. A level is
// shown by position and size.

export const STRATUM_COLORS: Record<ThemeMode, Record<string, string>> = {
  light: {
    A: "#0072B2",  // blue
    B: "#009E73",  // green
    C: "#D55E00",  // vermilion
    D: "#CC79A7",  // purple
    E: "#E69F00",  // orange
    F: "#56B4E9",  // sky blue
    G: "#8B6F00",  // dark gold: yellow is indistinguishable on a light ground
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

// ─── The kinds of object ─────────────────────────────────────────────────────
// A kind is told by the shape of a point on the map rather than by colour:
// colour is already taken by the stratum.
export const KIND_SYMBOLS: Record<string, string> = {
  paradigm: "circle",
  architecture: "diamond",
  technique: "triangle",
  tool: "rect",
  artifact: "pin",
};

// ─── Typefaces ───────────────────────────────────────────────────────────────

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
      // Headings are serif: they open material that is read straight through.
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
      // Rules are hairline: content is separated by a line, not by a shadow.
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
          // Numbers align down the column, or the tables are unreadable.
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

/** The serif face for the long texts of the article. */
export const SERIF_FAMILY = SERIF;
