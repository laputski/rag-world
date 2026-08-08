-- STAGE-6 Ф1 (ADR-010): единый реестр технологий RAG в PostgreSQL.
-- Полное описание таблиц — registry/README.md. Порядок создания: сначала enum'ы,
-- затем таблицы и FK, затем индексы. Идемпотентность обеспечивается
-- services/db/migrator.py через таблицу schema_migrations, а не DROP IF EXISTS
-- (схема не должна пересоздаваться на проде).

-- ─── Enum'ы (строгая типизация — основа точного сравнения) ────────────────────
DO $$ BEGIN
    CREATE TYPE technology_kind AS ENUM
        ('paradigm', 'architecture', 'technique', 'tool', 'artifact');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE measurement_group AS ENUM ('A','B','C','D','E','F','G');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE is_future_flag AS ENUM ('true', 'false', 'both');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE link_kind AS ENUM
        ('paper', 'preprint', 'github', 'product', 'venue', 'other');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE link_status AS ENUM ('verified', 'needs_review', 'unresolved');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    -- Типы свидетельств по плану 02 §3.2.
    CREATE TYPE evidence_type AS ENUM (
        'publication',
        'independent_reproduction',
        'repository',
        'build_run',
        'framework_presence',
        'package_downloads',
        'industrial_use',
        'provider_count'
    );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE evidence_basis AS ENUM ('computed', 'manual');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE change_status AS ENUM ('pending', 'approved', 'rejected');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    -- Метрики по плану 03 §4.4. Расширяемо через ALTER TYPE ADD VALUE.
    CREATE TYPE measurement_metric AS ENUM (
        'recall_at_k', 'precision_at_k', 'ndcg', 'mrr',
        'faithfulness', 'answer_correctness', 'attribution_rate',
        'latency_p50_ms', 'latency_p95_ms',
        'token_count', 'index_build_time', 'index_size'
    );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE measurement_origin AS ENUM ('own', 'authors', 'third_party');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE obtained_by AS ENUM ('auto', 'manual');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;


-- ─── technologies: факты о технологии ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS technologies (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    -- aliases хранятся массивом; уникальность проверяется триггером ниже
    -- (alias не может принадлежать двум разным technology_id).
    aliases         TEXT[] NOT NULL DEFAULT '{}',
    kind            technology_kind NOT NULL,
    family          CHAR(1),  -- A..K (семейство rag-taxonomy.md)
    tier            SMALLINT, -- 1/2, только для kind='paradigm'
    -- groups[] — отдельная таблица technology_groups (many-to-many), т.к. ARRAY
    -- внешних ключей через enum неудобен; см. ниже. Альтернатива ARRAY(enum)
    -- отклонена: сложнее JOIN для радара/фильтров.
    is_future       is_future_flag NOT NULL DEFAULT 'false',
    core_idea       TEXT,     -- короткий факт (1–2 предложения), язык-нейтральный
    prose_id        TEXT,     -- связь с локализованной прозой в ui/src/i18n/
    configuration   JSONB NOT NULL DEFAULT '{}'::jsonb,
    -- главное для автоматического сравнения: {"A4": "graph", "C2": "multi_hop_fixed", ...}
    residual        TEXT[] NOT NULL DEFAULT '{}',
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- tier осмыслен только для paradigm
    CONSTRAINT technologies_tier_only_for_paradigm
        CHECK ((kind = 'paradigm' AND tier IS NOT NULL)
               OR (kind <> 'paradigm' AND tier IS NULL)
               OR tier IS NULL),
    CONSTRAINT technologies_tier_range CHECK (tier IS NULL OR tier IN (1, 2))
);

CREATE INDEX IF NOT EXISTS idx_technologies_kind ON technologies (kind);
CREATE INDEX IF NOT EXISTS idx_technologies_family ON technologies (family);
CREATE INDEX IF NOT EXISTS idx_technologies_is_future ON technologies (is_future);
-- GIN-индекс по aliases для быстрого дедупликационного поиска
CREATE INDEX IF NOT EXISTS idx_technologies_aliases ON technologies USING GIN (aliases);
-- GIN по configuration — для фильтрации «все с A4=graph» в матрице сравнения
CREATE INDEX IF NOT EXISTS idx_technologies_configuration
    ON technologies USING GIN (configuration jsonb_path_ops);


