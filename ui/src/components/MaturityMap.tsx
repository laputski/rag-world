import { useMemo } from "react";
import ReactECharts from "echarts-for-react";
import { Box } from "@mui/material";
import { useTheme } from "@mui/material/styles";
import { useTranslation } from "react-i18next";
import type { MaturityArtifact, MaturityPoint } from "../api/types";
import { KIND_SYMBOLS, MONO, stratumColor, type ThemeMode } from "../theme";

/**
 * Карта созревания: зрелость по горизонтали, внимание по вертикали.
 *
 * Двумерная раскладка выбрана вместо круговой намеренно. Круговая форма
 * заимствует интуицию отраслевых радаров и читается как совет, что внедрять, —
 * а портал сообщает подтверждённую зрелость, а не рекомендацию. Кроме того,
 * круг несёт одну величину, тогда как вторая, внимание, для читателя не менее
 * важна: она отвечает на вопрос «обсуждают ли это сейчас», который к
 * работоспособности отношения не имеет и потому обязан быть отдельной осью.
 *
 * Положение внутри уровня задаётся уверенностью: запись с полным набором
 * свежих свидетельств стоит у правого края своей полосы, запись с неполным —
 * у левого. Так видно не только уровень, но и то, насколько он обеспечен.
 *
 * Две отдельные полосы отведены отсутствию данных: слева — записи без
 * вычисленного уровня, снизу — записи без данных о внимании. Помещать их в
 * ноль нельзя: ноль означал бы измеренную величину.
 */

interface Props {
  artifact: MaturityArtifact;
  height?: number;
  /** Показывать движение уровней: линия от прежнего положения к нынешнему. */
  showMovement?: boolean;
  onSelect?: (id: string) => void;
}

const UNKNOWN_LEVEL_X = -0.75;

/** Устойчивое дробное смещение по идентификатору: точка не прыгает между сборками. */
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
    // Полоса «нет данных» лежит ниже нуля и отделена от измеренных значений.
    const unknownAttentionY = -maxAttention * 0.12;

    const xOf = (p: MaturityPoint): number => {
      const index = levelIndex(levels, p.level);
      if (index < 0) return UNKNOWN_LEVEL_X + (stableJitter(p.id) - 0.5) * 0.3;
      // Полоса уровня центрирована на своей подписи, иначе точка у правого
      // края читается как принадлежащая следующему уровню. Внутри полосы
      // положение задаёт уверенность, а дрожание разводит совпадения и
      // остаётся устойчивым между сборками.
      const confidence = p.confidence ?? 0;
      return index + (confidence - 0.5) * 0.62 + (stableJitter(p.id) - 0.5) * 0.14;
    };
    const yOf = (p: MaturityPoint): number =>
      p.attention != null
        ? p.attention
        : unknownAttentionY + (stableJitter(p.id) - 0.5) * maxAttention * 0.06;

    const sizeOf = (p: MaturityPoint): number =>
      p.prevalence != null ? Math.min(26, 9 + Math.sqrt(p.prevalence)) : 11;

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
      symbolSize: (_: unknown, params: { dataIndex: number }) =>
        sizeOf(points[params.dataIndex]),
      data: points.map((p) => ({
        value: [xOf(p), yOf(p)],
        point: p,
        itemStyle: {
          color: stratumColor(p.group ?? "", mode),
          // Прозрачность отражает уверенность: чем меньше свежих проверенных
          // свидетельств, тем бледнее точка.
          opacity: p.level ? 0.35 + (p.confidence ?? 0) * 0.6 : 0.28,
          borderColor: theme.palette.background.default,
          borderWidth: 1,
        },
      })),
      emphasis: { focus: "series" as const, scale: 1.25 },
      z: 3,
    }));

    // Движение: отрезок от прежнего уровня к нынешнему.
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
          // Единица зависит от того, нормировалась ли величина: у малой
          // возрастной подгруппы медианы нет, и показывается измеренное
          // значение. Без различия читатель сравнил бы доли медианы с
          // цитированиями в месяц.
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
        // Границы целые, иначе деления не попадают на целые числа и подписи
        // уровней встают мимо своих полос.
        min: -1,
        max: levels.length,
        interval: 1,
        axisLine: { lineStyle: { color: line } },
        splitLine: { lineStyle: { color: line, type: "dashed" as const } },
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
        axisLine: { lineStyle: { color: line } },
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
          // Разделители полос «нет данных»: без них отсутствие величины
          // выглядело бы просто малым значением.
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
              // Нулевая линия отделяет измеренное внимание от его отсутствия,
              // а вертикаль — записи без вычисленного уровня от уровня L0.
              { yAxis: 0, name: t("map.noAttention") },
              { xAxis: 0, name: "" },
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
