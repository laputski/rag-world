import { useMemo } from "react";
import ReactECharts from "echarts-for-react";
import { Box } from "@mui/material";
import { useTheme } from "@mui/material/styles";
import { useTranslation } from "react-i18next";
import type { MaturityArtifact, MaturityPoint } from "../api/types";
import { KIND_SYMBOLS, MONO, stratumColor, type ThemeMode } from "../theme";

/**
 * The strata-and-levels grid: a second projection of the same data.
 *
 * The map shows a distribution well and answers "what is in this stratum at this
 * level" badly. The grid answers that directly and stays readable on sparse
 * data: an empty cell here is a meaningful observation rather than a hole in a
 * picture.
 *
 * The bottom row is given to records with no computed level. It stands apart
 * from the L0 row, because "not studied" and "a hypothesis" are different
 * claims.
 */

interface Props {
  artifact: MaturityArtifact;
  height?: number;
  onSelect?: (id: string) => void;
}

const UNKNOWN_ROW = "—";

/**
 * Places inside one cell, one per point, in a small block ordered by identifier.
 *
 * A cell is an area rather than a line, so the map's single row of slots does
 * not carry over. The points are laid out as a lattice: the count decides how
 * many columns, and each row is centred on its own, so a block with a ragged
 * last row still sits straight under the ones above it.
 *
 * The lattice is wider than it is tall because a cell is: a column of the grid
 * is about twice the width of a row's height, and a square block of points
 * would come out stretched. The order is by identifier, arbitrary and stable,
 * for the same reason it is on the map.
 */
export function cellPlaces(
  points: { id: string; group: string | null; level: string | null }[],
): Map<string, [number, number]> {
  const cells = new Map<string, string[]>();
  for (const point of points) {
    const key = `${point.group ?? ""}|${point.level ?? ""}`;
    cells.set(key, [...(cells.get(key) ?? []), point.id]);
  }

  const places = new Map<string, [number, number]>();
  for (const ids of cells.values()) {
    const ordered = [...ids].sort();
    const columns = Math.min(ordered.length, Math.ceil(Math.sqrt(ordered.length * CELL_ASPECT)));
    const rows = Math.ceil(ordered.length / columns);
    // The span is the distance from the first point to the last, so the step
    // divides by one less than the count. Dividing by the count leaves a margin
    // the block does not need and packs the points tighter than the cell asks.
    const stepX = CELL_SPAN_X / Math.max(1, columns - 1);
    const stepY = CELL_SPAN_Y / Math.max(1, rows - 1);
    for (let row = 0; row < rows; row += 1) {
      const inRow = ordered.slice(row * columns, (row + 1) * columns);
      inRow.forEach((id, i) => {
        places.set(id, [
          (i - (inRow.length - 1) / 2) * stepX,
          ((rows - 1) / 2 - row) * stepY,
        ]);
      });
    }
  }
  return places;
}

/** How much wider a cell is than it is tall, so the lattice matches its shape. */
const CELL_ASPECT = 2;

/** How much of a cell the points may occupy, leaving the rest as its margin. */
const CELL_SPAN_X = 0.74;
const CELL_SPAN_Y = 0.66;


