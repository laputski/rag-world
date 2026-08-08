import { useMemo } from "react";
import { Box, Tooltip } from "@mui/material";
import { useTheme } from "@mui/material/styles";
import { useTranslation } from "react-i18next";
import { DIMENSIONS, STRATA } from "../schema.generated";
import { stratumColor, type ThemeMode } from "../theme";

/**
 * Глиф конфигурации: подпись технологии в схеме измерений.
 *
 * Двадцать шесть клеток, разложенных по семи столбцам-стратам. Клетка залита
 * цветом своей страты, если технология задаёт по этому измерению собственное
 * значение, и остаётся пустой, если значение совпадает с умолчанием либо не
 * задано вовсе.
 *
 * Насыщенность заливки передаёт, какое именно значение выбрано: без этого
 * графовая и древесная топологии давали бы одинаковый отпечаток, хотя решения
 * за ними стоят разные.
 *
 * Смысл в том, что глиф показывает **где именно** технология принимает
 * решения. Приёмы предобработки запроса дают узкие отпечатки, полные
 * архитектуры — широкие, родственные архитектуры — похожие. В ленте это
 * работает как узнаваемая метка: строки перестают быть однородной простынёй
 * текста, а близкие технологии видно, не читая названий.
 *
 * Глиф целиком выводится из данных: ручной работы он не требует и устаревать
 * не может.
 */

interface Props {
  configuration: Record<string, string>;
  /** Высота глифа в пикселях; ширина считается пропорционально. */
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
        // Порядковый номер значения задаёт насыщенность, поэтому отпечаток
        // различает не только набор решений, но и сами решения.
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
