"""Опубликованные артефакты не должны расходиться с реестром.

Артефакты производны от `data/`, но версионируются намеренно: статический
хостинг собирает только интерфейс и Python не запускает, поэтому без них
опубликованный портал остался бы без данных.

У версионирования производного есть цена — оно может устареть. Этот тест не даёт
устареть: он пересобирает артефакты во временный каталог и сравнивает с теми,
что лежат в репозитории. Расходятся — значит, кто-то правил `data/` и забыл
выполнить сборку.

Момент сборки при сравнении игнорируется: он меняется при каждом запуске и
содержания не несёт.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.build_artifacts import OUT_DIR, build  # noqa: E402

#: Поля, меняющиеся при каждой сборке и потому исключаемые из сравнения.
VOLATILE_KEYS = {"built_at"}

COMPARED = ["registry.json", "map.json", "changes.json", "stats.json"]


def _normalize(payload):
    """Убрать изменчивые поля на всех уровнях структуры."""
    if isinstance(payload, dict):
        return {
            key: _normalize(value)
            for key, value in payload.items()
            if key not in VOLATILE_KEYS
        }
    if isinstance(payload, list):
        return [_normalize(item) for item in payload]
    return payload


def test_published_artifacts_match_registry(tmp_path):
    build(out_dir=tmp_path)

    stale: list[str] = []
    for name in COMPARED:
        published = OUT_DIR / name
        assert published.exists(), (
            f"артефакт {name} отсутствует в репозитории; выполните `make artifacts`"
        )
        expected = _normalize(json.loads((tmp_path / name).read_text(encoding="utf-8")))
        actual = _normalize(json.loads(published.read_text(encoding="utf-8")))
        if expected != actual:
            stale.append(name)

    assert not stale, (
        "опубликованные артефакты разошлись с реестром: "
        + ", ".join(stale)
        + "; выполните `make artifacts` и зафиксируйте результат"
    )


# ─── Поля, которых нет ───────────────────────────────────────────────────────
#
# Поле, пустое у всех записей сразу, выглядит как данные и данными не является.
# Так прожило поле распространённости: артефакт его нёс, интерфейс задавал им
# размер точки, а величины под ним не было ни у одной из шестидесяти двух
# записей. Все точки были одного размера, и заметить это можно было только
# глядя на карту с вопросом «почему они одинаковые».
#
# Обычным тестом такое не ловится: проверка «нет данных значит null» проходит
# вхолостую именно тогда, когда данных нет никогда. Ловится это только счётом
# по всему артефакту, поэтому проверка живёт здесь, рядом со сборкой, и
# смотрит на настоящие данные, а не на выдуманные.

#: Поля, пустые у всех записей на законных основаниях, с причиной у каждого.
ALLOWED_ALL_EMPTY = {
    # Пусто, пока ни одна запись не понижалась и не поднималась: история
    # появляется только при изменении уровня.
}


def _all_empty_fields(items: list[dict]) -> list[str]:
    """Поля, пустые у каждой записи набора."""
    keys: set[str] = set()
    for item in items:
        keys |= set(item)
    empty = []
    for key in sorted(keys):
        values = [item.get(key) for item in items]
        if all(value is None or value == [] or value == {} for value in values):
            empty.append(key)
    return empty


def test_no_field_is_empty_for_every_record():
    """Ни одно поле артефакта не пусто у всех записей сразу."""
    offenders: dict[str, list[str]] = {}
    for name, path in (
        ("map.json", "points"),
        ("registry.json", "technologies"),
    ):
        payload = json.loads((OUT_DIR / name).read_text(encoding="utf-8"))
        items = payload[path] if isinstance(payload, dict) else payload
        dead = [
            key for key in _all_empty_fields(items)
            if key not in ALLOWED_ALL_EMPTY
        ]
        if dead:
            offenders[name] = dead

    assert not offenders, (
        f"поля пусты у всех записей сразу: {offenders}. "
        "Либо величину никто не вычисляет, либо поле лишнее. И то и другое "
        "выглядит на портале как данные, которых нет."
    )


def test_feed_is_published():
    """Лента хроники — единственный способ узнать об изменениях извне портала."""
    feed = OUT_DIR / "feed.xml"
    assert feed.exists(), "лента отсутствует; выполните `make artifacts`"
    text = feed.read_text(encoding="utf-8")
    assert text.lstrip().startswith("<?xml"), "лента не является XML-документом"
    assert "<channel>" in text


def test_residual_codes_are_resolved_to_wording():
    """Данные хранят код механизма, читателю показывается формулировка.

    Разделение существует ради перевода: английская локализация меняет словарь,
    а не пятьдесят четыре записи реестра. Но если подстановка сломается,
    карточка покажет читателю `synonymy_edges`, и заметить это можно будет
    только глазами.
    """
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    vocabulary = json.loads(
        (root / "data" / "residual_vocabulary.json").read_text(encoding="utf-8")
    )
    codes = {m["id"] for m in vocabulary["mechanisms"]}
    wording = {m["ru"] for m in vocabulary["mechanisms"]}

    published = json.loads(
        (root / "ui" / "public" / "data" / "registry.json").read_text(encoding="utf-8")
    )
    seen = 0
    for row in published["technologies"]:
        for item in row.get("residual", []):
            seen += 1
            assert item not in codes, f"в артефакт попал код вместо формулировки: {item}"
            assert item in wording, f"формулировка вне словаря: {item!r}"
    assert seen > 0, "ни одного остатка в артефакте — проверка ничего не проверила"


def test_marked_dimensions_survive_into_the_artifact():
    """Пометки бесполезны, если не доходят до читателя.

    Они существуют, чтобы значение не читалось как утверждение, которым оно не
    является. Потеря их при сборке возвращает ровно ту неправду, ради которой
    поля заводились.
    """
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    published = json.loads(
        (root / "ui" / "public" / "data" / "registry.json").read_text(encoding="utf-8")
    )
    rows = {row["id"]: row for row in published["technologies"]}

    marked = [
        r for r in rows.values()
        if r.get("configuration_variable") or r.get("configuration_inapplicable")
    ]
    assert marked, "ни одной помеченной записи — проверка ничего не проверяет"

    for row in marked:
        for code in row.get("configuration_inapplicable", []):
            assert code not in row["configuration"], (
                f"{row['id']}: неприменимое измерение {code} несёт значение"
            )
        for code in row.get("configuration_variable", []):
            assert code in row["configuration"], (
                f"{row['id']}: переменное измерение {code} без значения"
            )


def test_rejected_names_do_not_return_to_the_registry():
    """Однажды отклонённое имя не заводится заново молча.

    Через полгода имя всплывает снова, никто не помнит, почему его убрали, и
    работа повторяется. Файл отклонений отвечает на вопрос «почему нет», а
    сторож не даёт ответу устареть незаметно: если запись всё-таки нужна, из
    файла её надо убрать осознанно.
    """
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    path = root / "data" / "rejected.jsonl"
    if not path.exists():
        return

    rejected = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        assert row.get("reason", "").strip(), (
            f"{row.get('name')}: отклонение без причины бесполезно"
        )
        if row.get("former_id"):
            rejected[row["former_id"]] = row["reason"]

    present = {p.stem for p in (root / "data" / "technologies").glob("*.json")}
    returned = sorted(rejected.keys() & present)
    assert not returned, (
        "отклонённые записи вернулись в реестр: "
        + ", ".join(f"{i} ({rejected[i][:60]}…)" for i in returned)
    )


def test_parse_notes_agree_with_the_registry():
    """Обоснование, разошедшееся с данными, хуже отсутствующего.

    Оно объясняет значение, которого нет, и делает это убедительно: читатель
    видит связное рассуждение и не догадывается сверить его с реестром.
    """
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root / "scripts"))
    import build_review

    notes = build_review.load_notes()
    if not notes:
        return
    problems = build_review.check(notes)
    assert not problems, "обоснования разошлись с реестром:\n  " + "\n  ".join(problems)


def test_parse_notes_say_both_what_and_why():
    """Разделение существенно: одно проверяется по источнику, другое по схеме.

    Слитая в одну фразу мысль читается как утверждение о технологии, тогда как
    половина её — утверждение о том, как схема эту технологию описывает.
    """
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root / "scripts"))
    import build_review

    for note in build_review.load_notes():
        where = f"{note['technology_id']}.{note.get('code') or note.get('residual')}"
        assert note.get("did", "").strip(), f"{where}: не сказано, что делает система"
        assert note.get("why", "").strip(), f"{where}: не сказано, почему следует значение"
        assert note.get("source", "").strip(), f"{where}: не указан источник"
