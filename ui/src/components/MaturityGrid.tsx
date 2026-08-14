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
          value: [
            (col < 0 ? 0 : col) + stableJitter(p.id, 7) * 0.55,
            row + stableJitter(p.id, 13) * 0.5,
          ],
          point: p,
          itemStyle: {
            color: stratumColor(p.group ?? "", mode),
            opacity: p.level ? 0.45 + (p.confidence ?? 0) * 0.5 : 0.3,
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
        // The bounds are whole numbers: otherwise the ticks miss the integers
        // and the stratum labels are not drawn at all.
        min: -1,
        max: columns.length,
        interval: 1,
        axisLine: { lineStyle: { color: line } },
        splitLine: { lineStyle: { color: line, type: "dashed" as const } },
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
        min: -1,
        max: rows.length,
        interval: 1,
        axisLine: { lineStyle: { color: line } },
        splitLine: { lineStyle: { color: line, type: "dashed" as const } },
        axisLabel: {
          color: muted,
          fontFamily: MONO,
          fontSize: 11,
          formatter: (v: number) =>
            Math.abs(v - Math.round(v)) > 0.01 ? "" : rows[Math.round(v)] ?? "",
        },
      },
      series,
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
