import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { ThemeProvider } from "@mui/material";
import { Outlet, RouterProvider, createMemoryRouter } from "react-router-dom";

// The chart is drawn on a canvas the test environment does not have. What is
// under test is the behaviour of the page rather than the work of somebody
// else's drawing library, so it is replaced by a marker that the space for the
// chart is taken.
vi.mock("echarts-for-react", () => ({
  default: () => <div data-testid="diagram" />,
}));
import i18n from "../i18n/index";
import { getTheme } from "../theme";
import { HomePage } from "../pages/HomePage";
import { RegistryPage } from "../pages/RegistryPage";
import { TechCardPage } from "../pages/TechCardPage";
import { ChangesPage } from "../pages/ChangesPage";
import { DigestPage } from "../pages/DigestPage";
import { ResidualsPage } from "../pages/ResidualsPage";
import { AboutPage } from "../pages/AboutPage";
import { NotFoundPage } from "../pages/NotFoundPage";
import { GeneralizedArticlePage } from "../pages/GeneralizedArticlePage";

/**
 * The pages of the portal over the real data.
 *
 * Before this file the reader-facing surface was checked by nothing: three tests
 * covered the design system, the contents of the dictionaries and the formatting,
 * and none of them rendered a page. Both errors found by proofreading (the count
 * in the article and the number of dimensions in a label) were caught by eye
 * rather than by a check.
 *
 * The data is not invented but built: `fetch` returns the very files from
 * `public/data` that go to the portal. Invented data checks that a page can draw
 * what was invented, whereas what breaks it is the real thing.
 */

// The artefacts enter the test build as modules rather than being read from
// disk, so the check does not depend on which directory it was started from and
// fails intelligibly when an artefact is not built.
import mapJson from "../../public/data/map.json";
import registryJson from "../../public/data/registry.json";
import changesJson from "../../public/data/changes.json";
import statsJson from "../../public/data/stats.json";
import digestJson from "../../public/data/digest.json";
import residualsJson from "../../public/data/residuals.json";
import releasesJson from "../../public/data/releases/index.json";

const ARTIFACTS: Record<string, unknown> = {
  "map.json": mapJson,
  "registry.json": registryJson,
  "changes.json": changesJson,
  "stats.json": statsJson,
  "digest.json": digestJson,
  "residuals.json": residualsJson,
  "index.json": releasesJson,
};

beforeAll(() => {
  globalThis.fetch = (async (input: RequestInfo | URL) => {
    const url = String(input);
    const name = url.slice(url.lastIndexOf("/") + 1);
    /*
      A technology card asks for one record rather than the whole registry. The
      answer is assembled here from the same built artefact, so the check still
      runs over the real data and not over an invented record.
    */
    if (url.includes("/tech/")) {
      const id = name.replace(/\.json$/, "");
      const found = (registryJson as { technologies: { id: string }[] })
        .technologies.find((t) => t.id === id);
      if (!found) return new Response("no such record", { status: 404 });
      return new Response(
        JSON.stringify({ built_at: (registryJson as { built_at: string }).built_at, technology: found }),
        { status: 200, headers: { "content-type": "application/json" } },
      );
    }
    const payload = ARTIFACTS[name];
    if (payload === undefined) {
      return new Response("no such artefact", { status: 404 });
    }
    return new Response(JSON.stringify(payload), {
      status: 200,
      headers: { "content-type": "application/json" },
    });
  }) as typeof fetch;
});

afterEach(async () => {
  await i18n.changeLanguage("ru");
});

/**
 * A page inside the real data router.
 *
 * A simpler wrapper will not do: a card takes its identifier from the route, the
 * not-found page takes the route error, and Foundations takes the outlet context.
 * Substituting any of that would mean checking something other than what the
 * reader sees.
 */
