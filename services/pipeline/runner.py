"""Реализация ступеней S2–S8 как чистых/тестируемых функций (STAGE-7 Ф9).

S1 (сбор) и S5 (детерминированная проверка) — в services/collectors/ (Ф8).
Здесь — S2 (нормализация), S3 (LLM-извлечение), S4 (LLM-проверка привязки),
S6 (непротиворечивость), S7 (вычисление уровня), S8 (классификация → очередь).

Каждая ступень принимает состояние и возвращает обновлённое. LLM-ступени (S3/S4)
принимают LlmClient; если он недоступен, ступень записывает ошибку и продолжается
(конвейер не падает — план 03 §5.5: обработка отказов).
"""

from __future__ import annotations

import json
import re
from datetime import date

from services.collectors.base import RawEvidence
from services.llm.client import SYSTEM_EXTRACT, SYSTEM_VERIFY, LlmClient, untrusted_wrap
from services.pipeline.stages import (
    PipelineState,
    Statement,
    classify_change,
)

# ─── S2: нормализация и сопоставление (детерминированная) ────────────────────


def normalize_value(s: str) -> str:
    """Нормализация значения для дедупликации: нижний регистр, удалить пунктуацию."""
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def dedup_evidence(evidence: list[RawEvidence]) -> list[RawEvidence]:
    """S2: убрать дубликаты по нормализованному (type, source, value).

    Запись в evidence-таблице имеет UNIQUE(technology_id, type, source, value),
    но S2 работает до записи — убирает дубли до попадания в S3/S5.
    """
    seen: set[tuple[str, str, str]] = set()
    unique: list[RawEvidence] = []
    for ev in evidence:
        key = (ev.type, ev.source, normalize_value(ev.value or ""))
        if key in seen:
            continue
        seen.add(key)
        unique.append(ev)
    return unique


# ─── S3: извлечение утверждений (LLM) ────────────────────────────────────────


def _parse_statements_json(raw: str) -> list[dict]:
    """Извлечь JSON из ответа LLM (может быть в код-блоке или с пояснениями)."""
    # Найти первый JSON-массив/объект в ответе.
    m = re.search(r"\[.*\]|\{.*\}", raw, re.DOTALL)
    if not m:
        return []
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else [data]


def extract_statements(
    technology_id: str,
    source_text: str,
    *,
    llm: LlmClient,
    today: date | None = None,
) -> list[Statement]:
    """S3: извлечь структурированные утверждения из текста источника через LLM.

    Каждое утверждение обязано иметь verbatim (дословный фрагмент). LLM-ответ
    парсится как JSON: [{claim, metric, value, dataset, baseline, verbatim}].
    """
    today = today or date.today()
    user_prompt = (
        f"Технология: {technology_id}\n"
        f"Извлеки утверждения из следующего источника. Для каждого укажи claim "
        f"(что заявлено), metric, value, dataset, baseline и verbatim — дословную "
        f"цитату из источника, подтверждающую claim. Формат: JSON-массив.\n\n"
        f"{untrusted_wrap(source_text)}"
    )
    raw = llm.chat(SYSTEM_EXTRACT, user_prompt)
    parsed = _parse_statements_json(raw)
    statements: list[Statement] = []
    for item in parsed:
        if not isinstance(item, dict) or "claim" not in item:
            continue
        statements.append(Statement(
            technology_id=technology_id,
            claim=str(item.get("claim", "")),
            metric=item.get("metric"),
            value=item.get("value"),
            dataset=item.get("dataset"),
            baseline=item.get("baseline"),
            verbatim=str(item.get("verbatim", "")),
        ))
    return statements


# ─── S4: проверка привязки (LLM) ─────────────────────────────────────────────


def verify_binding(statement: Statement, source_text: str, *, llm: LlmClient) -> bool:
    """S4: проверить, что statement.verbatim действительно присутствует в источнике.

    Решение 03-5: согласие LLM — слабое свидетельство (не независимая проверка).
    Детерминированная проверка (verbatim в source_text) — сильнее; используем её,
    а LLM — как дополнение для парафраз. Здесь — сначала детерминированная.
    """
    # Детерминированная проверка: verbatim (нормализованный) входит в source_text.
    if statement.verbatim:
        norm_verbatim = normalize_value(statement.verbatim)
        norm_source = normalize_value(source_text)
        if norm_verbatim and norm_verbatim in norm_source:
            return True
    # LLM как дополнение (парафраза). Менее надёжно (03-5), но помогает.
    if llm.is_available:
        user_prompt = (
            f"Утверждение: {statement.claim}\n"
            f"Цитата (verbatim): {statement.verbatim}\n"
            f"Поддерживается ли утверждение этой цитатой? Ответ: "
            f'{{"binding": true|false, "reason": "..."}}.\n\n'
            f"{untrusted_wrap(source_text)}"
        )
        raw = llm.chat(SYSTEM_VERIFY, user_prompt)
        m = re.search(r'"binding"\s*:\s*(true|false)', raw, re.I)
        if m:
            return m.group(1).lower() == "true"
    return False


# ─── S6: непротиворечивость (детерминированная) ──────────────────────────────


