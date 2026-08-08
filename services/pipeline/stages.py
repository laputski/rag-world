"""Ступени конвейера верификации (STAGE-7 Ф9, план 03 §5).

Направленный рабочий процесс с явными шлюзами (не свободный агентный цикл).
Состояние сохраняется для возобновления прерванных запусков (план 03 §5.1).
LLM применяется только на ступенях извлечения (S3) и привязки (S4); вычисление
уровня (S7) — детерминированная функция без LLM (core/maturity.py).

Ступени:
  S1 — обнаружение (детерминированная: сборщики из Ф8)
  S2 — нормализация и сопоставление (детерминированная: дедуп по id/alias)
  S3 — извлечение утверждений (LLM: из источника → структурированные утверждения)
  S4 — проверка привязки (LLM: утверждение ↔ дословный фрагмент источника)
  S5 — перекрёстная/детерминированная проверка (services/collectors/s5.py, Ф8)
  S6 — непротиворечивость (детерминированная: конфликт с имеющимися)
  S7 — вычисление уровня (core/maturity.py, без LLM)
  S8 — шлюз человеческого утверждения (очередь change_queue, классы 1/2/3)
  S9 — подготовка выпуска (сборка radar.json, журнал изменений)
"""

from __future__ import annotations

from dataclasses import dataclass, field

from services.collectors.base import RawEvidence
from services.collectors.s5 import CheckResult


@dataclass
class Statement:
    """Структурированное утверждение, извлечённое из источника (S3).

    Обязано ссылаться на дословный фрагмент (verbatim) для проверки привязки (S4).
    """

    technology_id: str
    claim: str                  # что заявлено
    metric: str | None = None   # метрика (recall, latency, ...)
    value: str | None = None    # численное значение
    dataset: str | None = None  # набор данных
    baseline: str | None = None # база сравнения
    verbatim: str = ""          # дословный фрагмент источника, подтверждающий claim
    # Результат проверки привязки (S4).
    binding_passed: bool | None = None


@dataclass
class PipelineState:
    """Сохраняемое состояние конвейера для одной технологии/публикации.

    Позволяет возобновить прерванный запуск (план 03 §5.1).
    """

    technology_id: str
    started_at: str = ""
    # Сырые свидетельства после S1.
    raw_evidence: list[RawEvidence] = field(default_factory=list)
    # Результаты детерминированной проверки S5.
    s5_results: list[tuple[RawEvidence, CheckResult]] = field(default_factory=list)
    # Утверждения после S3 (с результатом S4).
    statements: list[Statement] = field(default_factory=list)
    # Конфликты (S6).
    conflicts: list[str] = field(default_factory=list)
    # Текущая ступень.
    current_stage: str = "S1"
    # Ошибки, накопленные по ступеням.
    errors: list[str] = field(default_factory=list)
    # Завершён?
    completed: bool = False


# ─── Классы изменений S8 (план 03 §5.2) ───────────────────────────────────────
# Определяют требуемое число рецензентов (1/2/3) и тип применения (авто/ручное).

CHANGE_CLASS_AUTO = 1            # уточнение метаданных, библиометрия → автоматически
CHANGE_CLASS_ONE_REVIEWER = 2    # новая запись, повышение внутри L0..L3 → 1 рецензент
CHANGE_CLASS_TWO_REVIEWERS = 3   # переход через L3↔L4, любое понижение, смена правила


def classify_change(
    *,
    is_new: bool,
    level_before: str | None,
    level_after: str,
    rule_changed: bool,
) -> int:
    """Определить класс изменения для шлюза S8 (план 03 §5.2).

    Возвращает 1/2/3. Класс определяет: кто утверждает и сколько рецензентов.
    """
    if rule_changed:
        return CHANGE_CLASS_TWO_REVIEWERS
    if is_new:
        # Новая запись: всегда требует одного рецензента (класс 2), независимо от
        # уровня — это новая сущность в реестре, её нужно просмотреть.
        return CHANGE_CLASS_TWO_REVIEWERS
    # Существующая запись: проверяем переход уровня.
    if level_before is None:
        return CHANGE_CLASS_TWO_REVIEWERS
    order = ["L0", "L1", "L2", "L3", "L4", "L5", "L6"]
    if level_before not in order or level_after not in order:
        return CHANGE_CLASS_TWO_REVIEWERS
    bi, ai = order.index(level_before), order.index(level_after)
    # Понижение всегда класс 3.
    if ai < bi:
        return CHANGE_CLASS_TWO_REVIEWERS
    # Переход через границу L3↔L4 (из ≤3 в ≥4) — класс 3.
    if bi <= 3 < ai:
        return CHANGE_CLASS_TWO_REVIEWERS
    # Повышение внутри L0..L3 — класс 2; уточнение без смены уровня — класс 1.
    return CHANGE_CLASS_ONE_REVIEWER if ai > bi else CHANGE_CLASS_AUTO
