"""Выпуск: единственное необратимое действие в проекте.

Всё остальное можно пересобрать. Выпуск нельзя: он фиксирует состояние
навсегда, ссылка на него уходит в чужую работу, а описание из него подаётся во
внешний архив публикаций и получает постоянный идентификатор. Ошибка здесь не
исправляется, она только объясняется.

До появления этого файла выпуск не был покрыт ни одним тестом. Пробы показали
четыре способа выпустить неправду, и все четыре воспроизводились с первого
раза. Здесь под каждый построен случай.
"""

from __future__ import annotations

import json
import sys
import zipfile
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import make_release  # noqa: E402

from services.registry import store  # noqa: E402

TODAY = date(2026, 8, 11)


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    """Реестр, артефакты и каталог выпусков во временном месте."""
    for name, path in (
        ("DATA_DIR", tmp_path / "data"),
        ("TECHNOLOGIES_DIR", tmp_path / "data" / "technologies"),
        ("EVIDENCE_DIR", tmp_path / "data" / "evidence"),
        ("METRICS_DIR", tmp_path / "data" / "metrics"),
        ("LEVELS_FILE", tmp_path / "data" / "levels" / "history.jsonl"),
        ("COLLECTION_LOG", tmp_path / "data" / "collection_log.jsonl"),
    ):
        monkeypatch.setattr(store, name, path)
    (tmp_path / "data" / "technologies").mkdir(parents=True)

    artifacts = tmp_path / "public"
    artifacts.mkdir()
    monkeypatch.setattr(make_release, "ARTIFACTS", artifacts)
    monkeypatch.setattr(make_release, "RELEASES", artifacts / "releases")

    # Записей несколько, и числа выпуска различны намеренно. На реестре из
    # одной записи все они равны нулю или единице, и проверка «число попало в
    # описание» проходит по любой цифре из даты, ничего не проверяя.
    for index, tech_id in enumerate(("alpha", "beta", "gamma")):
        store.save_technology(store.Technology(
            id=tech_id, name=tech_id.title(), kind="architecture", groups=["A"],
            configuration={"A4": "graph", "C1": "graph_traversal"},
            configuration_reviewed=TODAY if index < 2 else None,
        ))
    store.append_evidence([
        store.Evidence(
            technology_id=tech_id, type="publication",
            value=f"arXiv:{number}", source=f"https://arxiv.org/abs/{number}",
            fetched_at=TODAY, obtained_by="auto", verified=True,
        )
        for tech_id, number in (
            ("alpha", 1), ("alpha", 2), ("alpha", 3),
            ("beta", 4), ("beta", 5), ("gamma", 6), ("gamma", 7),
        )
    ])
    store.append_level(store.LevelEntry(
        technology_id="alpha", level="L1", confidence=0.5,
        rule_version="1.0.0", computed_at=TODAY,
    ))
    return tmp_path


def build_artifacts_now() -> None:
    """Собрать артефакты в подменённый каталог, как это делает `make artifacts`."""
    import build_artifacts

    build_artifacts.build(out_dir=make_release.artifacts_dir())


# ─── Что замораживается ──────────────────────────────────────────────────────


def test_release_refuses_stale_artifacts(workspace):
    """Числа выпуска берутся из данных, файлы из артефактов.

    Сверки между ними не было, и расхождение получалось не теоретическое: в
    пробе снимок утверждал шестьдесят две технологии, а лежала в нём одна.
    Такой выпуск нельзя ни исправить, ни отозвать.
    """
    build_artifacts_now()
    store.save_technology(store.Technology(
        id="beta", name="Beta", kind="architecture", groups=["A"],
    ))

    problems = make_release.readiness()
    assert any("собран не из нынешних данных" in p for p in problems), problems
    assert make_release.run(today=TODAY) == 1
    assert not (make_release.releases_dir() / TODAY.isoformat()).exists()


def test_release_refuses_unbuilt_artifacts(workspace):
    problems = make_release.readiness()
    assert any("артефакты не собраны" in p for p in problems), problems
    assert make_release.run(today=TODAY) == 1


def test_release_refuses_broken_data(workspace):
    """Испорченные данные нельзя зафиксировать навсегда.

    Выпуск не звал проверку данных вовсе.
    """
    build_artifacts_now()
    store.save_technology(store.Technology(
        id="alpha", name="Alpha", kind="architecture", groups=["A"],
        configuration={"A4": "гиперкуб"},
    ))
    problems = make_release.readiness()
    assert any("данные не проходят проверку" in p for p in problems), problems
    assert make_release.run(today=TODAY) == 1


def test_snapshot_may_not_promise_a_file_it_lacks(workspace):
    """Отсутствующий файл снимка копировался молча.

    Выпуск при этом перечислял его в своём составе, и ссылка на него вела в
    никуда навсегда.
    """
    build_artifacts_now()
    (make_release.artifacts_dir() / "residuals.json").unlink()

    meta = make_release.build(tag="проба", today=TODAY)
    with pytest.raises(FileNotFoundError, match="снимок неполон"):
        make_release.publish(meta)


# ─── Целостность записи ──────────────────────────────────────────────────────


