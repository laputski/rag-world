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
  /** Идентификатор локализованной прозы карточки. */
  prose_id: string | null;
  /**
   * Проза, уложенная в артефакт на обоих языках.
   *
   * Портал берёт тексты из ресурсов локализации, а эти поля существуют ради
   * потребителя выгрузки: реестр, прочитанный без портала, состоял из кодов и
   * уровней без единого предложения о том, что это за технология.
   */
  summary?: string | null;
  summary_en?: string | null;
  description?: string | null;
  description_en?: string | null;
  first_published: string | null;
  /** Значения измерений: главное поле для сравнения технологий. */
  configuration: Record<string, string>;
  /** Механизмы, не выразимые схемой измерений (формулировки из словаря). */
  residual: string[];
  residual_en: string[];
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
  /** Обоснование разбора: почему у измерения такое значение. */
  parse_notes: ParseNote[];
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
  /* Распространённости здесь нет намеренно. Поле существовало и задавало
     размер точки, но величины под ним не было ни у одной записи. Подробности
     и причина, по которой заполнить его нечем, — в scripts/build_artifacts.py
     рядом с ATTENTION_METRIC. */
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

/**
 * Выпуск дайджеста.
 *
 * Порождается шаблоном по данным реестра, без языковой модели: выпуск
 * пересказывает уже вычисленное, и выдумать в нём нечего. Именно поэтому он
 * публикуется без просмотра человеком, в отличие от аннотаций записей.
 *
 * Выпуск не пересобирается: он утверждает, что было верно в день выхода.
 */
export interface DigestIssue {
  issued_at: string;
  /** Начало периода; null — первый выпуск, он охватывает всё. */
  since: string | null;
  text: string;
  /** Тот же выпуск по-английски. Пусто у выпусков, вышедших до локализации. */
  text_en?: string;
  added: DigestMove[];
  promoted: DigestMove[];
  demoted: DigestMove[];
  evidence_added: number;
  evidence_by_type: Record<string, number>;
  links_checked: number;
  links_broken: number;
  by_level: Record<string, number>;
  total: number;
}

export interface DigestMove {
  technology_id: string;
  name: string;
  level_before: string | null;
  level_after: string;
}

/**
 * Обоснование одного решения разбора.
 *
 * Разделено намеренно: `did` проверяется по источнику, `why` — по схеме
 * измерений. Слитые в одну фразу, они читаются как утверждение о технологии,
 * тогда как половина — утверждение о том, как схема её описывает.
 */
export interface ParseNote {
  code?: string;
  residual?: string;
  residual_term?: string | null;
  residual_term_en?: string | null;
  to?: string;
  variable?: boolean;
  inapplicable?: boolean;
  /** Что делает система — проверяется по источнику. */
  did: string;
  did_en?: string;
  /** Почему из этого следует значение — проверяется по схеме. */
  why: string;
  why_en?: string;
  /** Какое значение не подошло и почему. */
  instead?: string;
  instead_en?: string;
  /** Место, где источник допускает другое прочтение. */
  question?: string;
  question_en?: string;
  source: string;
  source_en?: string;
}

/**
 * Механизм, который схема не выражает.
 *
 * Очередь остатков — способ растить схему от наблюдений, а не от воображения.
 * Механизм, который приходится записывать снова и снова, показывает место, где
 * схема мала; встреченный однажды — частность одной работы.
 */
export interface ResidualMechanism {
  id: string;
  term: string;
  term_en: string;
  /** Почему схема этого не выражает. */
  note: string;
  note_en: string;
  count: number;
  technologies: { id: string; name: string }[];
  /** Набрал порог упоминаний и потому предлагается в измерения. */
  candidate: boolean;
}

/**
 * Работа, найденная каталогом и ждущая решения.
 *
 * Кандидат — предположение о технологии, а не технология. Решение «это новая
 * архитектура, а не приложение существующей» принимает человек: правило здесь
 * ошибается, и цена ошибки — запись реестра о том, чего нет.
 */
/**
 * Оценка пригодности кандидата реестру.
 *
 * Порядок просмотра очереди, а не утверждение о работе. Слагаемые показываются
 * вместе с числом: оценка без них требовала бы веры.
 */
export interface CandidateSignal {
  /** Код признака; фраза собирается локализацией. */
  code: string;
  tasks?: string[];
  count?: number;
}

export interface CandidateFit {
  score: number;
  signals: CandidateSignal[];
}

export interface Candidate {
  arxiv_id: string;
  fit: CandidateFit;
  title: string;
  /** Аннотация работы, как её даёт каталог, обрезанная для показа. */
  abstract: string;
  published: string | null;
  source: string;
  citations: number | null;
  repositories: string[];
  found_at: string;
  /** Пусто, пока решение не принято. */
  verdict: string | null;
}
