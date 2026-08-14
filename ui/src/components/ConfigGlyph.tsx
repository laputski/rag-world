import { useMemo } from "react";
import { Box, Tooltip } from "@mui/material";
import { useTheme } from "@mui/material/styles";
import { useTranslation } from "react-i18next";
import { DIMENSIONS, STRATA } from "../schema.generated";
import { stratumColor, type ThemeMode } from "../theme";

/**
 * The configuration glyph: a technology's signature in the dimension schema.
 *
 * Twenty-six cells laid out in seven stratum columns. A cell is filled with the
 * colour of its stratum when the technology sets a value of its own for that
 * dimension, and stays empty when the value matches the default or is not set at
 * all.
 *
 * The saturation of the fill carries which value was chosen: otherwise a graph
 * and a tree topology would give identical fingerprints while standing for
 * different things.
 *
 * The point is that a glyph shows **where exactly** a technology makes its
 * decisions. Query preprocessing techniques give narrow fingerprints, whole
 * architectures give wide ones, and related architectures give similar ones. In
 * a list it works as a recognisable mark: the rows stop being a uniform sheet of
 * text, and related technologies are visible without reading a name.
 *
 * The glyph is derived entirely from the data: it needs no hand work, and admits
 * none.
 */

interface Props {
  configuration: Record<string, string>;
  /** The height of the glyph in pixels; the width follows in proportion. */
  size?: number;
  title?: string;
}

const COLUMNS = STRATA.map((s) => s.code);
const MAX_ROWS = Math.max(
  ...COLUMNS.map((code) => DIMENSIONS.filter((d) => d.stratum === code).length)
);

export function ConfigGlyph({ configuration, size = 26, title }: Props) {
  const theme = useTheme();
  const { t } = useTranslation();
  const mode = theme.palette.mode as ThemeMode;

  const cell = size / MAX_ROWS;
  const gap = Math.max(1, cell * 0.18);
  const box = cell - gap;
  const width = COLUMNS.length * cell;

  const { cells, filledCount } = useMemo(() => {
    const out: {
      x: number; y: number; color: string; filled: boolean; opacity: number;
    }[] = [];
    let filled = 0;
    COLUMNS.forEach((stratum, col) => {
      DIMENSIONS.filter((d) => d.stratum === stratum).forEach((dim, row) => {
        const value = configuration[dim.code];
        const isSet = Boolean(value) && value !== dim.default;
        if (isSet) filled += 1;
        // The ordinal of the value sets the saturation, so the glyph tells
        // apart not only which decisions were made but what they were.
        const index = isSet ? Math.max(0, dim.values.indexOf(value)) : 0;
        const span = Math.max(1, dim.values.length - 1);
        out.push({
          x: col * cell,
          y: row * cell,
          color: stratumColor(stratum, mode),
          filled: isSet,
          opacity: isSet ? 0.45 + (index / span) * 0.55 : 1,
        });
      });
    });
    return { cells: out, filledCount: filled };
  }, [configuration, cell, mode]);

  const hint =
    title ??
    `${t("glyph.title")}: ${filledCount} ${t("glyph.of")} ${DIMENSIONS.length}`;

  return (
    <Tooltip title={hint} enterDelay={400}>
      <Box
        component="svg"
        width={width}
        height={size}
        viewBox={`0 0 ${width} ${size}`}
        aria-label={hint}
        role="img"
        sx={{ display: "block", flexShrink: 0 }}
      >
        {cells.map((c, i) => (
          <rect
            key={i}
            x={c.x}
            y={c.y}
            width={box}
            height={box}
            rx={Math.min(1.5, box / 3)}
            fill={c.filled ? c.color : "transparent"}
            fillOpacity={c.filled ? c.opacity : 1}
            stroke={c.filled ? "none" : theme.palette.divider}
            strokeWidth={0.7}
          />
        ))}
      </Box>
    </Tooltip>
  );
}
