import { afterEach, describe, expect, it } from "vitest";
import { cleanup, fireEvent, screen, within } from "@testing-library/react";
import i18n from "../i18n/index";
import { TechCardPage } from "../pages/TechCardPage";
import { layoutDiagram, nodeLines, type Frame, type Layout } from "../components/ArchitectureDiagram";
import type { TechDiagram } from "../api/types";
import { diskFetch, mount, readData } from "./readerHarness";

/**
 * The hand-drawn architecture on a technology card.
 *
 * That the diagram agrees with the record is checked on the Python side, by
 * `tests/contract/test_diagrams.py`. What is checked here is what a reader meets:
 * the section shows only where a diagram exists, a step opens its card, the card
 * quotes the justification in the reader's language, and no layout puts one step
 * on top of another or outside the drawing.
 */

// The language is put back after the page is gone: switching it under a mounted
// page re-renders every component outside the test's control.
afterEach(async () => {
  cleanup();
  await i18n.changeLanguage("en");
});

const pathrag = readData("tech/pathrag.json").technology as { diagram: TechDiagram };

async function openCard(lang: string, id: string) {
  await i18n.changeLanguage(lang);
  globalThis.fetch = diskFetch().fn;
  const view = mount([{ path: "/tech/:id", element: <TechCardPage /> }], `/tech/${id}`);
  await screen.findByRole("heading", { name: readData(`tech/${id}.json`).technology.name });
  return view;
}

describe("the architecture section", () => {
  it("is drawn where the record has a diagram, a button per step", async () => {
    await openCard("en", "pathrag");
    const group = await screen.findByRole("group", { name: "Architecture: PathRAG" });
    const steps = within(group as unknown as HTMLElement).getAllByRole("button");
    expect(steps).toHaveLength(Object.keys(pathrag.diagram.nodes).length);
    // Every code on the page is the one the artefact carries for that step.
    const shown = Object.fromEntries(
      steps.map((s) => [s.getAttribute("data-node"), s.getAttribute("data-codes")])
    );
    const expected = Object.fromEntries(
      Object.entries(pathrag.diagram.nodes).map(([id, n]) => [id, Object.keys(n.codes).join(" ")])
    );
    expect(shown).toEqual(expected);
  });

  it("is absent, without an empty frame, where the record has none", async () => {
    await openCard("en", "bm25_sparse");
    expect(screen.queryByText("Architecture")).toBeNull();
    expect(screen.queryByRole("group", { name: /Architecture/ })).toBeNull();
  });

  it("opens the card of a step with its justification and its section", async () => {
    await openCard("en", "pathrag");
    fireEvent.click(await screen.findByRole("button", { name: /^Keyword extraction/ }));
    const card = await screen.findByTestId("architecture-card");
    expect(card.textContent).toContain("B1");
    expect(card.textContent).toContain("A language model draws keywords out of the query");
    expect(card.textContent).not.toMatch(/[А-Яа-яЁё]/);
    const link = within(card).getByRole("link", { name: "Node Retrieval" });
    expect(link.getAttribute("href")).toBe("https://arxiv.org/html/2502.14902v2#Sx4.SSx1");
  });

  it("speaks Russian on a Russian card", async () => {
    await openCard("ru", "pathrag");
    fireEvent.click(await screen.findByRole("button", { name: /^Выделение ключевых слов/ }));
    const card = await screen.findByTestId("architecture-card");
    expect(card.textContent).toContain("Языковая модель вынимает из запроса ключевые слова");
  });

  // A residual is what the schema cannot say about a step. It was carried by
  // twenty-two steps and shown on none: the card listed codes only.
  it("names the residual of a step in words, not as a code", async () => {
    await openCard("en", "unified");
    fireEvent.click(await screen.findByRole("button", { name: /^Retrieved triples/ }));
    const residual = await screen.findByTestId("architecture-residual");
    expect(residual.textContent).toContain("the whole result of an exact query, with no cut");
    expect(residual.textContent).toContain("Everything that satisfies the conditions");
    expect(residual.textContent).not.toContain("whole_query_result");
  });

  it("names the residual in Russian on a Russian card", async () => {
    await openCard("ru", "unified");
    fireEvent.click(await screen.findByRole("button", { name: /^Найденные тройки/ }));
    const residual = await screen.findByTestId("architecture-residual");
    expect(residual.textContent).toContain("весь результат точного запроса без отсечения");
    expect(residual.textContent).not.toMatch(/[a-z]_[a-z]/);
  });

  it("has words for every residual on every step of every diagram", () => {
    const missing: string[] = [];
    for (const [id] of drawn) {
      const tech = readData(`tech/${id}.json`).technology as {
        diagram: TechDiagram;
        parse_notes: { residual?: string; residual_term?: string | null; residual_term_en?: string | null }[];
      };
      for (const [step, node] of Object.entries(tech.diagram.nodes)) {
        if (!node.residual) continue;
        const note = tech.parse_notes.find((n) => n.residual === node.residual);
        if (!note?.residual_term || !note?.residual_term_en) missing.push(`${id}.${step}`);
      }
    }
    expect(missing).toEqual([]);
  });

  it("opens and closes a card from the keyboard", async () => {
    await openCard("en", "pathrag");
    const step = await screen.findByRole("button", { name: /^Entity and relation extraction/ });
    fireEvent.keyDown(step, { key: "Enter" });
    expect((await screen.findByTestId("architecture-card")).textContent).toContain(
      "A language model finds the entities"
    );
    fireEvent.keyDown(step, { key: " " });
    expect(screen.queryByTestId("architecture-card")).toBeNull();
  });
});

