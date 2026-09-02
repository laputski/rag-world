/**
 * The two placements of the attention axis, and what each must keep apart.
 *
 * The chart itself is somebody else's drawing library and is not exercised here.
 * What is exercised is the option handed to it, because that is where the
 * decisions of this component live: where a value lands on the height, and what
 * the axis says it is.
 *
 * Two properties are pinned, and both were broken during the work that added the
 * second placement. The axis named itself logarithmic while the linear placement
 * was in force, which is worse than saying nothing: a reader who has learned
 * that distances are logarithms carries it over to the view where they are not.
 * And a record cited zero times sat at the foot of the scale, where it read as
 * "rarely cited" rather than as "never cited".
 */

import { render } from "@testing-library/react";
import { beforeAll, describe, expect, it, vi } from "vitest";

import type { MaturityArtifact, MaturityPoint } from "../api/types";

// The mock keeps the option instead of drawing it: the option is the subject.
let lastOption: Record<string, unknown> | null = null;
vi.mock("echarts-for-react", () => ({
  default: (props: { option: Record<string, unknown> }) => {
    lastOption = props.option;
    return <div data-testid="chart" />;
  },
}));

import i18n from "../i18n/index";
import { MaturityMap } from "../components/MaturityMap";

function point(over: Partial<MaturityPoint> & { id: string }): MaturityPoint {
  return {
    name: over.id,
    kind: "architecture",
    group: "A",
    groups: ["A"],
    level: "L2",
    confidence: 1,
    evidence_basis: "computed",
    attention: null,
    attention_raw: null,
    attention_cohort: null,
    first_published: null,
    prose_id: over.id,
    history: [],
    ...over,
  } as MaturityPoint;
}

const artifact: MaturityArtifact = {
  built_at: "2026-09-01",
  rule_version: "1.0.0",
  levels: ["L0", "L1", "L2", "L3", "L4", "L5", "L6"],
  strata: [{ code: "A", name: "Knowledge representation" }],
  points: [
    point({ id: "cited", attention: 5, attention_raw: 5, attention_cohort: "2024" }),
    point({ id: "silent", attention: 0, attention_raw: 0, attention_cohort: "2024" }),
    point({ id: "unknown" }),
  ],
  count: 3,
  stale: false,
};

/*
  Each render is taken down before the next: while both stayed mounted, a change
  of language re-rendered the first and it overwrote the option of the second, so
  the two placements came out identical and the test read one of them twice.
*/
function optionFor(scale: "log" | "linear") {
  lastOption = null;
  const { unmount } = render(<MaturityMap artifact={artifact} scale={scale} />);
  const option = lastOption;
  unmount();
  if (!option) throw new Error("the chart was given no option");
  return option as {
    yAxis: { name: string };
    series: { type: string; data?: { value: number[]; point?: MaturityPoint }[] }[];
  };
}

function heightOf(option: ReturnType<typeof optionFor>, id: string): number {
  for (const series of option.series) {
    for (const item of series.data ?? []) {
      if (item.point?.id === id) return item.value[1];
    }
  }
  throw new Error(`no point ${id} on the chart`);
}

describe("the attention axis", () => {
  // Without the instance the words come out as their keys, and a test that reads
  // keys would pass while the reader saw nothing.
  beforeAll(async () => {
    await i18n.changeLanguage("en");
  });

  it("names the placement in force, and names it differently for each", () => {
    const log = optionFor("log").yAxis.name;
    const linear = optionFor("linear").yAxis.name;
    expect(log).not.toEqual(linear);
    expect(log.toLowerCase()).toContain("logarithm");
    expect(linear.toLowerCase()).toContain("linear");
    expect(log.toLowerCase()).not.toContain("linear");
  });

  it("keeps a measured zero apart from an absent value on the logarithm", () => {
    // Three states, three places: cited, cited nothing, nobody counted. The
    // logarithm has no place for zero, so the zero gets a band of its own; the
    // absent value goes lower still, as it always did.
    const option = optionFor("log");
    const cited = heightOf(option, "cited");
    const silent = heightOf(option, "silent");
    const unknown = heightOf(option, "unknown");
    expect(silent).toBeLessThan(cited);
    expect(unknown).toBeLessThan(silent);
    // And the zero does not sit at the foot of the scale, where it would read as
    // a small value rather than as none.
    expect(silent).toBeLessThan(Math.log10(0.1));
  });

  it("puts a measured zero at zero on the linear placement", () => {
    // There the scale has a place for it, so a band would say a thing the data
    // does not: the old view is kept as it was.
    const option = optionFor("linear");
    expect(heightOf(option, "silent")).toEqual(0);
    expect(heightOf(option, "unknown")).toBeLessThan(0);
  });

  it("lays a value out by its logarithm and by itself, according to the scale", () => {
    expect(heightOf(optionFor("log"), "cited")).toBeCloseTo(Math.log10(5), 6);
    expect(heightOf(optionFor("linear"), "cited")).toEqual(5);
  });
});
