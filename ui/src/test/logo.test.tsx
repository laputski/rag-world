// @vitest-environment jsdom
/**
 * Знак портала.
 *
 * Проверяется не то, как он выглядит, а три свойства, нарушение которых
 * выглядит исправным знаком и обнаруживается на чужой странице либо не
 * обнаруживается вовсе.
 *
 * Рисунок задан и не выводится из данных. Знак, меняющийся вместе с
 * еженедельным прогоном, узнавать нечему, а подмена данными прошла бы молча.
 *
 * Мелкий размер даёт упрощение, а не сжатую кашу. Двадцать восемь клеток в
 * шестнадцати пикселях дают клетку тоньше пикселя, и знак превращается в грязь
 * ровно там, где чаще всего показывается.
 *
 * Знак и слово рядом — одна ссылка. Две ссылки на один адрес удваивают
 * остановку при обходе с клавиатуры и заставляют читалку назвать цель дважды.
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

describe("рисунок знака", () => {
  it("задан, а не выведен из реестра", () => {
    expect(LOGO_SOURCE).not.toMatch(/getRegistry|registry\.json|configuration\[/);
    expect(LOGO_SOURCE).toContain("PATTERN");
  });

  it("одинаков при каждом отображении", () => {
    expect(logoCells(32, "dark")).toEqual(logoCells(32, "dark"));
  });

  it("покрывает все семь страт", () => {
    const colors = new Set(logoCells(32, "dark").map((cell) => cell.color));
    expect(colors.size).toBe(7);
  });

  it("клетки не наезжают друг на друга", () => {
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
      expect(clash, `клетка ${cell.x},${cell.y} перекрыта`).toBeUndefined();
    }
  });

  it("умещается в объявленные размеры", () => {
    for (const size of [16, 20, 26, 32, 96]) {
      const width = logoWidth(size);
      for (const cell of logoCells(size, "light")) {
        expect(cell.x + cell.side).toBeLessThanOrEqual(width + 0.001);
        expect(cell.y + cell.side).toBeLessThanOrEqual(size + 0.001);
      }
    }
  });
});

describe("мелкий размер", () => {
  it("даёт упрощение, а не сжатую кашу", () => {
    const small = logoCells(16, "dark");
    const full = logoCells(32, "dark");
    expect(small.length).toBeLessThan(full.length);
    // Клетка обязана оставаться видимой: доля от размера, а не остаток.
    for (const cell of small) expect(cell.side).toBeGreaterThan(3);
  });

  it("порог объявлен, а не разбросан по коду", () => {
    expect(logoCells(COMPACT_BELOW, "dark").length)
      .toBeGreaterThan(logoCells(COMPACT_BELOW - 1, "dark").length);
  });

  it("упрощение остаётся тем же отпечатком", () => {
    const small = new Set(logoCells(16, "dark").map((c) => c.color));
    const full = new Set(logoCells(32, "dark").map((c) => c.color));
    for (const color of small) expect(full.has(color)).toBe(true);
  });
});

describe("знак в шапке", () => {
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

  it("стоит слева от словесного знака", () => {
    const { container } = render(shell());
    const home = container.querySelector('a[href="/"]');
    expect(home, "ссылки на главную нет").not.toBeNull();
    const svg = home!.querySelector("svg");
    expect(svg, "знака в ссылке нет").not.toBeNull();
    expect(home!.textContent).toContain("RAG World");
    // Порядок в разметке задаёт и порядок озвучивания, и порядок обхода.
    expect(home!.firstElementChild?.tagName.toLowerCase()).toBe("svg");
  });

  /*
    Проверяется связка, а не весь заголовок. Пункт «карта зрелости» тоже ведёт
    на главную, и это законно: он часть навигации. Недопустимо другое — чтобы
    знак и слово были двумя ссылками, стоящими вплотную, потому что обход с
    клавиатуры тогда останавливается дважды на одном и том же.
  */
  it("знак и слово — одна ссылка, а не две вплотную", () => {
    const { container } = render(shell());
    const lockup = container.querySelector('a[href="/"]')!;
    expect(lockup.querySelectorAll("a").length).toBe(0);
    expect(lockup.querySelectorAll("svg").length).toBe(1);
    expect(lockup.textContent).toBe("RAG World");
  });

  it("не озвучивается отдельно от слова рядом", () => {
    const { container } = render(shell());
    const svg = container.querySelector('a[href="/"] svg');
    expect(svg?.getAttribute("aria-hidden")).toBe("true");
  });
});

describe("знак сам по себе", () => {
  it("называет себя, когда стоит без слова", () => {
    render(
      <ThemeProvider theme={getTheme("light")}>
        <Logo size={48} />
      </ThemeProvider>
    );
    expect(screen.getByRole("img", { name: "RAG World" })).toBeInTheDocument();
  });

  it("берёт палитру темы, если она не задана явно", () => {
    const light = logoCells(32, "light").map((c) => c.color);
    const dark = logoCells(32, "dark").map((c) => c.color);
    expect(light).not.toEqual(dark);
  });
});
