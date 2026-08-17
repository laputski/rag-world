/**
 * The anchors one page links into another by.
 *
 * They live apart from the pages that hold them because the page linking and
 * the page linked are loaded in different chunks: importing the name from the
 * page itself would drag that whole page into the chunk of the one pointing at
 * it, and the reader would pay for a page they may never open.
 *
 * A name here is a promise to somebody's bookmark as much as to the code, so it
 * is not renamed for the sake of tidiness.
 */

/** The section on the second axis of the map, on the About page. */
export const ATTENTION_ANCHOR = "attention";

/**
 * The section of the article on the maturity scale. The name is also the
 * identifier of that section in `generalizedData`, and the two have to agree:
 * the link is built from this constant and the anchor from the data.
 */
export const MATURITY_ANCHOR = "maturity";