function show(node: React.ReactNode, route = "/") {
  // The shell repeats what the real one gives the pages: the theme with its
  // mode. It was a mismatch of names in exactly this context that drew the
  // Foundations diagrams light inside the dark theme, and the types said nothing.
  const Shell = () => (
    <ThemeProvider theme={getTheme("light")}>
      <Outlet context={{ mode: "light" }} />
    </ThemeProvider>
  );
  const wrapped = <ThemeProvider theme={getTheme("light")}>{node}</ThemeProvider>;
  const router = createMemoryRouter(
    [
      {
        path: "/",
        element: <Shell />,
        // The not-found page reads the route error, which the data router
        // supplies when no address matches.
        errorElement: wrapped,
        children: [
          { index: true, element: node },
          { path: "tech/:id", element: node },
        ],
      },
    ],
    { initialEntries: [route] }
  );
  return render(<RouterProvider router={router} />);
}

const registry = registryJson as unknown as {
  count: number;
  technologies: {
    id: string;
    name: string;
    level: string | null;
    evidence_count: number;
    links: { url: string; status: string }[];
    parse_notes: { did_en?: string }[];
  }[];
};
const stats = statsJson as unknown as { total: number };

// ─── Every page has to open ──────────────────────────────────────────────────
//
// The cheapest check and the one most often skipped: a page that crashes on the
// real data is currently discovered by the reader.

describe("the pages open over the built data", () => {
  const pages: [string, React.ReactNode, string?][] = [
    ["front page", <HomePage />],
    ["registry", <RegistryPage />],
    ["chronicle", <ChangesPage />],
    ["digest", <DigestPage />],
    ["residual queue", <ResidualsPage />],
    ["about", <AboutPage />],
    ["foundations", <GeneralizedArticlePage />],
    ["not found", <NotFoundPage />, "/no-such-address"],
  ];

  it.each(pages)("%s", async (_name, node, route) => {
    const { container } = show(node, route ?? "/");
    await waitFor(() => {
      expect(container.textContent?.length ?? 0).toBeGreaterThan(40);
    });
    // An error strip means the page could not read the data. Warnings and
    // explanations are legitimate: the "how to cite" section explains why a
    // release should be cited rather than a record.
    const errors = screen.queryAllByRole("alert").filter((el) =>
      el.className.includes("colorError") || el.className.includes("standardError")
    );
    expect(errors).toEqual([]);
  });
});

// ─── The numbers on a page come from the data ────────────────────────────────

describe("the numbers come from the data, not from the text", () => {
  it("the registry shows every record of the artefact", async () => {
    show(<RegistryPage />);
    await waitFor(() => {
      expect(screen.getByText(registry.technologies[0].name)).toBeInTheDocument();
    });
    for (const tech of registry.technologies.slice(0, 12)) {
      expect(screen.getAllByText(tech.name).length).toBeGreaterThan(0);
    }
    expect(registry.count).toBe(registry.technologies.length);
    expect(stats.total).toBe(registry.technologies.length);
  });

  it("a card shows as much evidence as the data holds", async () => {
    const tech = registry.technologies.find((t) => t.evidence_count > 3)!;
    show(<TechCardPage />, `/tech/${tech.id}`);
    await waitFor(() => {
      expect(screen.getAllByText(tech.name).length).toBeGreaterThan(0);
    });
    expect(
      screen.getByText(new RegExp(`\\(${tech.evidence_count}\\)`))
    ).toBeInTheDocument();
  });
});

// ─── An absence is shown as an absence ───────────────────────────────────────

describe("an absent quantity is never replaced by a zero", () => {
  it("a record with no computed level does not look like L0", async () => {
    const without = registry.technologies.find((t) => t.level === null);
    expect(without, "the registry has no record without a level; nothing to check").toBeTruthy();
    show(<TechCardPage />, `/tech/${without!.id}`);
    await waitFor(() => {
      expect(screen.getAllByText(without!.name).length).toBeGreaterThan(0);
    });
    const heading = screen.getAllByText(without!.name)[0].closest("div")!;
    expect(within(heading).queryByText("L0")).toBeNull();
  });
});

