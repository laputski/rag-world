/*
  A harness for rendering pages over the published artefacts, served as the
  static host serves them. Written for the review of 2026-09-22, whose
  demonstrations of reader-facing defects became the tests beside it.
*/
import { ThemeProvider } from "@mui/material";
import {
  MemoryRouter, Outlet, Route, RouterProvider, Routes, createMemoryRouter, useLocation, useNavigate,
  useRouteError, type NavigateFunction, type RouteObject,
} from "react-router-dom";
import { render } from "@testing-library/react";
import { getTheme } from "../theme";

/*
  The artefacts enter the test build as modules, as they do in pages.test.tsx:
  the check then depends neither on the directory it was started from nor on
  the platform's file access, and fails intelligibly when an artefact is not
  built.
*/
const PREFIX = "../../public/data/";
const FILES = import.meta.glob("../../public/data/**/*.json", {
  eager: true, import: "default",
}) as Record<string, unknown>;

export const readData = (rel: string): any => FILES[`${PREFIX}${rel}`];

/** The text of a published artefact, as the host would serve it. */
export const dataText = (rel: string): string | undefined => {
  const payload = FILES[`${PREFIX}${rel}`];
  return payload === undefined ? undefined : JSON.stringify(payload);
};

/** fetch that serves the published artefacts, as the static host does, and records the URLs. */
export function diskFetch(overrides: Record<string, unknown> = {}) {
  const requested: string[] = [];
  const fn = (async (input: RequestInfo | URL) => {
    const url = String(input);
    requested.push(url);
    const rel = url.replace(/^\/data\//, "");
    if (rel in overrides) {
      return new Response(JSON.stringify(overrides[rel]), { status: 200 });
    }
    const text = url.startsWith("/data/") ? dataText(rel) : undefined;
    if (text === undefined) {
      // The host rewrites every unknown address to index.html with a 200.
      return new Response("<!doctype html><html></html>", { status: 200 });
    }
    return new Response(text, { status: 200 });
  }) as typeof fetch;
  return { fn, requested };
}

export function ErrorProbe() {
  const error = useRouteError() as Error | undefined;
  return <div data-testid="route-error">{String(error)}</div>;
}

export function Frame() {
  return (
    <ThemeProvider theme={getTheme("light")}>
      <Outlet context={{ mode: "light" }} />
    </ThemeProvider>
  );
}

/*
  A non-data router for tests that navigate: the data router builds a fetch
  Request on every navigation, and jsdom's AbortSignal is rejected by Node's
  Request constructor. MemoryRouter + <Routes> navigates without a Request.
*/
export const nav: { go: NavigateFunction | null; path: string } = { go: null, path: "" };
function Grab() {
  nav.go = useNavigate();
  nav.path = useLocation().pathname;
  return null;
}
export function mountNavigable(
  routes: { path: string; element: React.ReactNode }[],
  initial: string,
  layout?: React.ReactNode,
) {
  const inner = routes.map((r) => <Route key={r.path} path={r.path} element={r.element} />);
  return render(
    <ThemeProvider theme={getTheme("light")}>
      <MemoryRouter initialEntries={[initial]}>
        <Grab />
        <Routes>
          <Route element={layout ?? <Outlet context={{ mode: "light" }} />}>{inner}</Route>
        </Routes>
      </MemoryRouter>
    </ThemeProvider>,
  );
}

export function mount(children: RouteObject[], initial: string) {
  const router = createMemoryRouter(
    [{ element: <Frame />, errorElement: <ErrorProbe />, children }],
    { initialEntries: [initial] },
  );
  const view = render(<RouterProvider router={router} />);
  return { router, ...view };
}
