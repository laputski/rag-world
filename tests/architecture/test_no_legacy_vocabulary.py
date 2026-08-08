"""Сторож словаря: устаревшая модель не должна возвращаться в проект.

Прежняя факторизация RAG («семь ортогональных осей») отменена: единственный
контракт — двадцать шесть измерений в семи стратах. Этот тест не даёт словарю
отменённой модели просочиться обратно ни в код, ни в тексты, ни в локализацию.

Правила намеренно точные. Запрещены **идентификаторы** отменённой модели и её
**именные обороты**, но не английское слово `axis` само по себе: оси координат
есть у диаграмм (`xAxis`, `yAxis`), а `d3-axis` — реальная зависимость сборки.
По той же причине не запрещено русское «ось»: у карты зрелости две оси, и
писать о них придётся.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Каталоги, которые не являются исходниками проекта.
SKIP_DIRS = {
    ".git", ".venv", "node_modules", "__pycache__", ".pytest_cache",
    ".ruff_cache", ".idea", ".zcode", ".deepeval", "dist", "build",
    "rag_constructor.egg-info", "rag_world.egg-info",
}

# Файлы, содержимое которых мы не пишем (имена сторонних пакетов и т. п.),
# и сам сторож: он обязан перечислять запрещённое, чтобы его искать.
SKIP_FILES = {"package-lock.json", "package.json", "test_no_legacy_vocabulary.py"}

SUFFIXES = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".md", ".json",
    ".yml", ".yaml", ".sql", ".toml", ".html", ".css",
}

# Идентификаторы отменённой модели: встречаются только в её коде и контрактах.
FORBIDDEN_IDENTIFIERS = (
    "AxisCoordinates",
    "AxesResponse",
    "AXIS_VALUES",
    "AXIS_TO_KIND",
    "AXIS_VALUE_TO_DIMENSIONS",
    "AXES_TO_DIMENSIONS",
    "blocked_axis_values",
    "config_hash_v1",
    "getAxes",
    "preset_coords",
    "pre_retrieval",
)

# Именные обороты отменённой модели на обоих языках.
FORBIDDEN_PHRASES = (
    r"семиосев\w*",
    r"ортогональн\w*",
    r"\b7\s*осей\b",
    r"\bсем[ьи]\s+осей\b",
    r"\b7\s*[- ]?осев\w*",
    r"\b7\s*сло[ёе]в\b",
    r"\bсем[ьи]\s+сло[ёе]в\b",
    r"\bсемисло\w*",
    r"\bос(?:ь|и|ей|ям|ями|ях)\s+конструктора\b",
    r"\bосева\w+\s+модел\w+",
    r"\bseven[- ]ax[ei]s\w*",
    r"\bseven[- ]layer\w*",
    r"\b7[- ]ax[ei]s\w*",
    r"\borthogonal\s+ax[ei]s\b",
)

PATTERN = re.compile(
    "|".join(
        [re.escape(i) for i in FORBIDDEN_IDENTIFIERS] + list(FORBIDDEN_PHRASES)
    ),
    re.IGNORECASE,
)

# Файлы, ожидающие переписывания в следующих фазах. Список обязан только
# сокращаться: тест падает и тогда, когда файл из списка уже чист, чтобы запись
# не осталась висеть после выполнения работы.
PENDING_REWRITE: frozenset[str] = frozenset({
    # Первоисточник наполнения реестра: остаётся как справочный материал,
    # переписывается вместе со следующим пополнением реестра.
    "lat.md/rag-taxonomy.md",
})


def _iter_source_files():
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        if path.name in SKIP_FILES:
            continue
        if path.suffix.lower() not in SUFFIXES and path.name != "Makefile":
            continue
        yield rel, path


def _violations(path: Path) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []
    return [m.group(0) for m in PATTERN.finditer(text)]


def test_legacy_vocabulary_absent_from_project():
    """Ни один файл вне списка ожидающих переписывания не несёт старый словарь."""
    offenders: dict[str, list[str]] = {}
    for rel, path in _iter_source_files():
        key = rel.as_posix()
        if key in PENDING_REWRITE:
            continue
        found = _violations(path)
        if found:
            offenders[key] = sorted(set(found))[:5]
    assert not offenders, (
        "Словарь отменённой модели вернулся в проект:\n"
        + "\n".join(f"  {k}: {', '.join(v)}" for k, v in sorted(offenders.items()))
    )


def test_pending_rewrite_list_only_shrinks():
    """Запись остаётся в списке, только пока файл действительно не переписан."""
    stale = []
    for name in sorted(PENDING_REWRITE):
        path = ROOT / name
        if not path.exists():
            continue  # файл удалён — запись убирается вместе со следующей правкой
        if not _violations(path):
            stale.append(name)
    assert not stale, (
        "Эти файлы уже очищены — уберите их из PENDING_REWRITE:\n  "
        + "\n  ".join(stale)
    )


def test_replacement_model_is_declared():
    """Отменённая модель заменена, а не просто удалена."""
    from core.dimensions_schema import DIMENSIONS, STRATA

    assert len(STRATA) == 7, "ожидается семь стратов"
    assert len(DIMENSIONS) == 26, "ожидается двадцать шесть измерений"
