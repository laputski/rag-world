"""Общие модели сборщиков свидетельств (STAGE-7 Ф8, план 03 §2).

Сборщики опрашивают источники (arXiv, OpenAlex, GitHub) и возвращают сырые
кандидатные свидетельства в нейтральном формате. Запись в БД (evidence-таблица,
append-only) делает оркестратор, а не сам сборщик — это позволяет тестировать
сборщики без БД и подменять HTTP-клиент.

Ключевые инварианты (план 03):
  - сбор только с перечня разрешённых доменов (allowlist, принцип C4 + мера 5.4.2);
  - свидетельство никогда не перезаписывается (append-only на уровне БД);
  - каждое свидетельство имеет тип, разрешимый источник и дату получения;
  - ступень S5 проверяет свиделиства детерминированно (без LLM).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Protocol

# ─── Allowlist разрешённых доменов (C4 + мера 5.4.2 плана 03) ────────────────
# Сбор с домена вне перечня требует ручного утверждения (план 03 §5.4.2).
# Список расширится (ACL Anthology, OpenReview, DBLP, PyPI, npm) по мере
# реализации соответствующих сборщиков.

ALLOWED_HOSTS: frozenset[str] = frozenset({
    "arxiv.org",
    "export.arxiv.org",
    "api.openalex.org",
    # Идентификатор работы в открытом индексе имеет вид openalex.org/W..., и
    # именно он попадает в поле источника свидетельства.
    "openalex.org",
    "api.github.com",
    "github.com",
    # Разметка курируемых списков берётся сырым файлом, а не страницей:
    # страница несёт оформление площадки, меняющееся независимо от списка.
    "raw.githubusercontent.com",
    "pypi.org",
    # Индекс пакетов не отдаёт число загрузок; его публикует отдельная служба.
    "pypistats.org",
    "aclanthology.org",
    "doi.org",
    # Каталог работ и кода, который ведёт сообщество при Hugging Face после
    # закрытия paperswithcode.com. Даёт площадку публикации вторым источником
    # и ленту работ под меткой метода для обнаружения новых.
    "paperswithcode.co",
    # Площадки, на которые ссылаются свидетельства, введённые человеком:
    # часть рецензируемых публикаций существует только здесь.
    "openreview.net",
    "dl.acm.org",
    "proceedings.neurips.cc",
    "openaccess.thecvf.com",
    "www.nature.com",
    "nature.com",
    "www.anthropic.com",
    "anthropic.com",
})


def is_allowed_host(url: str) -> bool:
    """True, если host URL входит в allowlist (C4)."""
    from urllib.parse import urlparse

    host = urlparse(url).hostname or ""
    host = host.lower()
    if host in ALLOWED_HOSTS:
        return True
    # поддомены разрешённых (api.github.com уже в списке; github.com покрывает raw).
    return any(host == h or host.endswith("." + h) for h in ALLOWED_HOSTS)


# ─── HTTP-клиент: протокол для инъекции (тесты подменяют без сети) ───────────


class HttpGetter(Protocol):
    """Минимальный интерфейс HTTP-клиента для сборщиков.

    Возвращает (status, body_bytes) для URL + headers. В проде — обёртка над
    requests; в тестах — заглушка, возвращающая предзаготовленный ответ.
    """

    def get(
        self, url: str, headers: dict[str, str] | None = None, timeout: int = 20
    ) -> tuple[int, bytes]:
        ...


# ─── Сырое кандидатное свидетельство ─────────────────────────────────────────


@dataclass
class RawEvidence:
    """Кандидатное свидетельство, извлечённое сборщиком.

    Не записывается в БД напрямую: проходит нормализацию (S2), проверку
    привязки (S4), перекрёстную проверку (S5), и только затем запись.
    Здесь — нейтральный формат, общий для всех сборщиков.
    """

    technology_id: str               # к какой технологии относится
    type: str                         # EvidenceType (publication/repository/...)
    value: str                        # содержание (площадка, id, лицензия)
    source: str                       # разрешимый URL
    fetched_at: date                  # дата получения (сегодня, если авто)
    obtained_by: str = "auto"         # auto/manual
    # Дополнительные поля для детерминированных проверок S5:
    verified: bool = False
    # title-поля для проверки совпадения заголовка (S5, та, что нашла 3 ошибки).
    expected_title: str | None = None
    actual_title: str | None = None


@dataclass
class CollectResult:
    """Результат сбора одного источника по одной технологии."""

    source_name: str                  # 'arxiv' | 'openalex' | 'github'
    technology_id: str
    evidence: list[RawEvidence] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    # Свидетельства, не попавшие в evidence (например, домен вне allowlist).
    skipped: list[str] = field(default_factory=list)
