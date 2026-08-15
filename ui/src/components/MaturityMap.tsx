import { useMemo } from "react";
import ReactECharts from "echarts-for-react";
import { Box } from "@mui/material";
import { useTheme } from "@mui/material/styles";
import { useTranslation } from "react-i18next";
import type { MaturityArtifact, MaturityPoint } from "../api/types";
import { KIND_SYMBOLS, MONO, stratumColor, type ThemeMode } from "../theme";

/**
 * The maturity map: maturity across, attention up.
 *
 * The two-dimensional layout was chosen over a circular one deliberately. A
 * circle borrows the intuition of industry radars and reads as advice on what to
 * adopt, whereas the portal reports confirmed maturity and not a recommendation.
 * A circle also carries one quantity, while the second — attention — matters to
 * a reader no less: it answers whether a thing is being discussed now, which has
 * nothing to do with whether it works and therefore has to be an axis of its
 * own.
 *
 * The position within a level carries nothing, and it is spread evenly on
 * purpose. It used to be set by confidence, and confidence is 1.0 for every
 * record with a level: the same evidence that grants a level is the evidence
 * measured for confidence, and evidence that fails the checks is never stored.
 * So the channel encoded a constant, and sixty-seven points piled into the same
 * third of their bands. Even spacing says plainly that the horizontal position
 * inside a band means nothing, and it lets a reader count what is there.
 *
 * Two separate bands are given to absent data: on the left, records with no
 * computed level; at the bottom, records with no attention data. Putting them at
 * zero is inadmissible: a zero would mean a measured quantity.
 */

interface Props {
  artifact: MaturityArtifact;
  height?: number;
  /** Show level movement: a line from the former position to the current one. */
  showMovement?: boolean;
  onSelect?: (id: string) => void;
}

const UNKNOWN_LEVEL_X = -0.75;

/**
 * Even positions inside a band, one slot per point, ordered by identifier.
 *
 * The order is deliberately arbitrary. Ordering by attention would put the
 * points on a diagonal inside every band, and a reader would see a relation
 * where there is none. An identifier carries no meaning and does not change
 * between builds, which is exactly what is wanted from a tiebreaker.
 *
 * The slots run `(rank + 1) / (total + 1)`, so a band holding one point places
 * it at the centre and a band holding many leaves a margin at both edges. The
 * span is narrower than the band, or a point at the edge would read as
 * belonging to the neighbouring level.
 */
export function bandOffsets(points: { id: string; level: string | null }[]): Map<string, number> {
  const bands = new Map<string, string[]>();
  for (const point of points) {
    const key = point.level ?? "";
    const list = bands.get(key) ?? [];
    list.push(point.id);
    bands.set(key, list);
  }
  const offsets = new Map<string, number>();
  for (const ids of bands.values()) {
    const ordered = [...ids].sort();
    ordered.forEach((id, rank) => {
      offsets.set(id, ((rank + 1) / (ordered.length + 1) - 0.5) * BAND_SPAN);
    });
  }
  return offsets;
}

/** How much of a band the points may occupy; the rest is the gap between bands. */
const BAND_SPAN = 0.76;

/** A stable fractional offset from the identifier, so a point does not jump between builds. */
function stableJitter(id: string): number {
  let hash = 0;
  for (let i = 0; i < id.length; i += 1) {
    hash = (hash * 31 + id.charCodeAt(i)) % 1000;
  }
  return hash / 1000;
}

function levelIndex(levels: string[], level: string | null): number {
  return level ? levels.indexOf(level) : -1;
}

