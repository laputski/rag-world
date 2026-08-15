import { describe, expect, it } from "vitest";

import { cellPlaces } from "../components/MaturityGrid";
import map from "../../public/data/map.json";

/**
 * Where a point stands inside its cell of the strata grid.
 *
 * A cell is an area rather than a line, so the map's single row of slots does
 * not carry over. The offsets used to be random and to run from zero upwards,
 * which cost twice: points overlapped, and every one of them sat above and to
 * the right of its own label, so the cell it belonged to had to be guessed.
 *
 * The crowding is real and not hypothetical: one cell holds nineteen points.
 */

interface Point { id: string; group: string | null; level: string | null }

const points = (map as { points: Point[] }).points;

describe("places inside a grid cell", () => {
  it("give every point in a cell a place of its own", () => {
    const places = cellPlaces(points);
    const byCell = new Map<string, string[]>();
    for (const p of points) {
      const key = `${p.group ?? ""}|${p.level ?? ""}`;
      const [x, y] = places.get(p.id)!;
      byCell.set(key, [...(byCell.get(key) ?? []), `${x.toFixed(6)},${y.toFixed(6)}`]);
    }
    for (const [cell, seats] of byCell) {
      expect(new Set(seats).size, `cell ${cell} seats two points alike`).toBe(seats.length);
    }
  });

  it("keep every point inside its own cell, symbol and all", () => {
    // Half a symbol is about a twentieth of a cell across and a tenth of one
    // down, and the boundary stands at half a cell.
    for (const [x, y] of cellPlaces(points).values()) {
      expect(Math.abs(x) + 0.06).toBeLessThan(0.5);
      expect(Math.abs(y) + 0.12).toBeLessThan(0.5);
    }
  });

  it("put a lone point in the middle of its cell", () => {
    const only = cellPlaces([{ id: "one", group: "A", level: "L4" }]).get("one");
    expect(only).toEqual([0, 0]);
  });

  it("centre each row on its own, so a ragged block still sits straight", () => {
    // Five points make three columns and two rows: three above, two below. Each
    // row has to be centred by its own count, or the last one hangs to one side.
    const places = cellPlaces(
      ["a", "b", "c", "d", "e"].map((id) => ({ id, group: "A", level: "L1" })),
    );
    const rows = new Map<number, number[]>();
    for (const [x, y] of places.values()) {
      rows.set(y, [...(rows.get(y) ?? []), x]);
    }
    for (const [y, xs] of rows) {
      const sum = xs.reduce((a, b) => a + b, 0);
      expect(Math.abs(sum), `row at ${y} is not centred`).toBeLessThan(1e-9);
    }
  });

  it("lay the block out wider than tall, as the cell is", () => {
    const places = cellPlaces(
      Array.from({ length: 8 }, (_, i) => ({ id: `p${i}`, group: "A", level: "L2" })),
    );
    const xs = new Set([...places.values()].map(([x]) => x.toFixed(6)));
    const ys = new Set([...places.values()].map(([, y]) => y.toFixed(6)));
    expect(xs.size).toBeGreaterThan(ys.size);
  });

  it("order by identifier, not by anything a reader could read into", () => {
    const places = cellPlaces(
      ["gamma", "alpha", "beta"].map((id) => ({ id, group: "B", level: "L2" })),
    );
    expect(places.get("alpha")![0]).toBeLessThan(places.get("beta")![0]);
    expect(places.get("beta")![0]).toBeLessThan(places.get("gamma")![0]);
  });
});
