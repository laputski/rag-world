import { lazy } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { ThemeProvider } from "@mui/material";
import { RouterProvider, createMemoryRouter, useRouteError } from "react-router-dom";

// The option handed to the chart is kept rather than drawn: the test
// environment has no canvas, and what is under test is where a point goes.
const chart: { option?: { series: { type: string; data: { point: { id: string } }[] }[] } } = {};
vi.mock("echarts-for-react", () => ({
  default: (props: { option: typeof chart.option }) => {
    chart.option = props.option;
    return <div data-testid="diagram" />;
  },
}));

import i18n from "../i18n/index";
import { getTheme } from "../theme";
import { getGeneralizedContent } from "../generalizedData";
import { MaturityGrid } from "../components/MaturityGrid";
import { AppLayout } from "../layouts/AppLayout";
import { AboutPage } from "../pages/AboutPage";
import { DigestPage } from "../pages/DigestPage";
import { HomePage } from "../pages/HomePage";
import { NotFoundPage } from "../pages/NotFoundPage";
import { RegistryPage } from "../pages/RegistryPage";
import { ResidualsPage } from "../pages/ResidualsPage";
import { TechCardPage } from "../pages/TechCardPage";
import { dataText, diskFetch, mount, mountNavigable, nav, readData } from "./readerHarness";

/**
 * Defects a reader meets, found by the review of 2026-09-22.
 *
 * Each was demonstrated on the published artefacts before it was fixed, and
 * each test here failed on the code as it stood. They run over the real data
 * rather than invented data, for the reason `pages.test.tsx` gives: what breaks
 * a page is the real thing.
 */

afterEach(() => cleanup());

const CYRILLIC_PHRASE = /[а-яё]{3,}\s+[а-яё]{3,}/gi;

describe("the candidate queue", () => {
  for (const lang of ["en", "ru"]) {
    it(`words every signal the published queue carries (${lang})`, () => {
      const codes = new Set<string>();
      for (const row of readData("candidates.json").candidates as {
        fit: { signals: { code: string }[] };
      }[]) {
        for (const signal of row.fit.signals) codes.add(signal.code);
      }
      const missing = [...codes].filter(
        (code) => !i18n.exists(`candidates.signal.${code}`, { lng: lang }),
      );
      expect(missing).toEqual([]);
    });

    it(`shows no raw key and names the lists that hold a work (${lang})`, async () => {
      await i18n.changeLanguage(lang);
      globalThis.fetch = diskFetch().fn;
      const { container } = mount(
        [{ path: "/residuals", element: <ResidualsPage /> }], "/residuals",
      );
      fireEvent.click(await screen.findByText(new RegExp(`^${i18n.t("candidates.title")} · \\d+`)));
      await waitFor(() => expect(container.textContent).toContain(i18n.t("candidates.fitWhat")));
      const items = [...container.querySelectorAll("li")].map((li) => li.textContent ?? "");
      expect(items.filter((text) => text.startsWith("candidates.signal."))).toEqual([]);
      expect(items.some((text) => text.includes("Awesome-GraphRAG"))).toBe(true);
    });
  }
});

describe("an English card", () => {
  it("carries no Russian phrase outside the marked justifications, on any record", async () => {
    await i18n.changeLanguage("en");
    globalThis.fetch = diskFetch().fn;
    const found: Record<string, string[]> = {};
    for (const tech of readData("registry.json").technologies as { id: string; name: string }[]) {
      const { container } = mount([{ path: "/tech/:id", element: <TechCardPage /> }], `/tech/${tech.id}`);
      await screen.findByRole("heading", { name: tech.name });
      const copy = container.cloneNode(true) as HTMLElement;
      copy.querySelectorAll("[data-basis]").forEach((el) => el.remove());
      const phrases = (copy.textContent ?? "").match(CYRILLIC_PHRASE);
      if (phrases) found[tech.id] = phrases;
      cleanup();
    }
    expect(found).toEqual({});
  }, 60000);
});

