"""Пригодность кандидата реестру: детерминированное правило, без языковой модели.

Обнаружение приносит около двадцати работ в неделю, и все они помечены в
каталоге как относящиеся к RAG. Между тем реестр держит **именованные
технологии извлечения**, а большинство находок — применения RAG к предметной
области: восстановление исторических документов, ответы по химической
литературе, экономические модели мира. Читать двадцать аннотаций подряд, чтобы
отделить одно от другого, владелец перестанет на третьей неделе.

Отсюда оценка. Она **не утверждение о работе**, а порядок просмотра очереди:
показывает, на что смотреть сначала. Ровно поэтому она живёт только в очереди
кандидатов и никогда не попадает на карточку технологии: там всё, что портал
говорит, обязано быть проверяемым, а здесь — эвристика.

Признаки названы поимённо и показываются вместе с оценкой. Число без слагаемых
означало бы «поверьте», а портал построен на обратном.

Чего в оценке нет и почему:

* **числа цитирований.** У работы недельной давности оно равно нулю у всех, и
  признак не различает ничего;
* **наличия репозитория.** Каталог это поле не заполняет: из двадцати четырёх
  найденных работ репозиторий указан у нуля. Признак, всегда равный нулю,
  выглядит как данные, не будучи ими.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

#: Метки задач каталога, попадающие в предмет реестра. Список выведен из того,
#: чем каталог действительно помечает работы про RAG, а не из воображения.
CORE_TASKS = frozenset({
    "retrieval",
    "embedding-models",
    "learning-to-rank",
})

#: Метки, соседние предмету: работа может оказаться и архитектурой извлечения,
#: и применением. Сами по себе решают мало.
NEAR_TASKS = frozenset({
    "question-answering",
    "reasoning",
    "summarization",
    "agents",
    "language-modeling",
    # Понимание документов бывает и предметом реестра, и предметом области:
    # восстановление исторических рукописей помечено им же. Одной этой метки
    # мало, чтобы работа считалась работой об извлечении.
    "document-understanding",
})

#: Метки, говорящие о другой области. Признак отрицательный только тогда, когда
#: ядровых меток нет вовсе: работа про извлечение в мультимодальной системе
#: остаётся работой про извлечение.
OFF_TASKS = frozenset({
    "image-restoration",
    "image-understanding",
    "audio-understanding",
    "world-models",
    "reinforcement-learning",
    "instruction-following",
    "coding-agents",
    "speech-recognition",
    "text-to-image",
})

#: Слова, которыми описывают устройство извлечения. Считаются в аннотации:
#: работа про архитектуру говорит об индексе, разбиении, переранжировании, а
#: работа-применение говорит о предметной области.
MECHANISM_WORDS = (
    "retriev", "index", "chunk", "passage", "rerank", "re-rank", "embedding",
    "vector", "corpus", "knowledge graph", "grounding", "context window",
    "query rewrit", "hybrid search", "sparse", "dense", "bm25", "recall@",
)

#: Заголовок вида «LEDGERMIND: Provenance-Constrained…»: имя стоит до
#: двоеточия и коротко. Записи реестра именованы, и своё имя работы — сильный
#: признак того, что она предлагает вещь, а не применяет чужую.
_NAMED = re.compile(r"^\s*([A-Z][\w.\-]{1,24}(?:\s[A-Z][\w.\-]{1,24})?)\s*:")

MAX_SCORE = 10


@dataclass
class Fit:
    """Оценка пригодности и её слагаемые.

    Слагаемые показываются читателю вместе с числом: оценка без них требует
    веры, а её здесь просить не за что.

    Признак записывается кодом и величинами, а не готовой фразой. Причина та
    же, по которой словарь остатков хранит коды: портал двуязычен, и фраза,
    собранная правилом, оказалась бы на одном языке у обоих читателей.
    """

    score: int = 0
    signals: list[dict] = field(default_factory=list)

    def add(self, score: int, code: str, **params: object) -> None:
        self.score += score
        self.signals.append({"code": code, **params})

    def as_dict(self) -> dict:
        return {"score": self.score, "signals": list(self.signals)}


def _task_slugs(tasks: list[dict] | None) -> set[str]:
    return {
        t.get("slug", "") for t in (tasks or []) if isinstance(t, dict)
    } - {""}


def assess(
    *,
    title: str,
    abstract: str,
    tasks: list[dict] | None = None,
    curated_by: list[str] | None = None,
) -> Fit:
    """Оценить пригодность работы реестру по её карточке в каталоге.

    Возвращает целое от нуля до десяти и перечень сработавших признаков.
    Целое, а не дробь: точность здесь мнимая, а десяти ступеней хватает, чтобы
    отсортировать два десятка работ.
    """
    fit = Fit()
    slugs = _task_slugs(tasks)

    # Включение в тематический список — решение человека, разбирающегося в
    # предмете, тогда как метка задачи в каталоге проставлена тем, кто работу
    # выложил. Без этого признака работы, найденные по спискам, получали бы
    # заведомо низкую оценку не по своим свойствам, а по бедности источника:
    # меток задач список не несёт вовсе.
    if curated_by:
        fit.add(2, "curatedList", lists=sorted(curated_by))

    core = sorted(slugs & CORE_TASKS)
    if core:
        fit.add(4, "coreTask", tasks=core)

    near = sorted(slugs & NEAR_TASKS)
    if near:
        fit.add(2, "nearTask", tasks=near)

    if _NAMED.match(title or ""):
        fit.add(2, "named")

    text = (abstract or "").lower()
    hits = sorted({word for word in MECHANISM_WORDS if word in text})
    if len(hits) >= 6:
        fit.add(2, "mechanismStrong", count=len(hits))
    elif len(hits) >= 3:
        fit.add(1, "mechanismWeak", count=len(hits))

    off = sorted(slugs & OFF_TASKS)
    if off and not core:
        fit.add(-3, "offTask", tasks=off)

    fit.score = max(0, min(MAX_SCORE, fit.score))
    return fit