export function MaturityGrid({ artifact, height = 460, onSelect }: Props) {
  const theme = useTheme();
  const { t } = useTranslation();
  const mode = theme.palette.mode as ThemeMode;
  const muted = theme.palette.text.secondary;
  const line = theme.palette.divider;

  const option = useMemo(() => {
    const columns = artifact.strata.map((s) => s.code);
    // Levels from the bottom up, with the "no data" row beneath them.
    const rows = [UNKNOWN_ROW, ...artifact.levels];

    const byKind = new Map<string, MaturityPoint[]>();
    for (const point of artifact.points) {
      const list = byKind.get(point.kind) ?? [];
      list.push(point);
      byKind.set(point.kind, list);
    }

    const places = cellPlaces(artifact.points);

    const series = [...byKind.entries()].map(([kind, points]) => ({
      name: t(`kind.${kind}`, { defaultValue: kind }),
      type: "scatter" as const,
      symbol: KIND_SYMBOLS[kind] ?? "circle",
      symbolSize: 11,
      data: points.map((p) => {
        const col = p.group ? columns.indexOf(p.group) : -1;
        const row = p.level ? rows.indexOf(p.level) : 0;
        return {
          // A place of its own inside the cell. The offsets used to be random
          // and to run from zero upwards, so points overlapped and every one of
          // them sat above and to the right of its own label.
          value: [
            (col < 0 ? 0 : col) + (places.get(p.id)?.[0] ?? 0),
            row + (places.get(p.id)?.[1] ?? 0),
          ],
          point: p,
          itemStyle: {
            color: stratumColor(p.group ?? "", mode),
            // Opacity tells a computed level from an absent one. It used to
            // carry confidence, which is 1.0 for every record with a level.
            opacity: p.level ? 0.95 : 0.3,
          },
        };
      }),
      emphasis: { scale: 1.3 },
    }));

    return {
      animation: false,
      grid: { left: 46, right: 20, top: 16, bottom: 46 },
      tooltip: {
        trigger: "item",
        backgroundColor: theme.palette.background.paper,
        borderColor: line,
        textStyle: { color: theme.palette.text.primary, fontSize: 12 },
        formatter: (params: { data?: { point?: MaturityPoint } }) => {
          const p = params.data?.point;
          if (!p) return "";
          return `<b>${p.name}</b><br/>${
            p.level ? t(`level.${p.level}`) : t("level.unknown")
          }`;
        },
      },
      xAxis: {
        type: "value",
        // A stratum is a column and the label names the column, so the bounds
        // fall on the cell edges and the dashed lines are drawn as marks below.
        // Drawn by the axis they would land on the ticks, and the ticks are
        // where the labels are: a line through a label reads as a boundary and
        // splits the cell in two.
        min: -0.5,
        max: columns.length - 0.5,
        interval: 0.5,
        // `onZero` is on by default, and it draws the axis at the zero of the
        // other scale instead of at the edge of the plot. Zero is the centre of
        // a column here, so the axis would stand inside a band and read as a
        // boundary that cuts it in half.
        axisLine: { onZero: false, lineStyle: { color: line } },
        axisTick: { show: false },
        splitLine: { show: false },
        axisLabel: {
          color: muted,
          fontFamily: MONO,
          fontSize: 11,
          formatter: (v: number) =>
            Math.abs(v - Math.round(v)) > 0.01 ? "" : columns[Math.round(v)] ?? "",
        },
      },
      yAxis: {
        type: "value",
        min: -0.5,
        max: rows.length - 0.5,
        interval: 0.5,
        // `onZero` is on by default, and it draws the axis at the zero of the
        // other scale instead of at the edge of the plot. Zero is the centre of
        // a column here, so the axis would stand inside a band and read as a
        // boundary that cuts it in half.
        axisLine: { onZero: false, lineStyle: { color: line } },
        axisTick: { show: false },
        splitLine: { show: false },
        axisLabel: {
          color: muted,
          fontFamily: MONO,
          fontSize: 11,
          formatter: (v: number) =>
            Math.abs(v - Math.round(v)) > 0.01 ? "" : rows[Math.round(v)] ?? "",
        },
      },
      series: [
        ...series,
        {
          // The cell boundaries, drawn as marks so that they fall between the
          // labels instead of through them. The line under the lowest row is
          // solid: it separates records with no computed level from those with
          // one, which is a different kind of boundary than a step between two
          // levels.
          name: "",
          type: "line" as const,
          data: [],
          silent: true,
          markLine: {
            silent: true,
            symbol: "none",
            label: { show: false },
            lineStyle: { color: line, type: "dashed" as const, width: 1 },
            data: [
              ...columns.slice(0, -1).map((_, i) => ({ xAxis: i + 0.5 })),
              ...rows.slice(1, -1).map((_, i) => ({ yAxis: i + 1.5 })),
              {
                yAxis: 0.5,
                lineStyle: { color: line, type: "solid" as const, width: 1 },
              },
            ],
          },
          z: 1,
        },
      ],
    };
  }, [artifact, mode, theme, t, line, muted]);

  return (
    <Box sx={{ width: "100%" }}>
      <ReactECharts
        option={option}
        style={{ height, width: "100%" }}
        notMerge
        onEvents={{
          click: (params: { data?: { point?: MaturityPoint } }) => {
            const id = params.data?.point?.id;
            if (id && onSelect) onSelect(id);
          },
        }}
      />
    </Box>
  );
}
