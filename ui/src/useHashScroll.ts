import { useEffect } from "react";
import { useLocation } from "react-router-dom";

/**
 * Bring the section named in the address into view.
 *
 * A link from one page to a section of another carries an anchor, and the
 * browser cannot act on it here: the pages load on demand, so at the moment the
 * address is read the section it names does not exist yet. Nothing happens, the
 * reader lands at the top of a long page, and the link looks broken while being
 * correct.
 *
 * Scrolling once on arrival is not enough either. The page keeps growing under
 * the reader for a while after it appears: the diagrams of the article are
 * drawn asynchronously and each one that renders pushes everything below it
 * down. A position measured before that is wrong by thousands of pixels. So the
 * position is held while the page is still settling, and let go of at the first
 * sign that the reader has taken over.
 */

/** How long a page is given to settle. Beyond this it is not loading, it is broken. */
const SETTLE_MS = 2000;

/** The air left between the header and the heading landed on. */
const GAP = 12;

/**
 * What the reader does to say they want to be somewhere else. After any of
 * these the position is let go of: holding it would be a fight with them.
 */
const TAKEOVER = ["wheel", "touchstart", "keydown"] as const;

export function useHashScroll() {
  const { hash, pathname } = useLocation();

  useEffect(() => {
    if (!hash) return;
    const target = () => document.getElementById(decodeURIComponent(hash.slice(1)));
    if (!target()) return;

    let done = false;
    const stop = () => {
      if (done) return;
      done = true;
      observer.disconnect();
      clearTimeout(timer);
      for (const event of TAKEOVER) window.removeEventListener(event, stop);
    };

    /*
      The offset is measured rather than assumed. The header is sticky and
      stands over the top of the page, so a section brought exactly to the top
      arrives underneath it: the reader lands on a heading whose upper half is
      gone. Its height is not one number either, since on a narrow screen the
      header folds into two rows, so it is read from the header itself.
    */
    const hold = () => {
      if (done) return;
      const node = target();
      if (!node) return;
      const header = document.querySelector("header")?.getBoundingClientRect().height ?? 0;
      const top = node.getBoundingClientRect().top + window.scrollY - header - GAP;
      window.scrollTo({ top: Math.max(0, top) });
    };

    for (const event of TAKEOVER) window.addEventListener(event, stop, { passive: true });

    const observer = new ResizeObserver(hold);
    observer.observe(document.body);
    const timer = setTimeout(stop, SETTLE_MS);

    hold();
    return stop;
  }, [hash, pathname]);
}
