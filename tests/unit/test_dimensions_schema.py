"""Тесты стратифицированной схемы измерений и конфигурации.

Покрывает: декларацию двадцати шести измерений, каталог значений, значения по
умолчанию, ограничения Φ (каждое несовместимое сочетание ловится автоматически),
`Configuration` с её устойчивым идентификатором, степень независимости и мёртвые
значения.
"""

import pytest

from core.configuration import Configuration, config_hash
from core.dimensions_schema import (
    ALL_VALUES,
    BY_CODE,
    CONDITIONAL_CODES,
    CONSTRAINTS,
    CORE_CODES,
    DEFAULTS,
    DIMENSIONS,
    SCHEMA_SIZE,
    STRATA,
    dead_values,
    dimensions_of,
    independence_degree,
    is_valid_value,
    validate,
)

# ─── Декларация измерений ────────────────────────────────────────────────────


def test_schema_size_matches_declaration():
    assert len(DIMENSIONS) == SCHEMA_SIZE == 26
    assert len(CORE_CODES) == 21
    assert len(CONDITIONAL_CODES) == 5


def test_all_strata_a_to_g_present():
    groups = {d.group for d in DIMENSIONS}
    assert groups == {"A", "B", "C", "D", "E", "F", "G"}
    assert set(STRATA) == groups


def test_every_stratum_is_named_and_non_empty():
    for code, name in STRATA.items():
        assert name, f"страт {code} без имени"
        assert dimensions_of(code), f"страт {code} без измерений"


def test_stratum_sizes():
    sizes = {code: len(dimensions_of(code)) for code in STRATA}
    assert sizes == {"A": 7, "B": 2, "C": 4, "D": 3, "E": 4, "F": 3, "G": 3}


def test_dimension_codes_are_unique_and_well_formed():
    codes = [d.code for d in DIMENSIONS]
    assert len(codes) == len(set(codes)), "дублирующие коды измерений"
    for code in codes:
        assert code[0] in "ABCDEFG" and code[1:].isdigit(), f"неверный код {code}"


def test_every_dimension_has_nonempty_values_and_default():
    for d in DIMENSIONS:
        assert len(d.values) >= 2, f"{d.code}: нужно не менее двух значений"
        assert d.default in d.values, f"{d.code}: умолчание {d.default!r} не в значениях"


def test_conditional_dimensions_are_exactly_a6_c4_and_f():
    """Условные: A6 (темпоральность), C4 (распределённость), F1–F3 (эволюция)."""
    assert set(CONDITIONAL_CODES) == {"A6", "C4", "F1", "F2", "F3"}


def test_is_valid_value():
    assert is_valid_value("A4", "graph")
    assert not is_valid_value("A4", "nonsense")
    assert not is_valid_value("ZZ", "x")


def test_defaults_match_dimensions():
    for d in DIMENSIONS:
        assert DEFAULTS[d.code] == d.default


# ─── Ограничения Φ ───────────────────────────────────────────────────────────


def test_constraints_are_well_formed():
    valid_kinds = {"requires", "excludes", "implies"}
    for c in CONSTRAINTS:
        assert c.kind in valid_kinds
        assert c.dim_a in BY_CODE and c.dim_b in BY_CODE
        assert c.val_a in ALL_VALUES[c.dim_a]
        assert c.val_b in ALL_VALUES[c.dim_b]
        assert c.reason, "у ограничения должна быть причина"


def test_validate_rejects_unknown_dimension():
    assert any("Неизвестное измерение" in e for e in validate({"ZZ": "x"}))


def test_validate_rejects_invalid_value():
    assert any("не в" in e for e in validate({"A4": "nonsense"}))


def test_validate_accepts_default_configuration():
    assert validate(DEFAULTS) == []


def test_tree_topology_allows_dense_representation():
    """Дерево и векторы совместимы: запрет обобщал свойство одной системы.

    Схема запрещала это сочетание со ссылкой на то, что «Vectorless не
    использует векторы». Не использует их Vectorless, а не древовидный индекс
    вообще: RAPTOR строит дерево рекурсивной кластеризацией представлений и ими
    же ищет. Свойство самой Vectorless выражается значением A5=none.
    """
    cfg = {**DEFAULTS, "A4": "tree", "A5": "dense_single",
           "C1": "tree_navigation", "D1": "none"}
    assert validate(cfg) == [], "допустимое сочетание не должно отвергаться"



def test_phi_cross_encoder_requires_vector_representation():
    cfg = {**DEFAULTS, "A5": "lexical", "D1": "cross_encoder", "C1": "lexical"}
    assert any("cross_encoder требует" in e for e in validate(cfg))


