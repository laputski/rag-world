"""Проверка данных: сторож последней инстанции, у которого не было сторожа.

`check_registry` — единственное, что стоит между сбором и коммитом бота.
Еженедельный проход идёт без человека, а коммит бота не поднимает рабочие
процессы (так устроена площадка), поэтому ни сверка артефактов с реестром, ни
сверка статьи с кодом на этом пути не выполняются. Остаётся эта функция.

До появления этого файла её не проверял никто. Мутационный прогон показал
цену: девять правок подряд отключали её проверки по одной, и весь набор
оставался зелёным. Данные в репозитории чистые, поэтому запуск проверки на них
подтверждал только их чистоту, а не то, что нарушение будет замечено.

Здесь под каждую проверку строится нарушение. Обратная сторона так же важна:
безупречный реестр обязан давать пустой список, иначе сторож начнёт кричать на
верные данные, и его перестанут слушать.
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import validate_data  # noqa: E402

from services.registry import store  # noqa: E402

TODAY = date(2026, 8, 11)


@pytest.fixture
def registry(tmp_path, monkeypatch):
    """Пустой реестр во временном каталоге."""
    for name, path in (
        ("DATA_DIR", tmp_path),
        ("TECHNOLOGIES_DIR", tmp_path / "technologies"),
        ("EVIDENCE_DIR", tmp_path / "evidence"),
        ("METRICS_DIR", tmp_path / "metrics"),
        ("LEVELS_FILE", tmp_path / "levels" / "history.jsonl"),
        ("COLLECTION_LOG", tmp_path / "collection_log.jsonl"),
    ):
        monkeypatch.setattr(store, name, path)
    (tmp_path / "technologies").mkdir(parents=True)
    return tmp_path


def save(**overrides) -> store.Technology:
    """Исправная запись, если не сказано иного."""
    payload = {
        "id": "alpha", "name": "Alpha", "kind": "architecture", "groups": ["A"],
    }
    payload.update(overrides)
    tech = store.Technology(**payload)
    store.save_technology(tech)
    return tech


def write_raw(name: str, payload: dict) -> None:
    """Записать файл в обход схемы: так порча выглядит на диске."""
    (store.TECHNOLOGIES_DIR / name).write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )


def complains_about(fragment: str, problems: list[str]) -> bool:
    return any(fragment in problem for problem in problems)


# ─── Обратная сторона: исправное не должно вызывать жалоб ────────────────────


def test_sound_registry_produces_no_complaints(registry):
    """Сторож, кричащий на верные данные, перестаёт быть сторожем."""
    save(configuration={"A4": "graph", "C1": "graph_traversal"},
         configuration_reviewed=TODAY)
    store.append_evidence([store.Evidence(
        technology_id="alpha", type="publication", value="arXiv:1",
        source="https://arxiv.org/abs/1", fetched_at=TODAY,
        obtained_by="auto", verified=True,
    )])
    store.append_level(store.LevelEntry(
        technology_id="alpha", level="L1", confidence=0.5,
        rule_version="1.0.0", computed_at=TODAY,
    ))
    store.append_metrics([store.MetricPoint(
        technology_id="alpha", metric="citation_velocity", value=1.0,
        measured_at=TODAY, source="https://openalex.org/W1",
    )])

    assert validate_data.check_registry() == []


# ─── Целостность самого реестра ──────────────────────────────────────────────


def test_empty_registry_is_a_violation(registry):
    assert complains_about("the registry is empty", validate_data.check_registry())


def test_unreadable_record_stops_everything(registry):
    write_raw("alpha.json", {"id": "alpha", "имя": "нет такого поля"})
    problems = validate_data.check_registry()
    assert complains_about("does not read against the schema", problems)


def test_identifier_must_follow_the_convention(registry):
    write_raw("Alpha-1.json", {
        "id": "Alpha-1", "name": "Alpha", "kind": "architecture", "groups": ["A"],
    })
    assert complains_about("breaks the convention", validate_data.check_registry())


def test_duplicate_identifier_is_caught(registry):
    save()
    write_raw("alpha_copy.json", {
        "id": "alpha", "name": "Alpha ещё раз", "kind": "architecture", "groups": [],
    })
    assert complains_about("is repeated", validate_data.check_registry())


def test_filename_must_match_the_identifier(registry):
    """Расхождение имени файла с идентификатором раздваивает запись.

    Проверка ссылок обходит реестр и сохраняет записи, сохранение идёт по
    идентификатору. Прежний файл остаётся, появляется новый, и в реестре
    оказываются две записи с одним идентификатором. До этой проверки такое
    состояние проходило молча.
    """
    write_raw("foo.json", {
        "id": "bar", "name": "Bar", "kind": "architecture", "groups": ["A"],
    })
    assert complains_about("does not match the file name",
                           validate_data.check_registry())


def test_split_record_is_reproducible_and_caught(registry):
    """Порча воспроизводится ровно тем действием, каким наступает в проходе."""
    write_raw("foo.json", {
        "id": "bar", "name": "Bar", "kind": "architecture", "groups": ["A"],
    })
    store.save_technology(store.load_technologies()[0])

    assert [t.id for t in store.load_technologies()] == ["bar", "bar"]
    problems = validate_data.check_registry()
    assert complains_about("is repeated", problems)
    assert complains_about("does not match the file name", problems)


def test_half_written_record_is_reported_not_swallowed(registry):
    """Оборванная запись файла обнаруживается чтением.

    Проход можно прервать в любой момент, и файл останется недописанным.
    Проверка обязана не только остановиться, но и назвать файл: разбирать
    отказ автономного прохода придётся по журналу задним числом, а сообщение
    схемы говорит, что не сошлось, и умалчивает, где.
    """
    save()
    (store.TECHNOLOGIES_DIR / "beta.json").write_text(
        '{"id": "beta", "name": "Be', encoding="utf-8"
    )
    problems = validate_data.check_registry()
    assert complains_about("does not parse", problems)
    assert complains_about("beta.json", problems), "отказ обязан называть файл"
    assert complains_about("does not read against the schema", problems)


def test_empty_name_is_a_violation(registry):
    write_raw("alpha.json", {
        "id": "alpha", "name": "   ", "kind": "architecture", "groups": [],
    })
    assert complains_about("the name is empty", validate_data.check_registry())


def test_unknown_stratum_is_a_violation(registry):
    save(groups=["A", "Z"])
    assert complains_about("unknown stratum", validate_data.check_registry())


# ─── Конфигурационное пространство ───────────────────────────────────────────


def test_dimension_outside_the_schema_is_a_violation(registry):
    save(configuration={"Z9": "что угодно"})
    assert complains_about("unknown dimension", validate_data.check_registry())


def test_value_outside_the_schema_is_a_violation(registry):
    save(configuration={"A4": "гиперкуб"})
    assert complains_about("which the schema does not contain", validate_data.check_registry())


def test_configuration_violating_constraints_is_a_violation(registry):
    """Ограничение Φ: графовая топология требует оператора обхода графа."""
    save(configuration={"A4": "graph", "C1": "dense"})
    assert complains_about("the configuration is inadmissible",
                           validate_data.check_registry())


def test_kind_without_configuration_may_not_carry_values(registry):
    """Атака не занимает места в конфигурационном пространстве."""
    kind = sorted(store.KINDS_WITHOUT_CONFIGURATION)[0]
    save(kind=kind, configuration={"A4": "flat"})
    assert complains_about("occupies no place", validate_data.check_registry())


def test_reviewed_record_must_assert_something(registry):
    save(configuration_reviewed=TODAY)
    assert complains_about("asserts neither values",
                           validate_data.check_registry())


# ─── Пометки измерений ───────────────────────────────────────────────────────


def test_dimension_cannot_be_variable_and_inapplicable_at_once(registry):
    save(configuration={"A4": "graph", "C1": "graph_traversal"},
         configuration_variable=["A4"], configuration_inapplicable=["A4"])
    assert complains_about("both", validate_data.check_registry())


def test_variable_dimension_outside_the_schema_is_a_violation(registry):
    save(configuration_variable=["Z9"])
    assert complains_about("the variable dimension", validate_data.check_registry())


def test_variable_dimension_without_a_value_is_a_violation(registry):
    """Пометка говорит, что значение не единственное, а не что его нет."""
    save(configuration_variable=["A4"])
    assert complains_about("is marked variable yet carries no",
                           validate_data.check_registry())


def test_inapplicable_dimension_outside_the_schema_is_a_violation(registry):
    save(configuration_inapplicable=["Z9"])
    assert complains_about("the inapplicable dimension", validate_data.check_registry())


def test_inapplicable_dimension_may_not_carry_a_value(registry):
    """Значение у неприменимого измерения утверждает о несуществующем."""
    save(configuration={"A4": "flat"}, configuration_inapplicable=["A4"])
    assert complains_about("is marked inapplicable yet carries",
                           validate_data.check_registry())


# ─── Остаток отображения ─────────────────────────────────────────────────────


def test_residual_outside_the_vocabulary_is_a_violation(registry):
    """Свободный текст в остатке делает подсчёт повторов бессмысленным."""
    (registry / "residual_vocabulary.json").write_text(
        json.dumps({"mechanisms": [{"id": "known_one"}]}), encoding="utf-8"
    )
    save(residual=["своими словами про рёбра"])
    assert complains_about("is not in the vocabulary", validate_data.check_registry())


def test_residual_from_the_vocabulary_passes(registry):
    (registry / "residual_vocabulary.json").write_text(
        json.dumps({"mechanisms": [{"id": "known_one"}]}), encoding="utf-8"
    )
    save(residual=["known_one"])
    assert validate_data.check_registry() == []


def test_vocabulary_is_read_at_check_time_not_at_import(registry):
    """Проход правит данные и проверяет их в том же запуске.

    Словарь, прочитанный при загрузке модуля, описывал бы состояние до правок,
    и механизм, добавленный этим же проходом, был бы объявлен самоуправством.
    """
    save(residual=["added_during_the_pass"])
    assert complains_about("is not in the vocabulary", validate_data.check_registry())

    (registry / "residual_vocabulary.json").write_text(
        json.dumps({"mechanisms": [{"id": "added_during_the_pass"}]}),
        encoding="utf-8",
    )
    assert validate_data.check_registry() == []


# ─── Источники ───────────────────────────────────────────────────────────────


def test_link_without_an_address_is_a_violation(registry):
    save(links=[store.Link(url="   ", kind="paper")])
    assert complains_about("a source without an address", validate_data.check_registry())


def test_verified_link_must_carry_a_date(registry):
    """Отметка о проверке без даты не даёт узнать, когда ссылку смотрели."""
    save(links=[store.Link(
        url="https://arxiv.org/abs/1", kind="preprint", status="verified",
    )])
    assert complains_about("yet no check date is given",
                           validate_data.check_registry())


# ─── Ссылочная целостность ───────────────────────────────────────────────────


def test_evidence_pointing_at_an_unknown_record(registry):
    save()
    store.append_evidence([store.Evidence(
        technology_id="ghost", type="publication", value=None,
        source="https://arxiv.org/abs/1", fetched_at=TODAY,
        obtained_by="auto", verified=True,
    )])
    assert complains_about("an unknown technology", validate_data.check_registry())


def test_evidence_without_a_source(registry):
    save()
    store.append_evidence([store.Evidence(
        technology_id="alpha", type="publication", value=None,
        source="   ", fetched_at=TODAY, obtained_by="auto", verified=True,
    )])
    assert complains_about("has no source", validate_data.check_registry())


def test_level_entry_pointing_at_an_unknown_record(registry):
    save()
    store.append_level(store.LevelEntry(
        technology_id="ghost", level="L1", confidence=0.5,
        rule_version="1.0.0", computed_at=TODAY,
    ))
    assert complains_about("refers to an unknown technology",
                           validate_data.check_registry())


def test_level_outside_the_scale(registry):
    save()
    store.LEVELS_FILE.parent.mkdir(parents=True, exist_ok=True)
    store.LEVELS_FILE.write_text(json.dumps({
        "technology_id": "alpha", "level": "L9", "confidence": 0.5,
        "rule_version": "1.0.0", "computed_at": TODAY.isoformat(),
        "evidence_snapshot": [], "evidence_basis": "computed",
    }) + "\n", encoding="utf-8")
    assert complains_about("the inadmissible level", validate_data.check_registry())


def test_confidence_outside_the_unit_interval(registry):
    save()
    store.LEVELS_FILE.parent.mkdir(parents=True, exist_ok=True)
    store.LEVELS_FILE.write_text(json.dumps({
        "technology_id": "alpha", "level": "L1", "confidence": 1.7,
        "rule_version": "1.0.0", "computed_at": TODAY.isoformat(),
        "evidence_snapshot": [], "evidence_basis": "computed",
    }) + "\n", encoding="utf-8")
    assert complains_about("lies outside [0, 1]", validate_data.check_registry())


def test_metric_pointing_at_an_unknown_record(registry):
    save()
    store.append_metrics([store.MetricPoint(
        technology_id="ghost", metric="citation_velocity", value=1.0,
        measured_at=TODAY, source="https://openalex.org/W1",
    )])
    assert complains_about("a measurement refers to an unknown",
                           validate_data.check_registry())


def test_metric_without_a_source(registry):
    save()
    store.append_metrics([store.MetricPoint(
        technology_id="alpha", metric="citation_velocity", value=1.0,
        measured_at=TODAY, source="   ",
    )])
    assert complains_about("has no source", validate_data.check_registry())


# ─── Код возврата ────────────────────────────────────────────────────────────
#
# Проверками сборки и целью `make validate` управляет именно он. Нулевой код
# при найденных нарушениях означал бы зелёную сборку на испорченных данных, а
# заметить это можно только чтением вывода, которого никто не читает.


def test_exit_code_is_nonzero_when_something_is_wrong(registry, monkeypatch):
    save(configuration={"A4": "гиперкуб"})
    monkeypatch.setattr(sys, "argv", ["validate_data.py"])
    assert validate_data.main() == 1


def test_exit_code_is_zero_on_sound_data(registry, monkeypatch):
    save()
    monkeypatch.setattr(sys, "argv", ["validate_data.py"])
    assert validate_data.main() == 0
