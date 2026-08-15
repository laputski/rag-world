import { describe, expect, it } from "vitest";
import { toBibTeX, toGost, toPlain } from "../citation";

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

/**
 * The persistent identifier of a release, once it has been deposited.
 *
 * A release is deposited after it is cut, so the identifier arrives later and is
 * recorded in the release index. Every citation format has to pick it up from
 * there: an address depends on the hosting outliving the citation, and that
 * dependency is the whole reason the identifier exists.
 */
describe("the identifier of a release", () => {
  const release = "2026-08-14";
  const doi = "10.5281/zenodo.21943979";

  it("reaches every citation format", () => {
    expect(toBibTeX({ release, doi })).toContain(`doi          = {${doi}}`);
    expect(toGost({ release, doi })).toContain(`DOI: ${doi}`);
    expect(toPlain({ release, doi })).toContain(`https://doi.org/${doi}`);
  });

  it("does not displace the address, which resolves without a library", () => {
    expect(toPlain({ release, doi })).toContain("ragworld.org");
    expect(toGost({ release, doi })).toContain("ragworld.org");
  });

  it("is absent from a release that has not been deposited", () => {
    expect(toBibTeX({ release })).not.toContain("doi");
    expect(toGost({ release })).not.toContain("DOI");
  });
});