function clashes(frames: Record<string, Frame>, width: number, height: number): string[] {
  const out: string[] = [];
  const list = Object.entries(frames);
  for (const [id, f] of list) {
    if (f.x < 0 || f.y < 0 || f.x + f.w > width || f.y + f.h > height) out.push(`${id} outside`);
  }
  list.forEach(([a, A], i) =>
    list.slice(i + 1).forEach(([b, B]) => {
      if (A.x < B.x + B.w && B.x < A.x + A.w && A.y < B.y + B.h && B.y < A.y + A.h) {
        out.push(`${a} over ${b}`);
      }
    })
  );
  return out;
}

// Every drawn record, not only the pilot: a diagram added later must not be the
// one whose row is too wide or whose steps collide.
const drawn = (readData("registry.json").technologies as { id: string; diagram?: TechDiagram }[])
  .filter((tech) => tech.diagram)
  .map((tech) => [tech.id, tech.diagram as TechDiagram] as const);

// The widest advance per character measured in a browser on 2026-10-21, over
// every line of at least fifteen characters on all cards: titles (14px, 500)
// reach 8.6 in Cyrillic, second lines (12px) 7.2. The layout itself estimates
// with smaller figures and a generous padding; this check asks only whether the
// text, at its widest, stays inside its frame with the 3px margin the browser
// check uses.
const TITLE_MEASURED = 8.7;
const SUB_MEASURED = 7.3;

/** Steps whose text, at its widest, would run out of the frame it is given. */
function overflowing(diagram: TechDiagram, lang: string, layout: Layout): string[] {
  return Object.entries(layout.frames).flatMap(([step, frame]) => {
    const { title, sub, marks } = nodeLines(diagram, step, lang);
    const second = (sub ? `${sub} · ` : "").length + marks.length;
    const need = Math.max(title.length * TITLE_MEASURED, second * SUB_MEASURED);
    return need > frame.w - 6 ? [`${step} text wider than its frame`] : [];
  });
}

describe("the layout", () => {
  for (const lang of ["en", "ru"]) {
    for (const narrow of [false, true]) {
      it(`keeps every step of every diagram inside the drawing and apart (${lang}, ${narrow ? "narrow" : "wide"})`, () => {
        const found: Record<string, unknown> = {};
        for (const [id, diagram] of drawn) {
          const layout = layoutDiagram(diagram, lang, narrow);
          const problems = clashes(layout.frames, layout.width, layout.height);
          // On a wide screen no diagram may fall back to one column: a row too
          // wide is a defect of its wording, not something to hide.
          if (layout.width !== (narrow ? 340 : 680)) problems.push(`width ${layout.width}`);
          // Only in one column: there every step gets the same width, set by the
          // drawing rather than by its text. In the wide layout the frame is
          // sized from the text itself, and the upper bound below would cry
          // over lines the browser shows whole.
          if (narrow) problems.push(...overflowing(diagram, lang, layout));
          if (problems.length) found[id] = problems;
        }
        expect(found).toEqual({});
      });
    }
  }

  it("catches a line too long for the one-column layout", () => {
    // The bait is the wording that ran out of its frame on a phone, found by a
    // browser pass over every card: a second line of the Qdrant diagram.
    const qdrant = (readData("tech/qdrant.json").technology as { diagram: TechDiagram }).diagram;
    const spoiled = structuredClone(qdrant);
    spoiled.nodes.fusion.sub = "по рангам или по распределению оценок";
    expect(overflowing(spoiled, "ru", layoutDiagram(spoiled, "ru", true))).toContain(
      "fusion text wider than its frame"
    );
    expect(overflowing(qdrant, "ru", layoutDiagram(qdrant, "ru", true))).toEqual([]);
  });

  it("draws no arrow between parallel branches and dashes a loop", () => {
    const plain = layoutDiagram(pathrag.diagram, "en", false);
    const branched = structuredClone(pathrag.diagram);
    branched.breaks = [["nodes", "paths"]];
    branched.loops = [["paths", "keywords"]];
    for (const narrow of [false, true]) {
      const before = layoutDiagram(pathrag.diagram, "en", narrow);
      const after = layoutDiagram(branched, "en", narrow);
      expect(after.arrows.filter((a) => !a.dashed)).toHaveLength(before.arrows.length - 1);
      expect(after.arrows.filter((a) => a.dashed)).toHaveLength(1);
    }
    expect(plain.arrows.every((a) => !a.dashed)).toBe(true);
  });

  it("sends a row too wide for the drawing into one column rather than cutting it", () => {
    const wide = structuredClone(pathrag.diagram);
    for (const id of wide.rows[1]) {
      wide.nodes[id].title_en = "A step whose title runs far too long";
    }
    const layout = layoutDiagram(wide, "en", false);
    expect(layout.width).toBe(340);
    expect(clashes(layout.frames, layout.width, layout.height)).toEqual([]);
  });
});