-- ─── technology_groups: many-to-many технология ↔ группа измерений ───────────
CREATE TABLE IF NOT EXISTS technology_groups (
    technology_id   TEXT NOT NULL REFERENCES technologies(id) ON DELETE CASCADE,
    group_code      measurement_group NOT NULL,
    PRIMARY KEY (technology_id, group_code)
);

CREATE INDEX IF NOT EXISTS idx_tech_groups_group ON technology_groups (group_code);


-- ─── links: разрешимые источники (1-to-many с technologies) ──────────────────
CREATE TABLE IF NOT EXISTS links (
    id              BIGSERIAL PRIMARY KEY,
    technology_id   TEXT NOT NULL REFERENCES technologies(id) ON DELETE CASCADE,
    url             TEXT NOT NULL,
    kind            link_kind NOT NULL,
    label           TEXT,
    status          link_status NOT NULL DEFAULT 'needs_review',
    verified_at     DATE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Одна запись (technology_id, url) — но один url может быть у нескольких
    -- технологий (общий обзорный paper). Уникальность пары обеспечивается для
    -- устранения точных дублей внутри записи.
    UNIQUE (technology_id, url, kind)
);

CREATE INDEX IF NOT EXISTS idx_links_technology ON links (technology_id);
CREATE INDEX IF NOT EXISTS idx_links_status ON links (status);
CREATE INDEX IF NOT EXISTS idx_links_kind ON links (kind);


-- ─── evidence: свидетельства (append-only) ───────────────────────────────────
-- Запись никогда не обновляется и не удаляется (план 03 §2). Изменение уровня —
-- новое свидетельство + пересчёт → новая запись в maturity_history.
CREATE TABLE IF NOT EXISTS evidence (
    id              BIGSERIAL PRIMARY KEY,
    technology_id   TEXT NOT NULL REFERENCES technologies(id) ON DELETE CASCADE,
    type            evidence_type NOT NULL,
    value           TEXT,
    source          TEXT NOT NULL,  -- разрешимый идентификатор (URL, DOI)
    fetched_at      DATE NOT NULL,
    obtained_by     obtained_by NOT NULL DEFAULT 'manual',
    verified        BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- append-only: триггер запрещает UPDATE/DELETE (см. ниже)
    -- Уникальность: одно и то же свидетельство (тип+источник+значение) не
    -- дублируется для одной технологии.
    UNIQUE (technology_id, type, source, value)
);

CREATE INDEX IF NOT EXISTS idx_evidence_technology ON evidence (technology_id);
CREATE INDEX IF NOT EXISTS idx_evidence_type ON evidence (type);
CREATE INDEX IF NOT EXISTS idx_evidence_verified ON evidence (verified);


-- ─── maturity_history: журнал версий уровня (обеспечивает 02-AC-2) ───────────
-- Каждое вычисление уровня — отдельная строка. Уровень на любую дату
-- воспроизводим выборкой. Заменяет git-воспроизводимость при переходе на БД.
CREATE TABLE IF NOT EXISTS maturity_history (
    id                  BIGSERIAL PRIMARY KEY,
    technology_id       TEXT NOT NULL REFERENCES technologies(id) ON DELETE CASCADE,
    level               TEXT NOT NULL,  -- 'L0'..'L6'
    confidence          REAL NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    evidence_basis      evidence_basis NOT NULL DEFAULT 'computed',
    rule_version        TEXT NOT NULL,
    computed_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- снимок идентификаторов свидетельств, учтённых при вычислении (для аудита)
    evidence_snapshot   JSONB NOT NULL DEFAULT '[]'::jsonb,

    CHECK (level IN ('L0','L1','L2','L3','L4','L5','L6'))
);

CREATE INDEX IF NOT EXISTS idx_maturity_history_tech
    ON maturity_history (technology_id, computed_at DESC);
CREATE INDEX IF NOT EXISTS idx_maturity_history_level
    ON maturity_history (level);
CREATE INDEX IF NOT EXISTS idx_maturity_history_rule
    ON maturity_history (rule_version);


