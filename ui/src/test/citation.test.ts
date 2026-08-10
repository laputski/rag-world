import { describe, expect, it } from "vitest";
import { toBibTeX, toGost } from "../citation";

/**
 * Ссылка обязана указывать на выпуск, а не на текущее состояние.
 *
 * Портал меняется: запись, на которую сослались вчера, сегодня может иметь
 * другой уровень. Ссылка без метки выпуска подтверждает не то, что
 * подтверждала, и хуже отсутствия ссылки — она выглядит надёжной.
 */
describe("библиографическая ссылка", () => {
  const release = "2026-08-10";

  it("на запись всегда содержит метку выпуска", () => {
    const target = { release, technology: { id: "pathrag", name: "PathRAG" } };
    expect(toBibTeX(target)).toContain(release);
    expect(toGost(target)).toContain(release);
    expect(toBibTeX(target)).toContain("release=2026-08-10");
  });

  it("на выпуск целиком ведёт к снимку, а не к текущим данным", () => {
    const text = toGost({ release });
    expect(text).toContain(`/data/releases/${release}/`);
    expect(text).not.toContain("/data/registry.json");
  });

  it("BibTeX содержит обязательные поля и закрывающую скобку", () => {
    const text = toBibTeX({ release });
    for (const field of ["author", "title", "year", "howpublished"]) {
      expect(text).toContain(field);
    }
    expect(text.trim().endsWith("}")).toBe(true);
  });

  it("ГОСТ называет дату обращения", () => {
    expect(toGost({ release })).toContain("дата обращения");
  });
});
