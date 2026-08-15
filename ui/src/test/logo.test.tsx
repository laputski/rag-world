// @vitest-environment jsdom
/**
 * The mark of the portal.
 *
 * What is checked is not how it looks but three properties whose breach still
 * looks like a sound mark and is discovered on somebody else's page, or not at
 * all.
 *
 * The pattern is given rather than derived from the data. A mark that changes
 * with every weekly pass is not something anyone learns to recognise, and
 * substituting data would make it one.
 *
 * A small size gives a simplification rather than compressed porridge. Twenty-six
 * cells at sixteen pixels give a cell thinner than a pixel, and the mark turns
 * into a smudge exactly where it is shown most often.
 *
 * The mark and the word beside it are one link. Two links to one address double
 * the stop in keyboard traversal and make a screen reader name the target
 * twice.
 */

import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { ThemeProvider } from "@mui/material";
import { I18nextProvider } from "react-i18next";

import i18n from "../i18n/index";
import { getTheme } from "../theme";
import { Logo, logoCells, logoWidth, COMPACT_BELOW } from "../components/Logo";
import { AppLayout } from "../layouts/AppLayout";
import LOGO_SOURCE from "../components/Logo.tsx?raw";

describe("the pattern of the mark", () => {
  it("is given rather than derived from the registry", () => {
    expect(LOGO_SOURCE).not.toMatch(/getRegistry|registry\.json|configuration\[/);
    expect(LOGO_SOURCE).toContain("PATTERN");
  });

  it("is the same on every render", () => {
    expect(logoCells(32, "dark")).toEqual(logoCells(32, "dark"));
  });

  it("covers all seven strata", () => {
    const colors = new Set(logoCells(32, "dark").map((cell) => cell.color));
    expect(colors.size).toBe(7);
  });

  it("the cells do not overlap", () => {
    const cells = logoCells(32, "dark");
    for (const cell of cells) {
      const clash = cells.find(
        (other) =>
          other !== cell &&
          other.x < cell.x + cell.side &&
          cell.x < other.x + other.side &&
          other.y < cell.y + cell.side &&
          cell.y < other.y + other.side
      );
      expect(clash, `the cell ${cell.x},${cell.y} is overlapped`).toBeUndefined();
    }
  });

  it("fits within the declared size", () => {
    for (const size of [16, 20, 26, 32, 96]) {
      const width = logoWidth(size);
      for (const cell of logoCells(size, "light")) {
        expect(cell.x + cell.side).toBeLessThanOrEqual(width + 0.001);
        expect(cell.y + cell.side).toBeLessThanOrEqual(size + 0.001);
      }
    }
  });
});

describe("a small size", () => {
  it("gives a simplification rather than compressed porridge", () => {
    const small = logoCells(16, "dark");
    const full = logoCells(32, "dark");
    expect(small.length).toBeLessThan(full.length);
    // A cell has to stay visible: a fraction of the size rather than a leftover.
    for (const cell of small) expect(cell.side).toBeGreaterThan(3);
  });

  it("the threshold is declared rather than scattered through the code", () => {
    expect(logoCells(COMPACT_BELOW, "dark").length)
      .toBeGreaterThan(logoCells(COMPACT_BELOW - 1, "dark").length);
  });

  it("the simplification stays the same fingerprint", () => {
    const small = new Set(logoCells(16, "dark").map((c) => c.color));
    const full = new Set(logoCells(32, "dark").map((c) => c.color));
    for (const color of small) expect(full.has(color)).toBe(true);
  });
});

describe("the mark in the header", () => {
  const shell = () => (
    <I18nextProvider i18n={i18n}>
      <ThemeProvider theme={getTheme("dark")}>
        <MemoryRouter>
          <AppLayout
            mode="dark"
            onToggleMode={() => {}}
            lang="en"
            onSetLang={() => {}}
            onOpenSearch={() => {}}
          />
        </MemoryRouter>
      </ThemeProvider>
    </I18nextProvider>
  );

  it("stands to the left of the wordmark", () => {
    const { container } = render(shell());
    const home = container.querySelector('a[href="/"]');
    expect(home, "there is no link to the front page").not.toBeNull();
    const svg = home!.querySelector("svg");
    expect(svg, "there is no mark inside the link").not.toBeNull();
    expect(home!.textContent).toContain("RAG World");
    /*
      The order in the markup sets both the order things are announced in and the
      order they are traversed. What is compared is the position of the nodes
      rather than the mark being the first child: on a narrow screen it is wrapped
      in a box that hides it, and a demand for "first child" would forbid the
      wrapper itself.
    */
    const word = [...home!.querySelectorAll("span")]
      .find((node) => node.textContent === "RAG World")!;
    expect(word, "there is no wordmark in the pair").toBeDefined();
    const order = svg!.compareDocumentPosition(word);
    expect(order & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  /*
    What is checked is the pair rather than the whole header. A navigation item
    may also lead to the front page, and that is legitimate: it is part of the
    navigation. What is inadmissible is the mark and the word being two links
    standing next to each other, because keyboard traversal then stops twice on
    the same thing.
  */
  it("the mark and the word are one link, not two side by side", () => {
    const { container } = render(shell());
    const lockup = container.querySelector('a[href="/"]')!;
    expect(lockup.querySelectorAll("a").length).toBe(0);
    expect(lockup.querySelectorAll("svg").length).toBe(1);
    expect(lockup.textContent).toBe("RAG World");
  });

  it("is not announced separately from the word beside it", () => {
    const { container } = render(shell());
    const svg = container.querySelector('a[href="/"] svg');
    expect(svg?.getAttribute("aria-hidden")).toBe("true");
  });
});

describe("the mark on its own", () => {
  it("names itself when it stands without a word", () => {
    render(
      <ThemeProvider theme={getTheme("light")}>
        <Logo size={48} />
      </ThemeProvider>
    );
    expect(screen.getByRole("img", { name: "RAG World" })).toBeInTheDocument();
  });

  it("takes the theme palette when none is given explicitly", () => {
    const light = logoCells(32, "light").map((c) => c.color);
    const dark = logoCells(32, "dark").map((c) => c.color);
    expect(light).not.toEqual(dark);
  });
});
