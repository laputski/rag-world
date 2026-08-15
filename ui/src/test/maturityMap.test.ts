import { describe, expect, it } from "vitest";

import { bandOffsets } from "../components/MaturityMap";
import map from "../../public/data/map.json";

/**
 * Where a point stands inside its level band.
 *
 * The horizontal offset used to be set by confidence, and confidence is 1.0 for
 * every record that has a level at all: a level is granted by the very evidence
 * confidence measures, and evidence failing the checks is never stored. The
 * channel encoded a constant, and sixty-seven points piled into the same third
 * of their bands.
 *
 * The offset now says nothing on purpose, and these tests pin the two properties
 * that makes it worth having: no point hides another, and no reader can find a
 * meaning in the order.
 */

interface Point { id: string; level: string | null }

const points = (map as { points: Point[] }).points;

describe("positions inside a level band", () => {
  it("give every point in a band a place of its own", () => {
    const offsets = bandOffsets(points);
    const byBand = new Map<string, number[]>();
    for (const p of points) {
      const key = p.level ?? "";
      byBand.set(key, [...(byBand.get(key) ?? []), offsets.get(p.id)!]);
    }
    for (const [band, xs] of byBand) {
      expect(new Set(xs).size, `band ${band} places two points alike`).toBe(xs.length);
    }
  });

  it("space them evenly, so a band reads as a count", () => {
    const offsets = bandOffsets(points);
    const crowded = [...new Set(points.map((p) => p.level ?? ""))]
      .map((level) => points.filter((p) => (p.level ?? "") === level))
      .sort((a, b) => b.length - a.length)[0];
    expect(crowded.length).toBeGreaterThan(2);

    const xs = crowded.map((p) => offsets.get(p.id)!).sort((a, b) => a - b);
    const gaps = xs.slice(1).map((x, i) => x - xs[i]);
    const first = gaps[0];
    for (const gap of gaps) {
      expect(Math.abs(gap - first)).toBeLessThan(1e-9);
    }
  });

  it("stay inside their own band, so no point reads as the next level", () => {
    for (const x of bandOffsets(points).values()) {
      expect(Math.abs(x)).toBeLessThan(0.5);
    }
  });

  it("order by identifier, not by anything a reader could read into", () => {
    const sample: Point[] = [
      { id: "gamma", level: "L2" },
      { id: "alpha", level: "L2" },
      { id: "beta", level: "L2" },
    ];
    const offsets = bandOffsets(sample);
    expect(offsets.get("alpha")!).toBeLessThan(offsets.get("beta")!);
    expect(offsets.get("beta")!).toBeLessThan(offsets.get("gamma")!);
  });

  it("put a lone point in the middle of its band", () => {
    expect(bandOffsets([{ id: "only", level: "L4" }]).get("only")).toBe(0);
  });

  it("treat records without a level as a band of their own", () => {
    const offsets = bandOffsets([
      { id: "a", level: null },
      { id: "b", level: null },
      { id: "c", level: "L1" },
    ]);
    expect(offsets.get("a")).not.toBe(offsets.get("b"));
    expect(offsets.get("c")).toBe(0);
  });
});
