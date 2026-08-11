import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { ThemeProvider } from "@mui/material";
import { Outlet, RouterProvider, createMemoryRouter } from "react-router-dom";

// Диаграмма рисуется на холсте, которого в тестовой среде нет. Проверяется
// поведение страницы, а не работа чужой библиотеки рисования, поэтому она
// заменяется отметкой о том, что место под диаграмму занято.
vi.mock("echarts-for-react", () => ({
  default: () => <div data-testid="диаграмма" />,
}));
import i18n from "../i18n/index";
import { getTheme } from "../theme";
import { HomePage } from "../pages/HomePage";
import { RegistryPage } from "../pages/RegistryPage";
import { TechCardPage } from "../pages/TechCardPage";
import { ChangesPage } from "../pages/ChangesPage";
import { DigestPage } from "../pages/DigestPage";
import { ResidualsPage } from "../pages/ResidualsPage";
import { CitePage } from "../pages/CitePage";
import { AboutPage } from "../pages/AboutPage";
import { NotFoundPage } from "../pages/NotFoundPage";
import { GeneralizedArticlePage } from "../pages/GeneralizedArticlePage";

/**
 * Страницы портала на настоящих данных.
 *
 * До этого файла читательская поверхность не проверялась ничем: двадцать три
 * теста покрывали дизайн-систему, состав словарей и оформление ссылки, и ни
 * один не отрисовывал страницу. Обе ошибки, найденные вычиткой (реестр в
 * статье и число измерений в подписи), увидел глаз, а не проверка.
 *
 * Данные берутся не выдуманные, а собранные: `fetch` отдаёт те самые файлы из
 * `public/data`, которые уходят на портал. Выдуманные данные проверяли бы, что
 * страница умеет рисовать выдуманное, тогда как ломается она на настоящем.
 */

// Артефакты вносятся в сборку теста как модули, а не читаются с диска: так
// проверка не зависит от того, из какого каталога её запустили, и падает
// внятно, если артефакт не собран.
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
    const payload = ARTIFACTS[name];
    if (payload === undefined) {
      return new Response("нет такого артефакта", { status: 404 });
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
 * Страница внутри настоящего маршрутизатора данных.
 *
 * Обёртка попроще не годится: карточка берёт идентификатор из адреса, страница
 * ненайденного — ошибку маршрута, а «Основания» — контекст оболочки. Подменять
 * это значило бы проверять не то, что видит читатель.
 */
function show(node: React.ReactNode, route = "/") {
  // Оболочка повторяет то, что даёт страницам настоящая: тему и контекст с
  // режимом. Именно из-за расхождения имён в этом контексте схемы на странице
  // «Основания» рисовались светлыми в тёмной теме, и типы этого не заметили.
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
        // Страница ненайденного читает ошибку маршрута, а её даёт только
        // маршрутизатор данных при несовпавшем адресе.
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
  }[];
};
const stats = statsJson as unknown as { total: number };

// ─── Каждая страница обязана открыться ───────────────────────────────────────
//
// Самая дешёвая и самая пропущенная проверка: страница, падающая на настоящих
// данных, обнаруживается сейчас читателем.

describe("страницы открываются на собранных данных", () => {
  const pages: [string, React.ReactNode, string?][] = [
    ["главная", <HomePage />],
    ["реестр", <RegistryPage />],
    ["хроника", <ChangesPage />],
    ["дайджест", <DigestPage />],
    ["очередь остатков", <ResidualsPage />],
    ["как ссылаться", <CitePage />],
    ["о портале", <AboutPage />],
    ["основания", <GeneralizedArticlePage />],
    ["страница не найдена", <NotFoundPage />, "/нет-такого-адреса"],
  ];

  it.each(pages)("%s", async (_name, node, route) => {
    const { container } = show(node, route ?? "/");
    await waitFor(() => {
      expect(container.textContent?.length ?? 0).toBeGreaterThan(40);
    });
    // Полоса ошибки означает, что страница не смогла прочитать свои данные.
    // Предупреждения и пояснения законны: страница «как ссылаться» ими и
    // объясняет, почему ссылаться надо на выпуск, а не на запись.
    const errors = screen.queryAllByRole("alert").filter((el) =>
      el.className.includes("colorError") || el.className.includes("standardError")
    );
    expect(errors).toEqual([]);
  });
});