def test_interrupted_release_does_not_leave_half_of_one(workspace, monkeypatch):
    """Прерывание оставляет черновик, а не полувыпуск.

    Каталог под меткой появляется уже целым, потому что собирается рядом и
    переносится одним движением.
    """
    build_artifacts_now()
    meta = make_release.build(tag=TODAY.isoformat(), today=TODAY)

    def die(*args, **kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(make_release.os, "replace", die)
    with pytest.raises(KeyboardInterrupt):
        make_release.publish(meta)

    target = make_release.releases_dir() / meta["tag"]
    assert not target.exists(), "полувыпуск остался бы навсегда"
    leftovers = [p for p in make_release.releases_dir().iterdir() if p.is_dir()]
    assert leftovers == [], f"черновик не убран: {leftovers}"


def test_incomplete_release_is_reported_not_accepted(workspace):
    """Пустой каталог под меткой не считается выпуском.

    Прежде проверялось существование каталога, поэтому прерванный выпуск
    навсегда оставался пустым: повтор сообщал «уже существует» и уходил,
    архива и описания не создавалось никогда.
    """
    build_artifacts_now()
    (make_release.releases_dir() / TODAY.isoformat()).mkdir(parents=True)

    assert make_release.is_complete(TODAY.isoformat()) is False
    assert make_release.run(today=TODAY) == 1


@pytest.mark.parametrize("part", [
    "release.json", "registry.json", "residuals.json", "архив", "описание",
    "перечень",
])
def test_any_missing_part_makes_the_release_incomplete(workspace, part):
    """Полнота спрашивается у каждой части по отдельности.

    Проверка одной части сходила бы за проверку всех, пока пример был один и
    тот же: пустой каталог не проходит по любому признаку сразу.
    """
    build_artifacts_now()
    tag = TODAY.isoformat()
    make_release.run(today=TODAY)
    assert make_release.is_complete(tag) is True

    releases = make_release.releases_dir()
    if part == "архив":
        (releases / f"rag-world-{tag}.zip").unlink()
    elif part == "описание":
        (releases / f"{tag}-deposit.json").unlink()
    elif part == "перечень":
        (releases / "index.json").write_text(
            json.dumps({"releases": []}), encoding="utf-8"
        )
    else:
        (releases / tag / part).unlink()

    assert make_release.is_complete(tag) is False, (
        f"выпуск без части «{part}» сошёл за полный"
    )


def test_published_release_is_never_rewritten(workspace):
    build_artifacts_now()
    meta = make_release.build(tag=TODAY.isoformat(), today=TODAY)
    make_release.publish(meta)
    with pytest.raises(FileExistsError):
        make_release.publish(meta)


def test_second_run_on_the_same_day_is_harmless(workspace):
    build_artifacts_now()
    assert make_release.run(today=TODAY) == 0
    before = sorted(p.name for p in make_release.releases_dir().iterdir())
    assert make_release.run(today=TODAY) == 0
    assert sorted(p.name for p in make_release.releases_dir().iterdir()) == before


def test_dry_run_writes_nothing(workspace):
    build_artifacts_now()
    assert make_release.run(today=TODAY, dry_run=True) == 0
    assert not make_release.releases_dir().exists()


# ─── Содержание выпуска ──────────────────────────────────────────────────────


def test_release_numbers_match_its_own_files(workspace):
    """Выпуск не должен спорить сам с собой.

    Это же сверяется и на выпущенном снимке: описание для внешнего архива
    строится из тех же чисел и получает постоянный идентификатор.
    """
    build_artifacts_now()
    make_release.run(today=TODAY)

    target = make_release.releases_dir() / TODAY.isoformat()
    meta = json.loads((target / "release.json").read_text(encoding="utf-8"))
    registry = json.loads((target / "registry.json").read_text(encoding="utf-8"))
    rows = registry["technologies"] if isinstance(registry, dict) else registry

    assert meta["technologies"] == len(rows)
    assert meta["evidence"] == sum(r.get("evidence_count", 0) for r in rows)
    assert meta["reviewed"] == sum(1 for r in rows if r.get("configuration_reviewed"))
    assert meta["with_level"] == sum(1 for r in rows if r.get("level"))


def test_bundle_contains_every_file_the_release_promises(workspace):
    build_artifacts_now()
    make_release.run(today=TODAY)

    archive = make_release.releases_dir() / f"rag-world-{TODAY.isoformat()}.zip"
    inside = set(zipfile.ZipFile(archive).namelist())
    assert set(make_release.SNAPSHOT_FILES) <= inside
    assert "release.json" in inside


def test_deposit_description_repeats_the_release_numbers(workspace):
    """Описание уходит во внешний архив и получает постоянный идентификатор.

    Заполнять его руками при каждом выпуске значит однажды ошибиться в числах,
    а числа здесь и есть содержание.
    """
    build_artifacts_now()
    make_release.run(today=TODAY)

    deposit = json.loads(
        (make_release.releases_dir() / f"{TODAY.isoformat()}-deposit.json")
        .read_text(encoding="utf-8")
    )
    meta = json.loads(
        (make_release.releases_dir() / TODAY.isoformat() / "release.json")
        .read_text(encoding="utf-8")
    )
    # Сверяются целые обороты, а не голые числа. Подстрока «3» находится в
    # любой дате, поэтому проверка по ней проходила бы и на описании, где все
    # числа подменены.
    description = deposit["metadata"]["description"]
    for phrase in (
        f"Technologies recorded: {meta['technologies']}",
        f"evidence: {meta['evidence']}",
        f"computed for {meta['with_level']}",
        f"primary sources for {meta['reviewed']}",
    ):
        assert phrase in description, f"в описании нет оборота «{phrase}»"
    assert deposit["metadata"]["version"] == meta["tag"]
    assert deposit["files"] == [f"rag-world-{TODAY.isoformat()}.zip"]


def test_index_lists_the_release_newest_first(workspace):
    build_artifacts_now()
    make_release.publish(make_release.build(tag="2026-08-01", today=date(2026, 8, 1)))
    make_release.publish(make_release.build(tag="2026-08-11", today=TODAY))

    assert [r["tag"] for r in make_release.releases_index()] == [
        "2026-08-11", "2026-08-01",
    ]
