import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { ThemeProvider } from "@mui/material";
import { STRATUM_COLORS, getTheme, stratumColor } from "../theme";
import { DIMENSIONS, SCHEMA_SIZE, STRATA, dimensionsOf } from "../schema.generated";
import { ConfigGlyph } from "../components/ConfigGlyph";
import "../i18n/index";

describe("палитра стратов", () => {
  it("покрывает все семь стратов в обеих темах", () => {
    for (const mode of ["light", "dark"] as const) {
      const codes = Object.keys(STRATUM_COLORS[mode]).sort();
      expect(codes).toEqual(["A", "B", "C", "D", "E", "F", "G"]);
    }
  });

  it("не содержит повторяющихся оттенков", () => {
    for (const mode of ["light", "dark"] as const) {
      const values = Object.values(STRATUM_COLORS[mode]);
      expect(new Set(values).size).toBe(values.length);
    }
  });

  it("для неизвестной страты возвращает нейтральный цвет, а не падает", () => {
    expect(stratumColor("Z", "light")).toMatch(/^#/);
  });
});

describe("схема измерений в интерфейсе", () => {
  it("совпадает по размеру с объявленным", () => {
    expect(DIMENSIONS.length).toBe(SCHEMA_SIZE);
    expect(SCHEMA_SIZE).toBe(26);
  });

  it("разложена по семи стратам без потерь", () => {
    expect(STRATA).toHaveLength(7);
    const total = STRATA.reduce((sum, s) => sum + dimensionsOf(s.code).length, 0);
    expect(total).toBe(DIMENSIONS.length);
  });

  it("у каждого измерения значение по умолчанию входит в список значений", () => {
    const broken = DIMENSIONS.filter((d) => !d.values.includes(d.default));
    expect(broken.map((d) => d.code)).toEqual([]);
  });
});

function renderGlyph(configuration: Record<string, string>) {
  return render(
    <ThemeProvider theme={getTheme("light")}>
      <ConfigGlyph configuration={configuration} />
    </ThemeProvider>
  );
}

/** Залитые клетки: у них есть заливка, а у пустых её нет. */
function filledCells(container: HTMLElement): number {
  return Array.from(container.querySelectorAll("rect")).filter(
    (r) => r.getAttribute("fill") !== "transparent"
  ).length;
}

describe("отпечаток конфигурации", () => {
  it("рисует клетку на каждое измерение схемы", () => {
    const { container } = renderGlyph({});
    expect(container.querySelectorAll("rect")).toHaveLength(SCHEMA_SIZE);
  });

  it("пустая конфигурация не заливает ни одной клетки", () => {
    const { container } = renderGlyph({});
    expect(filledCells(container)).toBe(0);
  });

  it("значение по умолчанию клетку не заливает", () => {
    const a4 = DIMENSIONS.find((d) => d.code === "A4")!;
    const { container } = renderGlyph({ A4: a4.default });
    expect(filledCells(container)).toBe(0);
  });

  it("собственное значение заливает ровно одну клетку", () => {
    const a4 = DIMENSIONS.find((d) => d.code === "A4")!;
    const other = a4.values.find((v) => v !== a4.default)!;
    const { container } = renderGlyph({ A4: other });
    expect(filledCells(container)).toBe(1);
  });

  it("одинаковые конфигурации дают одинаковый отпечаток", () => {
    const config = { A4: "graph", C1: "graph_traversal" };
    const first = renderGlyph(config).container.innerHTML;
    const second = renderGlyph(config).container.innerHTML;
    expect(first).toBe(second);
  });

  it("разные конфигурации дают разные отпечатки", () => {
    const graph = renderGlyph({ A4: "graph" }).container.innerHTML;
    const tree = renderGlyph({ A4: "tree" }).container.innerHTML;
    expect(graph).not.toBe(tree);
  });
});