describe("the build date", () => {
  // It is shown as written. Read through `Date` it became midnight in
  // Greenwich, and west of it the reader saw the day before.
  it("on the front page is the day of the build", async () => {
    await i18n.changeLanguage("ru");
    globalThis.fetch = diskFetch().fn;
    mount([{ path: "/", element: <HomePage /> }], "/");
    const built = readData("map.json").built_at as string;
    expect(await screen.findByText(`${i18n.t("common.builtAt")}: ${built}`)).toBeTruthy();
  });

  it("in the registry is the day of the build", async () => {
    await i18n.changeLanguage("ru");
    globalThis.fetch = diskFetch().fn;
    const { container } = mount([{ path: "/registry", element: <RegistryPage /> }], "/registry");
    const built = readData("registry.json").built_at as string;
    await waitFor(() =>
      expect(container.textContent).toContain(`${i18n.t("common.builtAt")} ${built}`),
    );
  });
});

describe("the strata grid", () => {
  it("places no record without a stratum in a stratum, and names it", async () => {
    await i18n.changeLanguage("en");
    const map = readData("map.json");
    const outside = (map.points as { id: string; name: string; group: string | null }[])
      .filter((p) => !p.group);
    expect(outside.length).toBeGreaterThan(0);

    render(
      <ThemeProvider theme={getTheme("light")}>
        <MaturityGrid artifact={map} />
      </ThemeProvider>,
    );
    const drawn = chart.option!.series
      .filter((s) => s.type === "scatter")
      .flatMap((s) => s.data.map((d) => d.point.id));
    for (const p of outside) {
      expect(drawn).not.toContain(p.id);
      expect(screen.getByText((text) => text.includes(p.name))).toBeTruthy();
    }
  });
});

describe("the article", () => {
  for (const lang of ["ru", "en"] as const) {
    it(`prints no Markdown in a reference or a diagram (${lang})`, () => {
      const content = getGeneralizedContent(lang);
      const markdown = /\[[^\]]+\]\((https?:\/\/[^)]+)\)/;
      expect(content.refs.filter((r) => markdown.test(r.label)).map((r) => r.label)).toEqual([]);
      expect(content.refs.filter((r) => r.url && /[[\]()]/.test(r.url)).map((r) => r.url)).toEqual([]);
      const diagrams = content.sections.map((s) => s.diagram ?? "");
      expect(diagrams.filter((d) => markdown.test(d))).toEqual([]);
    });
  }
});

describe("the digest", () => {
  const demotion = {
    built_at: "2026-09-28",
    issues: [{
      issued_at: "2026-09-28", since: "2026-09-21",
      text: "Понизилась в уровне: PathRAG с L3 до L1.", text_en: "Fell in level: PathRAG from L3 to L1.",
      added: [], promoted: [],
      demoted: [{ technology_id: "pathrag", name: "PathRAG", level_before: "L3", level_after: "L1" }],
      evidence_added: 0, evidence_by_type: {}, links_checked: 0, links_broken: 0, by_level: {}, total: 76,
    }],
  };

  for (const lang of ["en", "ru"]) {
    it(`words a fall as a fall (${lang})`, async () => {
      await i18n.changeLanguage(lang);
      globalThis.fetch = diskFetch({ "digest.json": demotion }).fn;
      mount([{ path: "/digest", element: <DigestPage /> }], "/digest");
      fireEvent.click(await screen.findByText(i18n.t("digest.showBasis", { count: 1 })));
      const row = (await screen.findByText("PathRAG")).parentElement!;
      await waitFor(() =>
        expect(row.textContent).toContain(i18n.t("digest.fell", { from: "L3", to: "L1" })),
      );
    });
  }

  it("keeps its keys unique when an issue moves one record twice", async () => {
    await i18n.changeLanguage("en");
    globalThis.fetch = diskFetch().fn;
    const duplicates: string[] = [];
    const spy = vi.spyOn(console, "error").mockImplementation((...args: unknown[]) => {
      if (String(args[0]).includes("same key")) duplicates.push(String(args[1]));
    });
    mount([{ path: "/digest", element: <DigestPage /> }], "/digest");
    await screen.findByText("2026-08-09");
    spy.mockRestore();
    expect(duplicates).toEqual([]);
  });
});