-- ─── measurements: результаты стенда (STAGE-7 Ф10) ──────────────────────────
CREATE TABLE IF NOT EXISTS measurements (
    id              BIGSERIAL PRIMARY KEY,
    technology_id   TEXT NOT NULL REFERENCES technologies(id) ON DELETE CASCADE,
    metric          measurement_metric NOT NULL,
    value           REAL NOT NULL,
    profile_id      TEXT NOT NULL,  -- сравнение только внутри профиля (03-AC-5)
    measured_at     DATE NOT NULL,
    origin          measurement_origin NOT NULL DEFAULT 'own',  -- 03-AC-6
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_measurements_tech
    ON measurements (technology_id, metric, profile_id);
CREATE INDEX IF NOT EXISTS idx_measurements_profile ON measurements (profile_id);
CREATE INDEX IF NOT EXISTS idx_measurements_origin ON measurements (origin);


-- ─── change_queue: очередь утверждения (замена git-MR, FR-7.15) ──────────────
-- Изменения применяются по классам S8: 1=авто, 2=один рецензент, 3=два рецензента.
CREATE TABLE IF NOT EXISTS change_queue (
    id              BIGSERIAL PRIMARY KEY,
    technology_id   TEXT REFERENCES technologies(id) ON DELETE SET NULL,
    -- technology_id может быть NULL для новой записи (создание)
    change_class    SMALLINT NOT NULL CHECK (change_class IN (1, 2, 3)),
    -- payload: JSON описания изменения {table, op, before, after, reason}
    payload         JSONB NOT NULL,
    status          change_status NOT NULL DEFAULT 'pending',
    reviewers       TEXT[] NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at     TIMESTAMPTZ,
    -- кто и когда утвердил/отклонил (последнее решение)
    resolved_by     TEXT
);

CREATE INDEX IF NOT EXISTS idx_change_queue_status ON change_queue (status, change_class);
CREATE INDEX IF NOT EXISTS idx_change_queue_tech ON change_queue (technology_id);


-- ─── schema_migrations: учёт применённых миграций ────────────────────────────
CREATE TABLE IF NOT EXISTS schema_migrations (
    applied_at      TIMESTAMPTZ PRIMARY KEY DEFAULT now(),
    filename        TEXT NOT NULL UNIQUE,
    checksum        TEXT
);


-- ─── Триггеры ─────────────────────────────────────────────────────────────────

-- updated_at для technologies
CREATE OR REPLACE FUNCTION touch_updated_at() RETURNS trigger AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_technologies_touch ON technologies;
CREATE TRIGGER trg_technologies_touch
    BEFORE UPDATE ON technologies
    FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

-- append-only для evidence: запрет UPDATE/DELETE (план 03 §2)
CREATE OR REPLACE FUNCTION enforce_evidence_append_only() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'evidence is append-only (plan 03 §2): row id=% cannot be modified',
        OLD.id;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_evidence_no_update ON evidence;
CREATE TRIGGER trg_evidence_no_update
    BEFORE UPDATE OR DELETE ON evidence
    FOR EACH ROW EXECUTE FUNCTION enforce_evidence_append_only();

-- Уникальность alias: псевдоним не может принадлежать двум технологиям
-- (дедупликация «LightRAG» / «Light-RAG» — критерий AC-6.7, план 02 §4.1).
CREATE OR REPLACE FUNCTION enforce_unique_aliases() RETURNS trigger AS $$
DECLARE
    conflict_id TEXT;
    alias_val   TEXT;
BEGIN
    -- FOREACH безопасен для пустого массива (в отличие от FOR с array_lower,
    -- который падает на NULL для {}). Проверка уникальности alias по всем
    -- технологиям, кроме текущей (дедупликация «LightRAG»/«Light-RAG»).
    FOREACH alias_val IN ARRAY NEW.aliases LOOP
        SELECT id INTO conflict_id FROM technologies
        WHERE alias_val = ANY(aliases) AND id <> NEW.id
        LIMIT 1;
        IF conflict_id IS NOT NULL THEN
            RAISE EXCEPTION 'alias % is already owned by technology id=%', alias_val, conflict_id;
        END IF;
    END LOOP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_technologies_unique_aliases ON technologies;
CREATE TRIGGER trg_technologies_unique_aliases
    BEFORE INSERT OR UPDATE OF aliases ON technologies
    FOR EACH ROW EXECUTE FUNCTION enforce_unique_aliases();
