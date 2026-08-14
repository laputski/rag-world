import { Box } from "@mui/material";
import { useTheme } from "@mui/material/styles";
import { stratumColor, type ThemeMode } from "../theme";

/**
 * The mark of the portal: a configuration fingerprint.
 *
 * A column stands for a stratum and a cell for a decision within it. That is the
 * same way of writing a record as the glyph of a registry entry uses, and the
 * mark deliberately resembles it: the project says that a system can be written
 * down as a point in a space.
 *
 * The pattern of the mark is **given, not derived from the data**. The glyph of
 * a record changes as the reading changes; the mark must not. Recognition rests
 * on constancy, and a mark that updates with every weekly pass is not something
 * anyone learns to recognise.
 *
 * Three decisions tell the mark from a record glyph, or the header of the portal
 * would read as one more row of the registry:
 *
 *  * the cells are rectangular, whereas a glyph rounds them;
 *  * empty cells are not drawn at all, whereas a glyph shows them with a pale
 *    fill, which makes it look like a speckle while the mark looks like a
 *    drawing;
 *  * saturation is constant, whereas in a glyph it carries the number of the
 *    value.
 *
 * Below twenty-four pixels the pattern simplifies. Seven columns at sixteen
 * pixels give a cell thinner than a pixel, that is, porridge. There is nothing
 * to shrink here, so what is shown is a projection of the same fingerprint onto
 * four columns. The simplification is declared rather than fitted, because a
 * fitted drawing would diverge from the full mark at the first edit.
 */

/** The strata in the order a query is processed; the columns follow it. */
const STRATA = ["A", "B", "C", "D", "E", "F", "G"] as const;

/**
 * The fingerprint of the mark: one row per decision within a stratum.
 *
 * The values are chosen as a drawing rather than copied from a registry record.
 * Taking the configuration of an existing technology would mean marking one of
 * them with the mark of the whole portal.
 */
const PATTERN: Record<string, boolean[]> = {
  A: [true, true, false, true],
  B: [true, false, false, false],
  C: [true, true, true, false],
  D: [false, true, true, false],
  E: [true, false, true, false],
  F: [false, true, false, false],
  G: [true, false, false, false],
};

/** The strata and rows that survive in the simplified drawing. */
const COMPACT_STRATA = ["A", "C", "E", "G"] as const;
const COMPACT_ROWS = 3;

/** Below this size the simplified fingerprint is drawn. */
export const COMPACT_BELOW = 24;

interface Props {
  /** The height of the mark in pixels; the width follows from the columns. */
  size?: number;
  /** The theme, when the mark is drawn outside the theme tree (icons, previews). */
  mode?: ThemeMode;
  title?: string;
}

interface Cell {
  x: number;
  y: number;
  side: number;
  color: string;
}

/** The cells of the mark at a given size: the full fingerprint or its projection. */
export function logoCells(size: number, mode: ThemeMode): Cell[] {
  const compact = size < COMPACT_BELOW;
  const strata: readonly string[] = compact ? COMPACT_STRATA : STRATA;
  const rows = compact ? COMPACT_ROWS : 4;

  // The cell and the gap are computed from the size, so the mark stays sharp at
  // any screen density and relies on no raster.
  const step = size / rows;
  const gap = compact ? step * 0.16 : step * 0.2;
  const side = step - gap;

  const cells: Cell[] = [];
  strata.forEach((stratum, col) => {
    const pattern = PATTERN[stratum] ?? [];
    for (let row = 0; row < rows; row += 1) {
      if (!pattern[row]) continue;
      cells.push({
        x: col * step,
        y: row * step,
        side,
        color: stratumColor(stratum, mode),
      });
    }
  });
  return cells;
}

/** The width of the mark at a given height. */
export function logoWidth(size: number): number {
  const compact = size < COMPACT_BELOW;
  const rows = compact ? COMPACT_ROWS : 4;
  const columns = compact ? COMPACT_STRATA.length : STRATA.length;
  return (size / rows) * columns;
}

export function Logo({ size = 26, mode, title = "RAG World" }: Props) {
  const theme = useTheme();
  const resolved = mode ?? (theme.palette.mode as ThemeMode);
  const cells = logoCells(size, resolved);
  const width = logoWidth(size);

  return (
    <Box
      component="svg"
      width={width}
      height={size}
      viewBox={`0 0 ${width} ${size}`}
      role={title ? "img" : "presentation"}
      aria-label={title || undefined}
      aria-hidden={title ? undefined : true}
      sx={{ display: "block", flexShrink: 0 }}
    >
      {title && <title>{title}</title>}
      {cells.map((cell, i) => (
        <rect
          key={i}
          x={cell.x}
          y={cell.y}
          width={cell.side}
          height={cell.side}
          fill={cell.color}
        />
      ))}
    </Box>
  );
}
