/**
 * Библиографическая ссылка на реестр и его записи.
 *
 * Ссылка всегда указывает на выпуск, а не на текущее состояние. Портал
 * меняется: запись, на которую сослались вчера, сегодня может иметь другой
 * уровень и другую конфигурацию, и ссылка подтвердит не то, что подтверждала.
 * Выпуск зафиксирован навсегда, поэтому ссылаться следует на него.
 *
 * Два формата: BibTeX для систем вёрстки и ГОСТ Р 7.0.5 для русских работ.
 */

const AUTHOR = "Лапутский А.";
const AUTHOR_LATIN = "Laputski, A.";
const TITLE = "RAG World: реестр технологий Retrieval-Augmented Generation";
const TITLE_LATIN = "RAG World: a registry of Retrieval-Augmented Generation technologies";
// Собственное имя портала, а не адрес площадки. Ссылка живёт дольше
// хостинга: переезд на другую площадку не должен обрывать ссылки в чужих
// работах, а адрес вида *.onrender.com принадлежит площадке, не порталу.
const BASE = "https://ragworld.org";

export interface CitationTarget {
  /** Метка выпуска: без неё ссылка указывает на изменяющийся объект. */
  release: string;
  /** Запись реестра; отсутствует, если ссылаются на выпуск целиком. */
  technology?: { id: string; name: string };
}

function releaseUrl(target: CitationTarget): string {
  return target.technology
    ? `${BASE}/tech/${target.technology.id}?release=${target.release}`
    : `${BASE}/data/releases/${target.release}/registry.json`;
}

function year(release: string): string {
  return release.slice(0, 4);
}

/** Ссылка в формате BibTeX. */
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
    `  howpublished = {\\url{${releaseUrl(target)}}}`,
    `}`,
  ].join("\n");
}

/** Ссылка по ГОСТ Р 7.0.5. */
export function toGost(target: CitationTarget): string {
  const what = target.technology
    ? `${target.technology.name} // ${TITLE}`
    : TITLE;
  return (
    `${AUTHOR} ${what} : выпуск ${target.release}. ` +
    `URL: ${releaseUrl(target)} (дата обращения: ${today()}).`
  );
}

function today(): string {
  const now = new Date();
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${pad(now.getDate())}.${pad(now.getMonth() + 1)}.${now.getFullYear()}`;
}