describe("the frame", () => {
  // The shell of `main.tsx`, which cannot be imported: it mounts the
  // application on import. It hands the router's error to the frame the same way.
  function Shell() {
    const failed = Boolean(useRouteError());
    return (
      <ThemeProvider theme={getTheme("light")}>
        <AppLayout mode="light" onToggleMode={() => {}} lang="en" onSetLang={() => {}}
          onOpenSearch={() => {}} failed={failed} />
      </ThemeProvider>
    );
  }
  // What a reader with an open tab meets after a redeploy: the page's chunk
  // is gone.
  const BrokenChunk = lazy(() => Promise.reject(new TypeError("Failed to fetch dynamically imported module")));

  it("explains a page that failed instead of showing an empty frame", async () => {
    await i18n.changeLanguage("en");
    const router = createMemoryRouter(
      [{
        element: <Shell />,
        errorElement: <Shell />,
        children: [
          { path: "/registry", element: <BrokenChunk /> },
          { path: "*", element: <NotFoundPage /> },
        ],
      }],
      { initialEntries: ["/registry"] },
    );
    const { container } = render(<RouterProvider router={router} />);
    await waitFor(() =>
      expect(container.querySelector("main")?.textContent).toContain(i18n.t("notFound.brokenTitle")),
    );
  });

  it("opens a page whose anchor does not decode", async () => {
    await i18n.changeLanguage("en");
    globalThis.fetch = diskFetch().fn;
    const { container } = mount([{ path: "/about", element: <AboutPage /> }], "/about#%E0%A4%A");
    await waitFor(() => expect(container.textContent).toContain(i18n.t("about.title")));
    expect(container.querySelector('[data-testid="route-error"]')).toBeNull();
  });
});

describe("the head of the document", () => {
  // The data router builds a Request on every navigation, and Node's Request
  // refuses the AbortSignal of the test environment; a plain stand-in does.
  class PlainRequest {
    url: string; method: string; signal: AbortSignal; headers = new Headers();
    constructor(url: string | URL, init?: { method?: string; signal?: AbortSignal }) {
      this.url = String(url); this.method = init?.method ?? "GET"; this.signal = init?.signal as AbortSignal;
    }
  }

  it("does not keep the previous page's description", async () => {
    const original = globalThis.Request;
    (globalThis as { Request: unknown }).Request = PlainRequest;
    try {
      await i18n.changeLanguage("en");
      globalThis.fetch = diskFetch().fn;
      const { router } = mount([
        { path: "/registry", element: <RegistryPage /> },
        { path: "*", element: <NotFoundPage /> },
      ], "/registry");
      await screen.findByText("PathRAG");
      await act(async () => { await router.navigate("/no-such-page"); });
      await screen.findByText(i18n.t("notFound.title"));
      const meta = (sel: string) => document.head.querySelector(sel)?.getAttribute("content");
      expect(meta('meta[name="description"]')).not.toContain(i18n.t("head.registry.description"));
      expect(meta('meta[property="og:description"]')).not.toContain(i18n.t("head.registry.description"));
    } finally {
      (globalThis as { Request: unknown }).Request = original;
    }
  });
});

describe("a technology card", () => {
  it("shows the record in the address, whichever answer arrives last", async () => {
    await i18n.changeLanguage("en");
    // The answers are released by hand, so their order can be chosen.
    const release = new Map<string, () => void>();
    globalThis.fetch = ((input: RequestInfo | URL) => new Promise<Response>((resolve) => {
      const url = String(input);
      release.set(url, () => resolve(new Response(dataText(url.replace("/data/", "")))));
    })) as typeof fetch;
    const { container } = mountNavigable([{ path: "/tech/:id", element: <TechCardPage /> }], "/tech/raptor");
    await waitFor(() => expect(release.has("/data/tech/raptor.json")).toBe(true));
    // The reader opens another record before the first has arrived.
    await act(async () => { nav.go!("/tech/pathrag"); });
    await waitFor(() => expect(release.has("/data/tech/pathrag.json")).toBe(true));
    await act(async () => { release.get("/data/tech/pathrag.json")!(); });
    await screen.findByRole("heading", { name: "PathRAG" });
    await act(async () => {
      release.get("/data/tech/raptor.json")!();
      await new Promise((r) => setTimeout(r, 20));
    });
    expect(nav.path).toBe("/tech/pathrag");
    expect(container.querySelector("h3")?.textContent).toBe("PathRAG");
    expect(document.title).toBe("PathRAG — RAG World");
  });
});