def check_consistency(
    new_statements: list[Statement],
    existing_value: str | None,
) -> list[str]:
    """S6: выявить противоречия новых утверждений с существующими.

    Противоречие: новое (metric, dataset) с тем же ключом, но разным value.
    Возвращает список описаний конфликтов. Понижение уровня по конфликту
    требует ручного подтверждения (план 03 §5.2 S6).
    """
    conflicts: list[str] = []
    if not existing_value:
        return conflicts
    # Грубая проверка: если новое value для той же metric+dataset отличается.
    for st in new_statements:
        if st.metric and st.dataset and st.value:
            # Простая эвристика: если existing содержит тот же metric с другим value.
            metric_in_existing = re.search(
                rf"{re.escape(st.metric)}=([0-9.]+)", existing_value
            )
            if metric_in_existing and metric_in_existing.group(1) != str(st.value):
                conflicts.append(
                    f"конфликт {st.metric}: существующее={metric_in_existing.group(1)}, "
                    f"новое={st.value} (dataset={st.dataset})"
                )
    return conflicts


# ─── S7: вычисление уровня (без LLM, core/maturity.py) ───────────────────────


def compute_maturity_level(
    technology_id: str,
    evidence: list[RawEvidence],
    *,
    today: date | None = None,
) -> tuple[str, float, str]:
    """S7: применить детерминированную функцию уровня (core/maturity.py).

    Возвращает (level, confidence, evidence_basis). БЕЗ LLM (план 03 §5.1).
    """
    from core.maturity import EvidenceIn, compute_level

    today = today or date.today()
    evidence_in = [
        EvidenceIn(
            type=e.type,
            source=e.source,
            value=e.value,
            fetched_at=e.fetched_at,
            verified=e.verified,
        )
        for e in evidence
    ]
    result = compute_level(evidence_in, as_of=today)
    return result.level, result.confidence, result.evidence_basis


# ─── S8: классификация и постановка в очередь (детерминированная) ────────────


@staticmethod
def _static_placeholder() -> None:  # pragma: no cover
    ...


def enqueue_change(
    *,
    technology_id: str,
    is_new: bool,
    level_before: str | None,
    level_after: str,
    rule_changed: bool,
    payload: dict,
) -> int:
    """S8: классифицировать изменение и вернуть его класс (1/2/3).

    Записи здесь больше нет. Раньше функция вставляла строку в таблицу
    `change_queue` работавшей рядом базы; база удалена вместе с серверным
    API, а очередью изменений стал журнал уровней `data/levels/history.jsonl`,
    который дописывается при изменении уровня и разбирается шлюзом
    `scripts/classify_changes.py`.

    Классификация оставлена: она чистая, покрыта тестами и нужна ступени
    независимо от того, куда пишется результат.
    """
    return classify_change(
        is_new=is_new,
        level_before=level_before,
        level_after=level_after,
        rule_changed=rule_changed,
    )


def run_pipeline(
    state: PipelineState,
    *,
    source_text: str,
    existing_value: str | None,
    level_before: str | None,
    llm: LlmClient,
    today: date | None = None,
) -> PipelineState:
    """Прогнать S2→S8 для одной технологии. Возвращает обновлённое состояние.

    S1 (сбор) выполняется вне run_pipeline (оркестратором Ф8); сюда приходят
    уже собранные raw_evidence. S5 выполнен в Ф8 (s5_results); S7 использует
    прошедшие S5 свидетельства.
    """
    today = today or date.today()
    state.current_stage = "S2"

    # S2: дедуп.
    passed_evidence = [
        ev for ev, res in state.s5_results if res.passed
    ]
    state.raw_evidence = dedup_evidence(passed_evidence)
    state.current_stage = "S3"

    # S3/S4: LLM-извлечение утверждений и проверка привязки. Если LLM недоступен —
    # пропускаем (конвейер не падает; утверждения не извлекаются, но уровень
    # вычисляется по свидетельствам S5).
    if llm.is_available and source_text:
        try:
            statements = extract_statements(
                state.technology_id, source_text, llm=llm, today=today
            )
            for st in statements:
                st.binding_passed = verify_binding(st, source_text, llm=llm)
            state.statements = statements
        except Exception as exc:  # pragma: no cover
            state.errors.append(f"S3/S4: {exc}")
    state.current_stage = "S6"

    # S6: непротиворечивость.
    bound = [s for s in state.statements if s.binding_passed]
    state.conflicts = check_consistency(bound, existing_value)
    state.current_stage = "S7"

    # S7: вычисление уровня (без LLM).
    level_after, confidence, basis = compute_maturity_level(
        state.technology_id, state.raw_evidence, today=today
    )
    state.current_stage = "S8"

    # S8: классификация и постановка в очередь. payload описывает изменение.
    payload = {
        "level_before": level_before,
        "level_after": level_after,
        "confidence": confidence,
        "evidence_basis": basis,
        "n_evidence": len(state.raw_evidence),
        "n_statements": len(state.statements),
        "conflicts": state.conflicts,
    }
    try:
        change_class = enqueue_change(
            technology_id=state.technology_id,
            is_new=level_before is None,
            level_before=level_before,
            level_after=level_after,
            rule_changed=False,
            payload=payload,
        )
        state.current_stage = f"S8(enqueued,class={change_class})"
    except Exception as exc:  # pragma: no cover
        state.errors.append(f"S8: {exc}")
        state.current_stage = "S8(failed)"

    state.completed = True
    return state
