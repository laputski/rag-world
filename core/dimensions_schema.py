"""Стратифицированное конфигурационное пространство: 26 измерений и ограничения Φ.

Декларативное описание схемы, на которой держится весь проект: произвольная
система RAG представляется точкой этого пространства. Измерения сгруппированы в
семь стратов A–G (представление знаний, формулировка запроса, извлечение,
формирование контекста, синтез и контроль, эволюция состояния, оболочка
ограничений).

Модуль предметно-нейтрален: только структура пространства, никаких адаптеров и
бэкендов. Значения — устойчивые ASCII-коды; читаемые человеком подписи живут в
локализации интерфейса.

Каждое измерение несёт код (A1..G3), имя, упорядоченный список значений, признак
ядрового или условного и охраняющее условие для условных. Ограничения Φ бывают
трёх видов:
  requires — значение требует другого значения (графовая топология требует
             обхода графа);
  excludes — значение исключает другое (древесная топология без векторов
             исключает плотную модель представления);
  implies  — значение влечёт значение другого измерения по умолчанию.

Связанность решений выражена этими ограничениями явно: недопустимые сочетания
обнаруживает функция validate(), а не список исключений в прозе.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Dimension:
    code: str            # A1..G3
    name: str            # человекочитаемое имя (RU)
    values: tuple[str, ...]
    core: bool = True    # Я — ядро, определено всегда; У — условное
    guard: str = ""      # охраняющее условие для условных измерений
    # Значение по умолчанию: применяется, когда измерение не задано явно.
    default: str = ""

    @property
    def group(self) -> str:
        return self.code[0]


@dataclass(frozen=True)
class Constraint:
    """Ограничение Φ между значениями измерений.

    kind:
      'requires' — (dim_a, val_a) требует, чтобы в config было (dim_b, val_b).
                   Если (dim_a,val_a) присутствует, а (dim_b) отсутствует или
                   отличается — ошибка.
      'excludes' — (dim_a, val_a) и (dim_b, val_b) не могут встречаться вместе.
      'implies'  — синоним requires, применяемый как значение по умолчанию при
                   достройке неполной конфигурации.
    """

    kind: str
    dim_a: str
    val_a: str
    dim_b: str
    val_b: str
    reason: str = ""


# ─── 22 измерения по плану 01 §3 ──────────────────────────────────────────────

DIMENSIONS: tuple[Dimension, ...] = (
    # Группа A — Представление знаний
    Dimension("A1", "Единица извлечения",
              ("passage", "proposition", "entity", "node_edge",
               "page_image", "table_row", "summary_node"), default="passage"),
    Dimension("A2", "Сегментация",
              ("fixed", "structure_aware", "late_chunking", "semantic", "none"),
              default="fixed"),
    Dimension("A3", "Обогащение единицы",
              ("none", "context_prefix", "summary", "extracted_triples", "metadata"),
              default="none"),
    Dimension("A4", "Топология индекса",
              ("flat", "tree", "graph", "hypergraph", "community_hierarchy"),
              default="flat"),
    Dimension("A5", "Модель представления",
              ("lexical", "dense_single", "dense_multi_late_interaction",
               "symbolic", "vision_language", "none"),
              default="dense_single"),
    Dimension("A6", "Темпоральность",
              ("snapshot", "append_only", "bitemporal"),
              core=False, guard="определено при F1≠none (эволюция состояния)",
              default="snapshot"),
    Dimension("A7", "Модальность",
              ("text", "image", "table", "audio", "scene_3d"), default="text"),

    # Группа B — Формулировка и маршрутизация запроса
    Dimension("B1", "Преобразование запроса",
              ("identity", "hyde", "multi_reformulation", "step_back",
               "subquestion_decomposition"), default="identity"),
    Dimension("B2", "Маршрутизация",
              ("static", "trained_classifier", "llm_router", "cost_aware_policy"),
              default="static"),

    # Группа C — Извлечение
    Dimension("C1", "Оператор поиска",
              ("ann", "lexical", "graph_traversal", "boolean_query",
               "tree_navigation", "spatial_range"), default="ann"),
    Dimension("C2", "Управление обходом",
              ("single_shot", "multi_hop_fixed", "iterative_stopping",
               "agentic_open_loop"), default="single_shot"),
    Dimension("C3", "Слияние источников",
              ("none", "rrf", "score_normalization", "learned_fusion"),
              default="none"),
    Dimension("C4", "Распределённость",
              ("single_store", "multiple_local", "federation"),
              core=False, guard="определено при нескольких источниках",
              default="single_store"),

    # Группа D — Формирование контекста
    Dimension("D1", "Переранжирование",
              ("none", "cross_encoder", "graph_structural", "set_cover",
               "path_pruning"), default="cross_encoder"),
    Dimension("D2", "Отбор и сжатие",
              ("top_k", "budget_aware", "abstractive_compression",
               "latent_compression"), default="top_k"),
    Dimension("D3", "Компоновка",
              ("natural_order", "reliability_ascending", "hierarchical"),
              default="natural_order"),

    # Группа E — Синтез и контроль
    Dimension("E1", "Режим генерации",
              ("single_pass", "draft_verify", "ensemble_fragments",
               "multi_agent"), default="single_pass"),
    Dimension("E2", "Контроль обоснованности",
              ("none", "pre_gen_grounding", "post_gen_check",
               "decoding_reflection", "decoding_trigger", "external_judge"),
              default="none"),
    Dimension("E3", "Атрибуция",
              ("none", "document_level", "fragment_level", "claim_level"),
              default="none"),
    Dimension("E4", "Политика отказа",
              ("no_refusal", "confidence_threshold", "domain_policy"),
              default="no_refusal"),

    # Группа F — Эволюция состояния (все условные)
    Dimension("F1", "Запись обратно",
              ("none", "episodic", "consolidating"),
              core=False, guard="определено для систем с памятью", default="none"),
    Dimension("F2", "Разрешение противоречий",
              ("none", "by_time", "by_authority", "explicit_reconciliation"),
              core=False, guard="определено при F1≠none", default="none"),
    Dimension("F3", "Забывание",
              ("none", "by_ttl", "by_significance_decay"),
              core=False, guard="определено при F1≠none", default="none"),

    # Группа G — Оболочка ограничений (G1/G3 влияют на поведение — ADR-007, 01-6)
    Dimension("G1", "Приватность",
              ("open", "isolated_circuit", "differential_privacy", "tee"),
              default="open"),
    Dimension("G2", "Место исполнения",
              ("server", "edge_device", "mixed"), default="server"),
    Dimension("G3", "Обучаемость компонентов",
              ("frozen", "trained_retriever", "trained_reader", "joint_training"),
              default="frozen"),
)

# Состав схемы: A1–A7 = 7, B1–B2 = 2, C1–C4 = 4, D1–D3 = 3, E1–E4 = 4,
# F1–F3 = 3, G1–G3 = 3, всего 26 измерений, из них условных пять: A6, C4, F1–F3.
# Число зафиксировано проверкой, чтобы изменение состава было осознанным: правка
# схемы требует одновременного обновления научного текста и данных реестра.
SCHEMA_SIZE = 26
_n = len(DIMENSIONS)
assert _n == SCHEMA_SIZE, f"ожидалось {SCHEMA_SIZE} измерений, определено {_n}"

# Быстрый доступ по коду.
BY_CODE: dict[str, Dimension] = {d.code: d for d in DIMENSIONS}
CORE_CODES: tuple[str, ...] = tuple(d.code for d in DIMENSIONS if d.core)
CONDITIONAL_CODES: tuple[str, ...] = tuple(d.code for d in DIMENSIONS if not d.core)
ALL_VALUES: dict[str, tuple[str, ...]] = {d.code: d.values for d in DIMENSIONS}
DEFAULTS: dict[str, str] = {d.code: d.default for d in DIMENSIONS}


# ─── Ограничения Φ ───────────────────────────────────────────────────────────
# Каждое несовместимое или требующее сочетание значений описано здесь явно и
# проверяется автоматически. Список пополняется по мере появления архитектур,
# обнажающих новую несовместимость.

CONSTRAINTS: tuple[Constraint, ...] = (
    # Ограничения «дерево исключает векторы» здесь были и сняты: они обобщали
    # свойство одной системы на всё значение. Не использует векторы Vectorless,
    # а не древовидный индекс вообще — RAPTOR строит дерево рекурсивной
    # кластеризацией представлений и ими же ищет. Свойство самой Vectorless
    # выражается значением A5=none и отдельного запрета не требует.
    #
    # Урок общий: несовместимость записывается сюда, только если она следует из
    # устройства значений, а не из того, что первая встреченная система такого
    # сочетания не имела.
    # cross_encoder несовместим с невекторными моделями (none, lexical, symbolic).
    # dense_single/multi/vision_language допустимы — cross_encoder работает по любому
    # векторному входу. Это разрешает graph store + cross_encoder (PathRAG-стиль),
    # где rerank применяется поверх графовых результатов.
    Constraint("excludes", "D1", "cross_encoder", "A5", "none",
               reason="cross_encoder требует векторного входа (не none)"),
    Constraint("excludes", "D1", "cross_encoder", "A5", "lexical",
               reason="cross_encoder требует векторного входа (не lexical)"),
    Constraint("excludes", "D1", "cross_encoder", "A5", "symbolic",
               reason="cross_encoder требует векторного входа (не symbolic)"),
    # 2. hypergraph store + path_pruning несовместимы (OG-RAG использует set_cover).
    Constraint("excludes", "A4", "hypergraph", "D1", "path_pruning",
               reason="hypergraph ontology использует set_cover, не path-pruning"),
    # 3. graph store требует graph_traversal как оператор поиска (требует, не исключает).
    # Ограничение «граф требует обхода» здесь было и снято: оно тоже обобщало
    # одну реализацию на всё значение. Граф можно не обходить шаг за шагом, а
    # запрашивать языком запросов графовой базы — так устроен Unified RAG, и
    # это обычная практика, а не исключение. Второй раз подряд ограничение
    # заставляло приписывать записи значение, которого в источнике нет.
    # 4. self_rag_tokens (decoding_reflection) требует fine-tuned модели (G3≠frozen).
    Constraint("requires", "E2", "decoding_reflection", "G3", "trained_reader",
               reason="reflection tokens требуют fine-tuned LLM (lat.md §4)"),
    # 5. agentic traversal + crag_evaluator — двойной corrective-слой (предупредить).
    #    Формализуем как excludes (избыточно по lat.md §4).
    Constraint("excludes", "C2", "agentic_open_loop", "E2", "post_gen_check",
               reason="agentic + post-gen check — двойной corrective-слой (§4)"),
    # 6. iterative/agentic traversal требуют не-single_shot — encoded в C2 значениях.
    #    multi_hop требует graph/topology (обход осмыслен только по графу/дереву).
    Constraint("requires", "C2", "multi_hop_fixed", "A4", "graph",
               reason="multi_hop осмыслен только над графом"),
)


# ─── API для проверки конфигурации ────────────────────────────────────────────


def is_valid_value(code: str, value: str) -> bool:
    return value in ALL_VALUES.get(code, ())


def validate(config: dict[str, str]) -> list[str]:
    """Вернуть список ошибок конфигурации (пустой = допустима).

    Проверяет: (1) каждое значение принадлежит измерению; (2) ни одно requires/
    excludes-ограничение не нарушено. Условные измерения могут отсутствовать
    (охраняющее условие не выполнено) — это не ошибка.
    """
    errors: list[str] = []

    # (1) Значения в каталоге.
    for code, value in config.items():
        if code not in BY_CODE:
            errors.append(f"Неизвестное измерение {code!r}")
            continue
        if not is_valid_value(code, value):
            errors.append(
                f"Измерение {code}: {value!r} не в {ALL_VALUES[code]}"
            )

    # (2) Ограничения Φ.
    for c in CONSTRAINTS:
        a_val = config.get(c.dim_a)
        b_val = config.get(c.dim_b)
        if a_val != c.val_a:
            continue  # ограничение неактивно (условие-источник не выполнено)
        if c.kind == "excludes":
            if b_val == c.val_b:
                errors.append(
                    f"{c.dim_a}={c.val_a} исключает {c.dim_b}={c.val_b}: {c.reason}"
                )
        elif c.kind == "requires":
            # requires: если b-измерение задано, оно должно совпадать; если не задано
            # — это не ошибка для условных, но ошибка для ядровых (которые обязаны
            # присутствовать в полной конфигурации). Здесь проверяем только конфликт.
            if b_val is not None and b_val != c.val_b:
                errors.append(
                    f"{c.dim_a}={c.val_a} требует {c.dim_b}={c.val_b}, "
                    f"получено {c.dim_b}={b_val!r}: {c.reason}"
                )
    return errors


def independence_degree() -> float:
    """Степень независимости схемы (определение 6 плана 01) — аппроксимация.

    Точное вычисление требует перебора ~10^14 конфигураций (21 ядровое измерение),
    что неисполнимо. Используется локальная аппроксимация: доля пар
    (значение, значение) из разных измерений, которые не запрещены excludes-Φ,
    среди всех возможных пар. Величина описательная; **не** использовать как
    показатель «улучшения» между версиями схемы (замечание 01-8) — при дроблении
    измерения на два степень растёт, хотя предметная область не изменилась.
    """
    # Все пары значений из РАЗНЫХ измерений (ядровых).
    excludes_pairs: set[tuple[str, str, str, str]] = {
        (c.dim_a, c.val_a, c.dim_b, c.val_b) for c in CONSTRAINTS if c.kind == "excludes"
    }
    core_dims = [d for d in DIMENSIONS if d.core]
    total_pairs = 0
    forbidden_pairs = 0
    for i, di in enumerate(core_dims):
        for dj in core_dims[i + 1:]:
            for vi in di.values:
                for vj in dj.values:
                    total_pairs += 1
                    if (di.code, vi, dj.code, vj) in excludes_pairs or (
                        dj.code, vj, di.code, vi
                    ) in excludes_pairs:
                        forbidden_pairs += 1
    if total_pairs == 0:
        return 1.0
    return round(1.0 - forbidden_pairs / total_pairs, 4)


def dead_values() -> list[tuple[str, str]]:
    """Мёртвые значения: недостижимые ни в одной допустимой конфигурации.

    Полный перебор ~10^14 конфигураций неисполним, поэтому используется
    локальный анализ: значение считается мёртвым, если оно состоит в excludes-
    ограничении, запрещающем его вместе со ВСЕМИ значениями другого измерения,
    ИЛИ в requires-ограничении, требующем значение, которого нет в каталоге.
    Это нижняя оценка (могут быть и более тонкие случаи мёртвости, но они
    требуют разрешения системы ограничений — выходит за рамки Ф3).
    """
    dead: list[tuple[str, str]] = []
    for d in DIMENSIONS:
        if not d.core:
            continue
        for v in d.values:
            if _is_locally_dead(d.code, v):
                dead.append((d.code, v))
    return dead


def _is_locally_dead(code: str, value: str) -> bool:
    """Локальная проверка мёртвости значения по excludes/requires."""
    # requires: требует значение, отсутствующее в каталоге → мёртвое.
    for c in CONSTRAINTS:
        if c.kind == "requires" and c.dim_a == code and c.val_a == value:
            if c.val_b not in ALL_VALUES.get(c.dim_b, ()):
                return True
        # excludes: запрещает со всеми значениями другого измерения.
        if c.kind == "excludes" and c.dim_a == code and c.val_a == value:
            other = BY_CODE.get(c.dim_b)
            if other and len(other.values) == 1 and c.val_b == other.values[0]:
                return True
    return False


# ─── Страты ──────────────────────────────────────────────────────────────────

STRATA: dict[str, str] = {
    "A": "Представление знаний",
    "B": "Формулировка и маршрутизация запроса",
    "C": "Извлечение",
    "D": "Формирование контекста",
    "E": "Синтез и контроль",
    "F": "Эволюция состояния",
    "G": "Оболочка ограничений",
}


def dimensions_of(stratum: str) -> tuple[Dimension, ...]:
    """Измерения одного страта в порядке объявления."""
    return tuple(d for d in DIMENSIONS if d.group == stratum)
