import { describe, expect, it } from "vitest";
import { toBibTeX, toGost } from "../citation";

/**
 * A citation has to point at a release rather than at the current state.
 *
 * The portal changes: a record cited yesterday may carry a different level today.
 * A citation without a release tag supports something other than what it
 * supported, and is worse than no citation at all — it looks dependable.
 */
describe("a bibliographic citation", () => {
  const release = "2026-08-10";

  it("of a record always carries the release tag", () => {
    const target = { release, technology: { id: "pathrag", name: "PathRAG" } };
    expect(toBibTeX(target)).toContain(release);
    expect(toGost(target)).toContain(release);
    expect(toBibTeX(target)).toContain("release=2026-08-10");
  });

  it("of a whole release leads to the snapshot, not to the current data", () => {
    const text = toGost({ release });
    expect(text).toContain(`/data/releases/${release}/`);
    expect(text).not.toContain("/data/registry.json");
  });

  it("in BibTeX carries the required fields and the closing brace", () => {
    const text = toBibTeX({ release });
    for (const field of ["author", "title", "year", "howpublished"]) {
      expect(text).toContain(field);
    }
    expect(text.trim().endsWith("}")).toBe(true);
  });

  it("under GOST names the date accessed", () => {
    expect(toGost({ release })).toContain("дата обращения");
  });
});
