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

function stableJitter(id: string, salt: number): number {
  let hash = salt;
  for (let i = 0; i < id.length; i += 1) {
    hash = (hash * 31 + id.charCodeAt(i)) % 997;
  }
  return hash / 997 - 0.5;
}

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

    const series = [...byKind.entries()].map(([kind, points]) => ({
      name: t(`kind.${kind}`, { defaultValue: kind }),
      type: "scatter" as const,
      symbol: KIND_SYMBOLS[kind] ?? "circle",
      symbolSize: 11,
      data: points.map((p) => {
        const col = p.group ? columns.indexOf(p.group) : -1;
        const row = p.level ? rows.indexOf(p.level) : 0;
        return {
          // Centred on the cell, not pushed into a corner of it. The offsets
          // used to run from zero upwards, so every point sat above and to the
          // right of its own label and the cell it belonged to had to be
          // guessed.
          value: [
            (col < 0 ? 0 : col) + (stableJitter(p.id, 7) - 0.5) * 0.55,
            row + (stableJitter(p.id, 13) - 0.5) * 0.5,
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
        axisLine: { lineStyle: { color: line } },
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
        axisLine: { lineStyle: { color: line } },
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