// ─── Числа на странице приходят из данных ────────────────────────────────────

describe("числа приходят из данных, а не из текста", () => {
  it("реестр показывает все записи артефакта", async () => {
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

  it("карточка показывает столько свидетельств, сколько их в данных", async () => {
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

// ─── Отсутствие показывается как отсутствие ──────────────────────────────────

describe("отсутствие величины не подменяется нулём", () => {
  it("запись без вычисленного уровня не выглядит как L0", async () => {
    const without = registry.technologies.find((t) => t.level === null);
    expect(without, "в реестре нет записи без уровня, проверять нечего").toBeTruthy();
    show(<TechCardPage />, `/tech/${without!.id}`);
    await waitFor(() => {
      expect(screen.getAllByText(without!.name).length).toBeGreaterThan(0);
    });
    const heading = screen.getAllByText(without!.name)[0].closest("div")!;
    expect(within(heading).queryByText("L0")).toBeNull();
  });
});

// ─── Честность о собственных пределах ────────────────────────────────────────

describe("портал не выдаёт непроверенное за проверенное", () => {
  it("источник, закрытый для робота, помечен на карточке", async () => {
    const tech = registry.technologies.find((t) =>
      t.links.some((l) => l.status === "guarded")
    );
    expect(tech, "в реестре нет закрытых источников, проверять нечего").toBeTruthy();
    show(<TechCardPage />, `/tech/${tech!.id}`);
    await waitFor(() => {
      expect(screen.getAllByText(tech!.name).length).toBeGreaterThan(0);
    });
    expect(screen.getByText(i18n.t("link.guarded"))).toBeInTheDocument();
  });
});

// ─── Локализация видна читателю, а не только словарю ─────────────────────────

describe("английская версия не показывает русский текст", () => {
  it("карточка по-английски обходится без кириллицы", async () => {
    await i18n.changeLanguage("en");
    const tech = registry.technologies.find((t) => t.id === "hipporag")
      ?? registry.technologies[0];
    const { container } = show(<TechCardPage />, `/tech/${tech.id}`);
    await waitFor(() => {
      expect(screen.getAllByText(tech.name).length).toBeGreaterThan(0);
    });
    // Обоснования разбора остаются русскими намеренно и помечены `data-basis`;
    // они из проверки исключаются, всё остальное обязано быть переведено.
    // Отдельные кириллические слова могут оказаться именами собственными,
    // поэтому ищутся связные фразы, то есть два русских слова подряд.
    const copy = container.cloneNode(true) as HTMLElement;
    copy.querySelectorAll("[data-basis]").forEach((el) => el.remove());
    const russianPhrases = (copy.textContent ?? "").match(
      /[а-яё]{3,}\s+[а-яё]{3,}/gi
    );
    expect(russianPhrases ?? []).toEqual([]);
  });

  it("русское обоснование под английской версией названо русским", async () => {
    // Обоснования разбора не переводятся: каждое утверждает, что говорит
    // первоисточник, и машинный перевод изменил бы утверждение портала о
    // технологии. Умолчать об этом значило бы показать читателю русский абзац
    // без объяснения, и он решил бы, что портал сломан.
    await i18n.changeLanguage("en");
    const tech = registry.technologies.find((t) => t.id === "hipporag")
      ?? registry.technologies[0];
    show(<TechCardPage />, `/tech/${tech.id}`);
    await waitFor(() => {
      expect(screen.getAllByText(tech.name).length).toBeGreaterThan(0);
    });
    const openers = screen.getAllByText(i18n.t("techCard.showBasis"));
    expect(openers.length).toBeGreaterThan(0);
    fireEvent.click(openers[0]);
    await waitFor(() => {
      expect(
        screen.getAllByText(i18n.t("techCard.basisRussianOnly")).length
      ).toBeGreaterThan(0);
    });
  });

  it("очередь остатков по-английски обходится без кириллицы", async () => {
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
