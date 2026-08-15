import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { ThemeProvider } from "@mui/material";
import { STRATUM_COLORS, getTheme, stratumColor } from "../theme";
import { DIMENSIONS, SCHEMA_SIZE, STRATA, dimensionsOf } from "../schema.generated";
import { ConfigGlyph } from "../components/ConfigGlyph";
import "../i18n/index";

describe("the stratum palette", () => {
  it("covers all seven strata in both themes", () => {
    for (const mode of ["light", "dark"] as const) {
      const codes = Object.keys(STRATUM_COLORS[mode]).sort();
      expect(codes).toEqual(["A", "B", "C", "D", "E", "F", "G"]);
    }
  });

  it("holds no repeated hues", () => {
    for (const mode of ["light", "dark"] as const) {
      const values = Object.values(STRATUM_COLORS[mode]);
      expect(new Set(values).size).toBe(values.length);
    }
  });

  it("returns a neutral colour for an unknown stratum rather than crashing", () => {
    expect(stratumColor("Z", "light")).toMatch(/^#/);
  });
});

/**
 * The schema is checked here for internal consistency, and its size is not
 * written in as a number.
 *
 * A pinned "26" once called the correct value an error: the schema grew to
 * twenty-eight and the test failed on a generated file that must not be edited.
 * Agreement with the primary source is guarded by
 * `tests/architecture/test_schema_module_in_sync.py`, which can reach the Python
 * declaration and compares the module with it whole. The interface cannot see
 * that source, so what is checked here is what it can see.
 */
describe("the dimension schema in the interface", () => {
  it("matches the declared size", () => {
    expect(DIMENSIONS.length).toBe(SCHEMA_SIZE);
    expect(new Set(DIMENSIONS.map((d) => d.code)).size).toBe(SCHEMA_SIZE);
  });

  it("is laid out across seven strata with nothing lost", () => {
    expect(STRATA).toHaveLength(7);
    const total = STRATA.reduce((sum, s) => sum + dimensionsOf(s.code).length, 0);
    expect(total).toBe(DIMENSIONS.length);
  });

  it("the base value of every dimension belongs to its list of values", () => {
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

/** The filled cells: they carry a fill and the empty ones do not. */
function filledCells(container: HTMLElement): number {
  return Array.from(container.querySelectorAll("rect")).filter(
    (r) => r.getAttribute("fill") !== "transparent"
  ).length;
}

describe("the configuration fingerprint", () => {
  it("draws a cell for every dimension of the schema", () => {
    const { container } = renderGlyph({});
    expect(container.querySelectorAll("rect")).toHaveLength(SCHEMA_SIZE);
  });

  it("an empty configuration fills no cell", () => {
    const { container } = renderGlyph({});
    expect(filledCells(container)).toBe(0);
  });

  it("a base value fills no cell", () => {
    const a4 = DIMENSIONS.find((d) => d.code === "A4")!;
    const { container } = renderGlyph({ A4: a4.default });
    expect(filledCells(container)).toBe(0);
  });

  it("a value of its own fills exactly one cell", () => {
    const a4 = DIMENSIONS.find((d) => d.code === "A4")!;
    const other = a4.values.find((v) => v !== a4.default)!;
    const { container } = renderGlyph({ A4: other });
    expect(filledCells(container)).toBe(1);
  });

  it("identical configurations give identical fingerprints", () => {
    const config = { A4: "graph", C1: "graph_traversal" };
    const first = renderGlyph(config).container.innerHTML;
    const second = renderGlyph(config).container.innerHTML;
    expect(first).toBe(second);
  });

  it("different configurations give different fingerprints", () => {
    const graph = renderGlyph({ A4: "graph" }).container.innerHTML;
    const tree = renderGlyph({ A4: "tree" }).container.innerHTML;
    expect(graph).not.toBe(tree);
  });
});
