/** Загрузка данных портала.
 *
 * Портал статический: данные читаются из заранее собранных артефактов, которые
 * лежат рядом со сборкой. Живого сервера нет, поэтому отказ внешних источников
 * не приводит к отказу портала — он приводит только к устареванию данных, о чём
 * артефакт сообщает полем даты сборки и признаком устаревания.
 */

import type {
  Candidate,
  DigestIssue,
  ResidualMechanism,
  MaturityArtifact,
  RegistryChange,
  RegistryStats,
  RegistryTechnology,
} from "./types";

const DATA = "/data";

async function loadJson<T>(name: string): Promise<T> {
  const resp = await fetch(`${DATA}/${name}`);
  if (!resp.ok) {
    throw new Error(`${resp.status}: не удалось загрузить ${name}`);
  }
  return (await resp.json()) as T;
}

/** Карта зрелости: точки технологий с уровнем, вниманием и историей. */
export async function getMaturityMap(): Promise<MaturityArtifact> {
  return loadJson<MaturityArtifact>("map.json");
}

/** Реестр технологий целиком; отбор выполняется на клиенте. */
export async function getRegistry(): Promise<{
  count: number;
  built_at: string;
  technologies: RegistryTechnology[];
}> {
  return loadJson("registry.json");
}

/** Хроника изменений реестра. */
/**
 * Одна запись реестра отдельным файлом.
 *
 * Карточка читала весь реестр ради одной записи, то есть восемьсот килобайт на
 * страницу, куда чаще всего приходят по ссылке извне. Отдельный файл весит
 * около десяти килобайт и несёт ровно ту же запись.
 */
export async function getTechnology(id: string): Promise<RegistryTechnology> {
  const payload = await loadJson<{ technology: RegistryTechnology }>(`tech/${id}.json`);
  return payload.technology;
}

export async function getChanges(): Promise<{
  built_at: string;
  changes: RegistryChange[];
}> {
  return loadJson("changes.json");
}

/** Сводка: распределение по уровням, покрытие, свежесть. */
export async function getStats(): Promise<RegistryStats> {
  return loadJson<RegistryStats>("stats.json");
}

/** Выпуски дайджеста, свежие впереди. */
export async function getDigest(): Promise<{
  built_at: string;
  issues: DigestIssue[];
}> {
  return loadJson("digest.json");
}

/** Очередь остатков: механизмы, которых схема не выражает. */
/** Кандидаты в реестр: работы, найденные каталогом и ждущие решения. */
export async function getCandidates(): Promise<{
  built_at: string;
  candidates: Candidate[];
}> {
  return loadJson("candidates.json");
}

export async function getResiduals(): Promise<{
  built_at: string;
  candidate_threshold: number;
  mechanisms: ResidualMechanism[];
}> {
  return loadJson("residuals.json");
}
