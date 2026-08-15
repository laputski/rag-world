/**
 * A bibliographic citation of the registry and of its records.
 *
 * A citation always points at a release rather than at the current state. The
 * portal changes: a record cited yesterday may today carry a different level and
 * a different configuration, and the citation would support something other than
 * what it supported. A release is fixed for ever, so a release is what to cite.
 *
 * Two formats: BibTeX for typesetting systems, and GOST R 7.0.5 for works
 * written in Russian.
 */

// The portal itself stands as the author. The registry is assembled and updated
// without a person taking part in each individual change, and signing it with a
// personal name would credit a person with what a rule did.
const AUTHOR = "RAG World";
const AUTHOR_LATIN = "RAG World";
const TITLE = "RAG World: реестр технологий Retrieval-Augmented Generation";
const TITLE_LATIN = "RAG World: a registry of Retrieval-Augmented Generation technologies";
// The portal's own name rather than the address of a hosting platform. A
// citation outlives its host: moving to another platform must not break links in
// somebody else's work, and an address of the form *.onrender.com belongs to the
// platform and not to the portal.
const BASE = "https://ragworld.org";

export interface CitationTarget {
  /** The release tag: without it a citation points at a changing object. */
  release: string;
  /** A registry record; absent when the whole release is cited. */
  technology?: { id: string; name: string };
  /**
   * The persistent identifier of this release, once it has been deposited.
   *
   * It is preferred over the address wherever a citation style has room for it:
   * the address depends on the hosting outliving the citation, and the identifier
   * does not. The address stays beside it, because it resolves for a reader with
   * no library behind them.
   */
  doi?: string;
}

function releaseUrl(target: CitationTarget): string {
  return target.technology
    ? `${BASE}/tech/${target.technology.id}?release=${target.release}`
    : `${BASE}/data/releases/${target.release}/registry.json`;
}

function year(release: string): string {
  return release.slice(0, 4);
}

/** The resolvable form of an identifier, for the styles that want a link. */
function doiUrl(doi: string): string {
  return `https://doi.org/${doi}`;
}

/** The citation in BibTeX form. */
export function toBibTeX(target: CitationTarget): string {
  const key = target.technology
    ? `ragworld:${target.technology.id}:${target.release}`
    : `ragworld:${target.release}`;
  const title = target.technology
    ? `${target.technology.name} --- ${TITLE_LATIN}`
    : TITLE_LATIN;
  return [
    `@misc{${key},`,
    `  author       = {${AUTHOR_LATIN}},`,
    `  title        = {${title}},`,
    `  year         = {${year(target.release)}},`,
    `  note         = {Release ${target.release}},`,
    ...(target.doi ? [`  doi          = {${target.doi}},`] : []),
    `  howpublished = {\\url{${releaseUrl(target)}}}`,
    `}`,
  ].join("\n");
}

/** The citation under GOST R 7.0.5. */
export function toGost(target: CitationTarget): string {
  const what = target.technology
    ? `${target.technology.name} // ${TITLE}`
    : TITLE;
  const doi = target.doi ? `DOI: ${target.doi}. ` : "";
  return (
    `${AUTHOR}. ${what} : выпуск ${target.release}. ${doi}` +
    `URL: ${releaseUrl(target)} (дата обращения: ${today("ru")}).`
  );
}

/**
 * The citation in the ordinary English form.
 *
 * GOST is of no use to an English-speaking reader: it is a Russian standard, and
 * its layout inside somebody else's work looks like a mistake. What is given
 * instead is the plain order of author, title, version, address and date
 * accessed, which suits most styles.
 */
export function toPlain(target: CitationTarget): string {
  const what = target.technology
    ? `${target.technology.name}. In ${TITLE_LATIN}`
    : TITLE_LATIN;
  const doi = target.doi ? `${doiUrl(target.doi)}. ` : "";
  return (
    `${AUTHOR_LATIN}. ${what}. Release ${target.release}. ${doi}` +
    `Available at: ${releaseUrl(target)} (accessed ${today("en")}).`
  );
}

function today(lang: "ru" | "en"): string {
  const now = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  if (lang === "en") {
    return now.toISOString().slice(0, 10);
  }
  return `${pad(now.getDate())}.${pad(now.getMonth() + 1)}.${now.getFullYear()}`;
}
