import { useEffect, useRef } from "react";
import { useLocation } from "react-router-dom";

/**
 * Counting the visits of a portal assembled in the browser.
 *
 * The counter itself is loaded from the markup and counts the first visit on
 * its own. What it cannot see is everything after: moving from the map to a
 * record loads no document, so without this hook a reader who walked through
 * ten sections would be counted once, and every section but the entry one would
 * look unvisited.
 *
 * The number of the counter is written down here a second time, the first being
 * in `index.html`: a script in the markup shares nothing with the modules of
 * the bundle. If it is changed, it is changed in both places.
 */

const COUNTER = 111641296;

declare global {
  interface Window {
    ym?: (counter: number, action: string, ...rest: unknown[]) => void;
  }
}

export function useMetrikaHit() {
  const { pathname } = useLocation();
  // The address the reader came from, for the chain of transitions inside the
  // portal: without it every section looks like an entry point.
  const previous = useRef<string | null>(null);

  useEffect(() => {
    // The address carries no filter parameters, as the canonical one does not:
    // narrowing the registry is not a visit to another page, and counted as one
    // it would bury the sections under the facets of a single reader.
    const url = `${window.location.origin}${pathname}`;

    // The first run is the visit the counter has already sent for itself on
    // load. Sending it again would double the entry page against all the rest.
    if (previous.current === null) {
      previous.current = url;
      return;
    }

    window.ym?.(COUNTER, "hit", url, { referer: previous.current, title: document.title });
    previous.current = url;
  }, [pathname]);
}