// ─── Honesty about its own limits ────────────────────────────────────────────

describe("the portal does not pass the unchecked off as checked", () => {
  it("a source closed to a robot is marked on the card", async () => {
    const tech = registry.technologies.find((t) =>
      t.links.some((l) => l.status === "guarded")
    );
    expect(tech, "the registry has no closed sources; nothing to check").toBeTruthy();
    show(<TechCardPage />, `/tech/${tech!.id}`);
    await waitFor(() => {
      expect(screen.getAllByText(tech!.name).length).toBeGreaterThan(0);
    });
    expect(screen.getByText(i18n.t("link.guarded"))).toBeInTheDocument();
  });
});

// ─── The localisation is visible to the reader, not only to the dictionary ───

describe("the English version shows no Russian text", () => {
  it("an English card does without Cyrillic", async () => {
    await i18n.changeLanguage("en");
    const tech = registry.technologies.find((t) => t.id === "hipporag")
      ?? registry.technologies[0];
    const { container } = show(<TechCardPage />, `/tech/${tech.id}`);
    await waitFor(() => {
      expect(screen.getAllByText(tech.name).length).toBeGreaterThan(0);
    });
    // The reading justifications stay Russian deliberately and are marked as
    // such, so they are excluded from the check; everything else has to be
    // English. Isolated Cyrillic words may turn out to be names, so what is
    // looked for is connected phrases, that is, two Russian words in a row.
    const copy = container.cloneNode(true) as HTMLElement;
    copy.querySelectorAll("[data-basis]").forEach((el) => el.remove());
    const russianPhrases = (copy.textContent ?? "").match(
      /[а-яё]{3,}\s+[а-яё]{3,}/gi
    );
    expect(russianPhrases ?? []).toEqual([]);
  });

  it("a translated justification is shown in English", async () => {
    await i18n.changeLanguage("en");
    const tech = registry.technologies.find((x) =>
      x.parse_notes?.some((n) => n.did_en)
    );
    expect(tech, "not one justification is translated").toBeTruthy();
    show(<TechCardPage />, `/tech/${tech!.id}`);
    await waitFor(() => {
      expect(screen.getAllByText(tech!.name).length).toBeGreaterThan(0);
    });
    fireEvent.click(screen.getAllByText(i18n.t("techCard.showBasis"))[0]);
    const translated = tech!.parse_notes.find((n) => n.did_en)!;
    await waitFor(() => {
      expect(screen.getAllByText(translated.did_en!).length).toBeGreaterThan(0);
    });
  });

  it("an untranslated justification is named as untranslated", async () => {
    // A blank space and a silent Russian paragraph look equally like a breakage,
    // so the reader is told that this record is not translated yet.
    await i18n.changeLanguage("en");
    const tech = registry.technologies.find((x) =>
      x.parse_notes?.length > 0 && x.parse_notes.every((n) => !n.did_en)
    );
    if (!tech) return; // the translation is complete; nothing to check
    show(<TechCardPage />, `/tech/${tech.id}`);
    await waitFor(() => {
      expect(screen.getAllByText(tech.name).length).toBeGreaterThan(0);
    });
    fireEvent.click(screen.getAllByText(i18n.t("techCard.showBasis"))[0]);
    await waitFor(() => {
      expect(
        screen.getAllByText(i18n.t("techCard.basisNotYetTranslated")).length
      ).toBeGreaterThan(0);
    });
  });

  it("the residual queue in English does without Cyrillic", async () => {
    await i18n.changeLanguage("en");
    const { container } = show(<ResidualsPage />);
    await waitFor(() => {
      expect(container.textContent?.length ?? 0).toBeGreaterThan(80);
    });
    const russianPhrases = (container.textContent ?? "").match(
      /[а-яё]{3,}\s+[а-яё]{3,}/gi
    );
    expect(russianPhrases ?? []).toEqual([]);
  });
});