def test_phi_cross_encoder_excludes_non_vector_models():
    for bad in ("none", "lexical", "symbolic"):
        cfg = {**DEFAULTS, "A5": bad, "D1": "cross_encoder"}
        if bad == "lexical":
            cfg["C1"] = "lexical"
        assert any("cross_encoder" in e for e in validate(cfg)), (
            f"A5={bad} должно блокировать cross_encoder"
        )
    for good in ("dense_single", "dense_multi_late_interaction", "vision_language"):
        cfg = {**DEFAULTS, "A5": good, "D1": "cross_encoder"}
        assert not any("cross_encoder" in e for e in validate(cfg)), (
            f"A5={good} не должно блокировать cross_encoder"
        )


def test_graph_topology_with_cross_encoder_is_valid():
    """Графовая архитектура с перекрёстным кодировщиком допустима (стиль PathRAG)."""
    cfg = Configuration(A4="graph", C1="graph_traversal", D1="cross_encoder")
    assert not any("cross_encoder" in e for e in cfg.validate()), cfg.validate()


def test_phi_hypergraph_excludes_path_pruning():
    cfg = {**DEFAULTS, "A4": "hypergraph", "D1": "path_pruning", "C1": "boolean_query"}
    assert any("hypergraph" in e for e in validate(cfg))


def test_phi_graph_requires_graph_traversal():
    cfg = {**DEFAULTS, "A4": "graph", "C1": "ann"}
    assert any("graph traversal" in e for e in validate(cfg))


def test_phi_decoding_reflection_requires_trained_reader():
    """Рефлексия на этапе декодирования требует обученного ридера."""
    cfg = {**DEFAULTS, "E2": "decoding_reflection", "G3": "frozen"}
    assert any("fine-tuned" in e for e in validate(cfg))


def test_phi_agentic_excludes_post_generation_check():
    cfg = {**DEFAULTS, "C2": "agentic_open_loop", "E2": "post_gen_check"}
    assert any("двойной corrective" in e for e in validate(cfg))


def test_phi_multi_hop_requires_graph_topology():
    cfg = {**DEFAULTS, "C2": "multi_hop_fixed", "A4": "flat"}
    assert any("multi_hop" in e for e in validate(cfg))


def test_phi_constraint_count_is_pinned():
    """Число ограничений закреплено: новое Φ обязано приходить со своим тестом."""
    assert len(CONSTRAINTS) == 8, (
        f"Φ содержит {len(CONSTRAINTS)} ограничений; добавьте тест для нового. "
        "Список: " + ", ".join(
            f"{c.dim_a}={c.val_a} {c.kind} {c.dim_b}={c.val_b}" for c in CONSTRAINTS
        )
    )


# ─── Конфигурация ────────────────────────────────────────────────────────────


def test_configuration_defaults_match_schema():
    cfg = Configuration()
    for code, val in DEFAULTS.items():
        assert getattr(cfg, code) == val


def test_configuration_covers_every_dimension():
    keys = set(Configuration().as_dict())
    assert keys == {d.code for d in DIMENSIONS}


def test_configuration_hash_is_stable_and_idempotent():
    cfg = Configuration(A4="graph", C1="graph_traversal", C2="multi_hop_fixed")
    assert cfg.config_hash() == cfg.config_hash()
    assert len(cfg.config_hash()) == 16


def test_configuration_hash_changes_with_value():
    assert Configuration().config_hash() != Configuration(
        A4="graph", C1="graph_traversal"
    ).config_hash()


def test_config_hash_ignores_own_field():
    """Повторное применение к уже помеченной записи даёт тот же результат."""
    payload = Configuration().as_dict()
    first = config_hash(payload)
    assert config_hash({**payload, "config_hash": first}) == first


def test_configuration_validate_uses_phi():
    """Пример берётся из действующих ограничений, а не из отменённого.

    Перекрёстный кодировщик сравнивает представления, поэтому требует, чтобы
    модель представления существовала.
    """
    cfg = Configuration(D1="cross_encoder", A5="none")
    assert cfg.validate() != []
    assert not cfg.is_valid()


def test_configuration_rejects_unknown_field():
    with pytest.raises(Exception):
        Configuration(ZZ="x")


# ─── Свойства схемы ──────────────────────────────────────────────────────────


def test_independence_degree_is_between_zero_and_one():
    deg = independence_degree()
    assert 0.0 < deg <= 1.0, f"степень независимости {deg} вне (0, 1]"
    assert deg < 1.0, "при активных ограничениях степень независимости меньше единицы"


def test_dead_values_returns_valid_pairs():
    for code, value in dead_values():
        assert code in BY_CODE
        assert value in ALL_VALUES[code]
