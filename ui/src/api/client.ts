/** Загрузка данных портала.
 *
 * Портал статический: данные читаются из заранее собранных артефактов, которые
 * лежат рядом со сборкой. Живого сервера нет, поэтому отказ внешних источников
 * не приводит к отказу портала — он приводит только к устареванию данных, о чём
 * артефакт сообщает полем даты сборки и признаком устаревания.
 */

import type {
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
