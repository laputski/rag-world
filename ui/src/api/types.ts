/** Типы данных портала.
 *
 * Портал статический: все структуры ниже приходят из заранее собранных
 * артефактов (`public/data/*.json`), а не от живого сервера.
 *
 * Отсутствие величины всюду обозначается `null`, а не нулём. Ноль означал бы,
 * что величину измерили и она равна нулю; для «не измеряли» это неправда, и
 * представления обязаны показывать различие.
 */

/** Запись реестра технологий. */
export interface RegistryTechnology {
  id: string;
  name: string;
  aliases: string[];
  /** Род объекта: paradigm | architecture | technique | tool | artifact. */
  kind: string;
  family: string | null;
  /** Страты измерений, к которым относится вклад технологии (A–G). */
  groups: string[];
  core_idea: string | null;
  /** Идентификатор локализованной прозы карточки. */
  prose_id: string | null;
  first_published: string | null;
  /** Значения измерений: главное поле для сравнения технологий. */
  configuration: Record<string, string>;
  /** Механизмы, не выразимые схемой измерений (формулировки из словаря). */
  residual: string[];
  /** Измерения, значение которых выбирается во время работы или по режиму. */
  configuration_variable: string[];
  /** Измерения, к объекту неприменимые: значения в конфигурации не имеют. */
  configuration_inapplicable: string[];
  /**
   * Дата разбора конфигурации по первоисточникам; null — не разбиралась.
   * Отличает значение, сверенное с источником, от базового: выглядят они
   * одинаково, а утверждают разное.
   */
  configuration_reviewed: string | null;
  links: RegistryLink[];
  /** Вычисленный уровень зрелости; null — уровень не вычислялся. */
  level: string | null;
  confidence: number | null;
  /** `computed` — вычислено правилом, `manual` — введено человеком. */
  evidence_basis: string | null;
  attention: number | null;
  attention_raw: number | null;
  attention_cohort: string | null;
  evidence_count: number;
  evidence: EvidenceRecord[];
  /** Вывод правила: какие уровни выполнены и какие нет. */
  level_reason: LevelReason | null;
}

export interface EvidenceRecord {
  type: string;
  value: string | null;
  source: string;
  fetched_at: string;
  /** `auto` — собрано сборщиком, `manual` — введено человеком. */
  obtained_by: string;
}

export interface LevelReason {
  satisfied: string[];
  missing: string[];
  confidence: number;
  evidence_basis: string;
}

export interface RegistryLink {
  url: string;
  kind: string;
  label: string | null;
  status: string;
  verified_at: string | null;
}

/** Точка изменения уровня во времени. */
export interface LevelChangePoint {
  level: string;
  at: string;
}

/** Точка технологии на карте зрелости. */
export interface MaturityPoint {
  id: string;
  name: string;
  kind: string;
  /** Первичный страт: определяет цвет точки. */
  group: string | null;
  groups: string[];
  level: string | null;
  confidence: number | null;
  evidence_basis: string | null;
  /** Внимание: скорость цитирования, отнесённая к медиане своего года.
   *  null — данных нет. */
  attention: number | null;
  /** Измеренная скорость цитирования до нормировки. */
  attention_raw: number | null;
  /** Год подгруппы, по которой нормировано; null — нормировать было нечем. */
  attention_cohort: string | null;
  /** Распространённость: загрузки пакета либо звёзды репозитория. */
  prevalence: number | null;
  first_published: string | null;
  prose_id: string | null;
  history: LevelChangePoint[];
}

/** Артефакт карты зрелости. */
export interface MaturityArtifact {
  /** Момент сборки артефакта в формате ISO. */
  built_at: string;
  /** Версия правила вычисления уровня. */
  rule_version: string;
  levels: string[];
  strata: { code: string; name: string }[];
  points: MaturityPoint[];
  count: number;
  /** Признак устаревания данных. */
  stale: boolean;
}

/** Одно изменение в хронике. */
export interface RegistryChange {
  technology_id: string;
  name: string;
  kind: "level_up" | "level_down" | "added";
  level_before: string | null;
  level_after: string;
  evidence: { type?: string; source?: string }[];
  changed_at: string;
}

/** Сводка состояния реестра. */
export interface RegistryStats {
  built_at: string;
  total: number;
  by_level: Record<string, number>;
  by_kind: Record<string, number>;
  by_stratum: Record<string, number>;
  with_evidence: number;
  with_level: number;
  with_attention: number;
  evidence_total: number;
  freshest_evidence: string | null;
  stale: boolean;
}