export function MaturityMap({ artifact, height = 460, showMovement, onSelect }: Props) {
  const theme = useTheme();
  const { t } = useTranslation();
  const mode = theme.palette.mode as ThemeMode;
  const text = theme.palette.text.primary;
  const muted = theme.palette.text.secondary;
  const line = theme.palette.divider;

  const option = useMemo(() => {
    const levels = artifact.levels;
    const attentions = artifact.points
      .map((p) => p.attention)
      .filter((a): a is number => a != null);
    const maxAttention = attentions.length ? Math.max(...attentions) : 1;
    // The "no data" band lies below zero, apart from the measured values.
    const unknownAttentionY = -maxAttention * 0.12;

    // A band is centred on its own label, and the points inside it are spread
    // evenly across it. No two share a position, so a reader can count them.
    const offsets = bandOffsets(artifact.points);
    const xOf = (p: MaturityPoint): number => {
      const index = levelIndex(levels, p.level);
      const centre = index < 0 ? UNKNOWN_LEVEL_X : index;
      return centre + (offsets.get(p.id) ?? 0);
    };
    const yOf = (p: MaturityPoint): number =>
      p.attention != null
        ? p.attention
        : unknownAttentionY + (stableJitter(p.id) - 0.5) * maxAttention * 0.06;

    // The size of a point encodes nothing and is the same for all.
    //
    // It used to be set by spread, and there was no quantity behind it: nobody
    // wrote a series of such measurements, so the size was the same for everyone
    // anyway and merely looked meaningful. Worse, "no data" produced size 11
    // while fifteen hundred downloads a month produced 9 + √1748, which hit the
    // same ceiling: not knowing and knowing a small value could not be told
    // apart by eye. The portal is obliged to show that difference, not hide it.
    const POINT_SIZE = 11;

    const byKind = new Map<string, MaturityPoint[]>();
    for (const point of artifact.points) {
      const list = byKind.get(point.kind) ?? [];
      list.push(point);
      byKind.set(point.kind, list);
    }

    const scatterSeries = [...byKind.entries()].map(([kind, points]) => ({
      name: t(`kind.${kind}`, { defaultValue: kind }),
      type: "scatter" as const,
      symbol: KIND_SYMBOLS[kind] ?? "circle",
      symbolSize: POINT_SIZE,
      data: points.map((p) => ({
        value: [xOf(p), yOf(p)],
        point: p,
        itemStyle: {
          color: stratumColor(p.group ?? "", mode),
          // Opacity tells a computed level from an absent one, and nothing
          // else. It used to carry confidence, which is 1.0 for every record
          // that has a level at all.
          opacity: p.level ? 0.95 : 0.28,
          borderColor: theme.palette.background.default,
          borderWidth: 1,
        },
      })),
      emphasis: { focus: "series" as const, scale: 1.25 },
      z: 3,
    }));

    // Movement: a segment from the former level to the current one.
    const movement = showMovement
      ? artifact.points
          .filter((p) => p.history.length > 1 && p.level)
          .map((p) => {
            const previous = p.history[p.history.length - 2];
            const from = levelIndex(levels, previous.level);
            if (from < 0) return null;
            const y = yOf(p);
            return {
              coords: [[from, y], [xOf(p), y]],
              lineStyle: { color: stratumColor(p.group ?? "", mode), opacity: 0.5 },
            };
          })
          .filter(Boolean)
      : [];

    return {
      animation: false,
      grid: { left: 56, right: 24, top: 16, bottom: 52 },
      tooltip: {
        trigger: "item",
        backgroundColor: theme.palette.background.paper,
        borderColor: line,
        textStyle: { color: text, fontSize: 12 },
        formatter: (params: { data?: { point?: MaturityPoint } }) => {
          const p = params.data?.point;
          if (!p) return "";
          const level = p.level ? t(`level.${p.level}`) : t("level.unknown");
          // The unit depends on whether the quantity was normalised: a small
          // age subgroup has no median, and the measured value is shown
          // instead. Without the distinction a reader would compare fractions
          // of a median with citations a month.
          const attention = p.attention != null
            ? `${p.attention.toFixed(1)} ${
                p.attention_cohort
                  ? t("map.attentionUnit")
                  : t("map.attentionRaw")
              }`
            : t("map.noAttention");
          return [
            `<b>${p.name}</b>`,
            t(`kind.${p.kind}`, { defaultValue: p.kind }),
            level,
            attention,
          ].join("<br/>");
        },
      },
      xAxis: {
        type: "value",
        // A level is a column, and the label names the column rather than a
        // line inside it. The bounds therefore fall on the band edges, half a
        // step outside the outermost centres, so every column is full width and
        // none is clipped.
        //
        // The dashed lines are drawn as marks below, not by the axis: the axis
        // puts them on its ticks, and its ticks are where the labels are. A
        // reader who sees a line through a label reads it as a boundary and
        // splits the column in two.
        min: -1.5,
        max: levels.length - 0.5,
        interval: 0.5,
        axisLine: { lineStyle: { color: line } },
        axisTick: { show: false },
        splitLine: { show: false },
        axisLabel: {
          color: muted,
          fontFamily: MONO,
          fontSize: 11,
          formatter: (value: number) => {
            if (Math.abs(value - Math.round(value)) > 0.01) return "";
            const index = Math.round(value);
            if (index === -1) return t("level.unknown");
            return levels[index] ?? "";
          },
        },
        name: t("map.axisMaturity"),
        nameLocation: "middle" as const,
        nameGap: 32,
        nameTextStyle: { color: muted, fontSize: 12 },
      },
      yAxis: {
        type: "value",
        min: unknownAttentionY - maxAttention * 0.06,
        // `onZero` is on by default, and it draws the axis at the zero of the
        // other scale instead of at the edge of the plot. Zero is the centre of
        // a column here, so the axis would stand inside a band and read as a
        // boundary that cuts it in half.
        axisLine: { onZero: false, lineStyle: { color: line } },
        splitLine: { lineStyle: { color: line, type: "dashed" as const } },
        axisLabel: {
          color: muted,
          fontFamily: MONO,
          fontSize: 11,
          formatter: (value: number) =>
            value < 0 ? "" : String(Math.round(value)),
        },
        name: t("map.axisAttention"),
        nameLocation: "middle" as const,
        nameGap: 38,
        nameRotate: 90,
        nameTextStyle: { color: muted, fontSize: 12 },
      },
      series: [
        ...scatterSeries,
        {
          type: "lines" as const,
          coordinateSystem: "cartesian2d" as const,
          data: movement,
          lineStyle: { width: 1.5, curveness: 0 },
          effect: { show: false },
          symbol: ["none", "arrow"] as [string, string],
          symbolSize: 6,
          z: 2,
        },
        {
          // The separators of the "no data" bands: without them an absent
          // quantity would look like a merely small one.
          type: "line" as const,
          data: [],
          markLine: {
            silent: true,
            symbol: "none",
            label: {
              color: muted,
              fontSize: 10,
              position: "insideStartTop" as const,
              formatter: (params: { name?: string }) => params.name ?? "",
            },
            lineStyle: { color: line, type: "solid" as const, width: 1 },
            data: [
              // The zero line separates measured attention from its absence.
              { yAxis: 0, name: t("map.noAttention") },
              // The boundary between "no level" and L0 is solid: it separates
              // two kinds of thing, not two levels of one kind.
              { xAxis: -0.5, name: "" },
              // The boundaries between levels, dashed, at the edges of the
              // columns rather than through their labels.
              ...levels.slice(0, -1).map((_, i) => ({
                xAxis: i + 0.5,
                name: "",
                lineStyle: { color: line, type: "dashed" as const, width: 1 },
              })),
            ],
          },
          z: 1,
        },
      ],
    };
  }, [artifact, showMovement, mode, theme, t, line, muted, text]);

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
