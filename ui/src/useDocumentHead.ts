import { useEffect } from "react";
import { useTranslation } from "react-i18next";
import { useLocation } from "react-router-dom";

/**
 * The title, the description and the canonical address of a page.
 *
 * The portal is assembled in the browser, so the markup served by the host holds
 * the values of the front page and only those. Sixty-five cards and the sections
 * shared one title between them: in bookmarks, in browser history, in search
 * results and in a forwarded link they all looked the same, and telling them
 * apart took opening them.
 *
 * A crawler that runs the page's code reads what this hook sets; a crawler that
 * runs no code reads the static values from the markup. Both answers are
 * truthful, the second is merely poorer.
 *
 * The language of the root element is set here as well: it declares the language
 * of the page and switches with the reader's choice.
 */

const SITE = "https://ragworld.org";
const SUFFIX = "RAG World";

interface Head {
  /** The page title without the portal name: that is appended here. */
  title?: string;
  /** One sentence about the page, for search results and link previews. */
  description?: string;
}

function setMeta(selector: string, attribute: string, value: string) {
  let node = document.head.querySelector<HTMLMetaElement | HTMLLinkElement>(selector);
  if (!node) {
    node = selector.startsWith("link")
      ? Object.assign(document.createElement("link"), { rel: selector.match(/rel="(.+?)"/)?.[1] })
      : Object.assign(document.createElement("meta"), {
          name: selector.match(/name="(.+?)"/)?.[1] ?? "",
        });
    if (selector.includes("property=")) {
      node.setAttribute("property", selector.match(/property="(.+?)"/)?.[1] ?? "");
    }
    document.head.appendChild(node);
  }
  node.setAttribute(attribute, value);
}

export function useDocumentHead({ title, description }: Head) {
  const { i18n } = useTranslation();
  const { pathname } = useLocation();

  useEffect(() => {
    document.documentElement.lang = i18n.language === "ru" ? "ru" : "en";

    const full = title ? `${title} — ${SUFFIX}` : SUFFIX;
    document.title = full;
    setMeta('meta[property="og:title"]', "content", full);

    if (description) {
      setMeta('meta[name="description"]', "content", description);
      setMeta('meta[property="og:description"]', "content", description);
    }

    // The canonical address carries neither language nor filter parameters: one
    // page with the same content must not look like several different ones.
    const url = `${SITE}${pathname}`;
    setMeta('link[rel="canonical"]', "href", url);
    setMeta('meta[property="og:url"]', "content", url);
  }, [title, description, pathname, i18n.language]);
}
