import { Box } from "@mui/material";
import { useTheme } from "@mui/material/styles";
import { stratumColor, type ThemeMode } from "../theme";

/**
 * Знак портала: отпечаток конфигурации.
 *
 * Столбец отвечает страте, клетка — решению внутри неё. Это тот же способ
 * записи, что у глифа записи реестра, и знак сознательно на него похож: портал
 * о том и говорит, что систему можно записать точкой в пространстве решений.
 *
 * Рисунок знака **задан, а не выведен из данных**. Глиф записи меняется вместе
 * с разбором, знак меняться не должен: узнавание держится на повторении, и
 * знак, обновляющийся вместе с еженедельным прогоном, узнавать нечему.
 *
 * Три решения отличают знак от глифа записи, иначе шапка портала читалась бы
 * как ещё одна строка реестра:
 *
 *  * клетки прямоугольные, тогда как у глифа скруглены;
 *  * пустые клетки не рисуются вовсе, тогда как глиф показывает их бледной
 *    заливкой, отчего он выглядит крапом, а знак — рисунком;
 *  * насыщенность постоянна, тогда как у глифа она передаёт номер значения.
 *
 * Ниже двадцати четырёх пикселей рисунок упрощается. Двадцать восемь клеток в
 * шестнадцати пикселях дают клетку тоньше пикселя, то есть кашу, и притвориться
 * здесь нечем: показывается проекция того же отпечатка на четыре страты.
 * Упрощение объявлено, а не подогнано, потому что подогнанное расходится с
 * полным знаком при первой же правке.
 */

/** Страты в порядке обработки запроса; столбцы знака идут так же. */
const STRATA = ["A", "B", "C", "D", "E", "F", "G"] as const;

/**
 * Отпечаток знака: по строке на решение внутри страты.
 *
 * Значения выбраны как рисунок, а не срисованы с записи реестра. Взять
 * конфигурацию существующей технологии значило бы поставить одну запись выше
 * прочих знаком портала.
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

/** Страты и строки, остающиеся в упрощённом рисунке. */
const COMPACT_STRATA = ["A", "C", "E", "G"] as const;
const COMPACT_ROWS = 3;

/** Ниже этого размера рисуется упрощённый отпечаток. */
export const COMPACT_BELOW = 24;

interface Props {
  /** Высота знака в пикселях; ширина считается по числу столбцов. */
  size?: number;
  /** Тема, если знак рисуется вне дерева темы (значок вкладки, предпросмотр). */
  mode?: ThemeMode;
  title?: string;
}

interface Cell {
  x: number;
  y: number;
  side: number;
  color: string;
}

/** Клетки знака для заданного размера: полный отпечаток либо его проекция. */
export function logoCells(size: number, mode: ThemeMode): Cell[] {
  const compact = size < COMPACT_BELOW;
  const strata: readonly string[] = compact ? COMPACT_STRATA : STRATA;
  const rows = compact ? COMPACT_ROWS : 4;

  // Клетка и просвет считаются от размера, поэтому знак остаётся собой на
  // любом множителе плотности экрана и не полагается на растр.
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

/** Ширина знака при заданной высоте. */
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
