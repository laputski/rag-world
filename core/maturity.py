"""Детерминированная функция уровня зрелости RAG-технологий (план 02 §3, STAGE-6 Ф2).

Чистая функция: принимает свидетельства, возвращает (уровень, уверенность, basis).
Без языковой модели, без обращений к БД. Запись результата в журнал
maturity_history делает вызывающий код (services/db/repository.py).

Утверждённые решения рецензии:
- **02-1 (двойной путь к L2).** L2 достигается либо по научному пути
  (рецензируемая площадка/независимое воспроизведение), либо по отраслевому
  (документированное промышленное применение). Без отраслевого пути
  Contextual Retrieval (промышленный стандарт без рецензирования) получил бы
  L0/L1 и оказался ниже препринта — прямая инверсия.
- **02-3 (manual для L5/L6).** Достаточные условия L5/L6 не имеют
  машиночитаемого источника, поэтому уровень на их основе помечается
  evidence_basis='manual' и не маскируется под вычисленный.

Шкала порядковая: арифметика над уровнями не определена. Монотонность:
достижение L_k требует выполнения условий всех уровней ниже.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

# Версия правила. Изменение логики → bump версии и пересчёт всех записей
# (план 02 §3.3: обе версии результата сохраняются в maturity_history).
RULE_VERSION = "1.0.0"

# Период актуальности свидетельства по типу (определение 5: «срок с даты получения
# превышает установленный для типа период»). L5/L6-свидетельства актуальны дольше,
# поскольку промышленное применение меняется медленнее библиометрии.
FRESHNESS_DAYS: dict[str, int] = {
    "publication": 365 * 3,           # публикация не устаревает как факт
    "independent_reproduction": 365 * 3,
    "repository": 180,                # активность репозитория — полугодовая
    "build_run": 90,                  # сборка/запуск — квартальная
    "framework_presence": 365,
    "package_downloads": 90,
    "industrial_use": 365 * 2,        # промышленное применение стабильно
    "provider_count": 365 * 2,
}


@dataclass
class EvidenceIn:
    """Входное свидетельство для вычисления уровня (нейтральная структура).

    Поля соответствуют таблице evidence (ADR-010). value и type несут семантику
    класса площадки / факта; см. _venue_class и условия ниже.
    """

    type: str
    source: str
    value: str | None = None
    fetched_at: date | None = None
    verified: bool = False


@dataclass
class MaturityResult:
    level: str            # 'L0'..'L6'
    confidence: float     # 0..1
    evidence_basis: str   # 'computed' | 'manual'
    satisfied: list[str] = field(default_factory=list)   # выполненные уровни
    missing: list[str] = field(default_factory=list)     # невыполненные условия


# ─── Классификация площадки публикации (для L1/L2 научного пути) ──────────────

# Рецензируемые площадки. Список утверждается отдельно (план 02 §3.2: «включённые
# в утверждённый перечень площадок»). value свидетельства типа publication может
# содержать имя площадки или маркер peer_reviewed=true.
PEER_REVIEWED_VENUES: frozenset[str] = frozenset(
    v.lower()
    for v in (
        # Конференции ML/NLP
        "NeurIPS", "ICLR", "ICML", "ACL", "EMNLP", "NAACL", "AAAI",
        "CVPR", "ICCV", "ECCV",
        # Журналы
        "TACL", "JMLR", "Nature", "Nature Communications", "Science",
        # БД/системы
        "VLDB", "PVLDB", "SIGMOD",
        # Прочие рецензируемые
        "ECIR", "CIKM", "WSDM", "KDD",
    )
)


def _venue_class(ev: EvidenceIn) -> str:
    """Класс площадки из value свидетельства publication.

    Возвращает одно из: 'peer_reviewed', 'workshop_preprint', 'blog_talk'.
    value может содержать: имя площадки, маркер 'peer_reviewed=true/false',
    или тип ('arXiv', 'workshop', 'blog').
    """
    val = (ev.value or "").lower()
    if "peer_reviewed=true" in val or "peer_reviewed=true" in val.replace(" ", ""):
        return "peer_reviewed"
    for venue in PEER_REVIEWED_VENUES:
        if venue.lower() in val:
            return "peer_reviewed"
    if any(m in val for m in ("workshop", "arxiv", "preprint", "openreview")):
        return "workshop_preprint"
    return "blog_talk"


# ─── Условия уровней ──────────────────────────────────────────────────────────


def _has_publication(evidence: list[EvidenceIn], min_class: str) -> bool:
    """Есть ли publication с классом площадки не ниже min_class.

    Порядок классов: blog_talk < workshop_preprint < peer_reviewed.
    """
    order = {"blog_talk": 0, "workshop_preprint": 1, "peer_reviewed": 2}
    threshold = order[min_class]
    for ev in evidence:
        if ev.type == "publication":
            if order[_venue_class(ev)] >= threshold:
                return True
    return False


def _has(evidence: list[EvidenceIn], etype: str) -> list[EvidenceIn]:
    return [e for e in evidence if e.type == etype]


def _has_any(evidence: list[EvidenceIn], etype: str) -> bool:
    return any(e.type == etype for e in evidence)


# ─── Свежесть (определение 5) ──────────────────────────────────────────────────


def _is_fresh(ev: EvidenceIn, as_of: date) -> bool:
    """Свидетельство актуально, если не истёк срок для его типа."""
    if ev.fetched_at is None:
        return False  # без даты получения считать устаревшим нельзя → не свежее
    days = FRESHNESS_DAYS.get(ev.type, 365)
    return (as_of - ev.fetched_at) <= timedelta(days=days)


# ─── Главная функция ──────────────────────────────────────────────────────────


def compute_level(
    evidence: list[EvidenceIn],
    *,
    as_of: date | None = None,
) -> MaturityResult:
    """Вычислить уровень зрелости из свидетельств (детерминированно, без LLM).

    Возвращает наибольший уровень, все условия которого выполнены, при
    монотонности (для L_k выполнены условия всех L_<k). Уверенность — доля
    обязательных свежих проверенных свидетельств для достигнутого уровня.

    L5 и L6 помечаются evidence_basis='manual', т.к. их условия
    (промышленное применение, число поставщиков) не имеют машиночитаемого
    источника (02-3).
    """
    as_of = as_of or date.today()
    satisfied: list[str] = ["L0"]  # L0 выполняется всегда (любая технология описана)

    # ── L1: Публикация (препринт/workshop) ──
    l1_ok = _has_publication(evidence, "workshop_preprint")
    if l1_ok:
        satisfied.append("L1")

    # ── L2: Рецензирование — ДВА пути (02-1) ──
    #   (а) научный: публикация в рецензируемой площадке (требует L1 по
    #       монотонности — есть препринт/публикация)
    #   (б) альтернативный путь без L1: независимое воспроизведение
    #       (independent_reproduction) либо документированное промышленное
    #       применение (industrial_use). План 02 §3.1: L2 = «рецензируемая
    #       площадка ЛИБО независимо воспроизведён»; отраслевой путь добавлен
    #       решением 02-1 (Contextual Retrieval без рецензирования).
    peer_reviewed_l2 = _has_publication(evidence, "peer_reviewed")
    independent_l2 = _has_any(evidence, "independent_reproduction")
    industrial_l2 = _has_any(evidence, "industrial_use")
    if peer_reviewed_l2 and "L1" in satisfied:
        satisfied.append("L2")  # научный путь с монотонностью
    elif independent_l2 or industrial_l2:
        satisfied.append("L2")  # альтернативные пути: L2 без L1 (02-1)

    # ── L3: Референсная реализация ──
    # Авторский репозиторий ИЛИ успешная сборка/запуск на стенде.
    l3_ok = _has_any(evidence, "repository") or _has_any(evidence, "build_run")
    if l3_ok and "L2" in satisfied:
        satisfied.append("L3")

    # ── L4: Независимое воспроизведение ──
    # Независимая реализация ИЛИ присутствие во фреймворке ИЛИ загрузки пакета.
    l4_ok = (
        _has_any(evidence, "independent_reproduction")
        or _has_any(evidence, "framework_presence")
        or _has_any(evidence, "package_downloads")
    )
    if l4_ok and "L3" in satisfied:
        satisfied.append("L4")

    # ── L5: Промышленная эксплуатация (manual, 02-3) ──
    # Документированное применение в производственной среде.
    l5_ok = _has_any(evidence, "industrial_use")
    if l5_ok and "L4" in satisfied:
        satisfied.append("L5")

    # ── L6: Отраслевой стандарт (manual, 02-3) ──
    # Реализована независимо ≥3 поставщиками (provider_count).
    l6_ok = _has_any(evidence, "provider_count")
    if l6_ok and "L5" in satisfied:
        satisfied.append("L6")

    level = satisfied[-1]
    basis = "manual" if level in ("L5", "L6") else "computed"
    confidence = _confidence_for(level, evidence, as_of)
    missing = [lv for lv in ("L1", "L2", "L3", "L4", "L5", "L6") if lv not in satisfied]
    return MaturityResult(
        level=level,
        confidence=confidence,
        evidence_basis=basis,
        satisfied=satisfied,
        missing=missing,
    )


def _confidence_for(level: str, evidence: list[EvidenceIn], as_of: date) -> float:
    """Доля обязательных свежих проверенных свидетельств для уровня (определение 5).

    Для L0 (нет требований) уверенность 1.0 (формально). Для L1..L6 — доля типов
    свидетельств, которые «обязательны» для этого уровня и присутствуют свежими и
    проверенными. Обязательные типы определены таблицей плана 02 §3.2.
    """
    if level == "L0":
        return 1.0

    required: list[str]
    if level == "L1":
        required = ["publication"]
    elif level == "L2":
        # L2 по научному пути требует publication(peer_reviewed) либо independent_reproduction;
        # по отраслевому — industrial_use. Для уверенности считаем все три как
        # альтернативные обязательные: учитываем достигнутые.
        required = ["publication", "independent_reproduction", "industrial_use"]
    elif level == "L3":
        required = ["repository", "build_run"]
    elif level == "L4":
        required = ["independent_reproduction", "framework_presence", "package_downloads"]
    elif level == "L5":
        required = ["industrial_use"]
    else:  # L6
        required = ["provider_count"]

    # Для альтернативных условий (несколько типов на один уровень) confidence =
    # отношение выполненных альтернатив к общему числу обязательных, но не ниже
    # доли свежих+проверенных среди присутствующих.
    present_types = {e.type for e in evidence}
    met = [t for t in required if t in present_types]
    if not met:
        return 0.0
    # Уверенность = среднее по met-альтернативам доли (свежих+проверенных / всех этого типа).
    per_alt: list[float] = []
    for t in met:
        of_type = [e for e in evidence if e.type == t]
        if not of_type:
            continue
        good = sum(1 for e in of_type if _is_fresh(e, as_of) and e.verified)
        per_alt.append(good / len(of_type))
    return round(sum(per_alt) / len(per_alt), 3) if per_alt else 0.0
