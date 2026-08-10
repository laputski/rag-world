"""Конфигурация RAG в стратифицированном пространстве измерений.

Единственный контракт описания RAG-системы в проекте: точка в пространстве
двадцати шести измерений, сгруппированных по семи стратам A–G
(`core/dimensions_schema.py`). Допустимость конфигурации определяется
ограничениями Φ («требует», «исключает», «подразумевает»), а не списком
исключений в прозе.

Идентификатор конфигурации (`config_hash`) устойчив: одна и та же конфигурация
всегда даёт один и тот же хэш, поэтому записи реестра и результаты сравнения
сопоставимы во времени.
"""

from __future__ import annotations

import hashlib

from pydantic import BaseModel, ConfigDict

from core.dimensions_schema import (
    CONDITIONAL_CODES,
    CORE_CODES,
    DEFAULTS,
    validate,
)


def config_hash(payload: dict[str, str]) -> str:
    """Стабильный SHA256 канонического представления конфигурации.

    Поле `config_hash` исключается из полезной нагрузки, чтобы вычисление было
    идемпотентным при повторном применении к уже помеченной записи.
    """
    clean = {k: v for k, v in payload.items() if k != "config_hash"}
    blob = str(sorted(clean.items())).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]


class Configuration(BaseModel):
    """RAG-конфигурация в пространстве двадцати шести измерений.

    Условные измерения (A6, C4, F1–F3) могут быть не заданы — тогда действует
    значение по умолчанию из `dimensions_schema.DEFAULTS`. Полная конфигурация
    для хэширования включает все измерения с подставленными значениями.
    """

    model_config = ConfigDict(extra="forbid")

    # Поля перечислены явно, чтобы Pydantic знал их типы; значения по умолчанию
    # берутся из dimensions_schema — единственного источника правды о схеме.
    #
    # Перечень приходится править вручную при изменении состава схемы, и это
    # намеренно: молчаливо подхваченное новое измерение появилось бы в хэше
    # конфигурации, не будучи заполненным ни у одной записи. Проверка состава в
    # tests/unit/test_dimensions_schema.py не даст забыть.
    A1: str = DEFAULTS["A1"]
    A2: str = DEFAULTS["A2"]
    A3: str = DEFAULTS["A3"]
    A4: str = DEFAULTS["A4"]
    A5: str = DEFAULTS["A5"]
    A6: str = DEFAULTS["A6"]
    A7: str = DEFAULTS["A7"]
    A8: str = DEFAULTS["A8"]
    B1: str = DEFAULTS["B1"]
    B2: str = DEFAULTS["B2"]
    C1: str = DEFAULTS["C1"]
    C2: str = DEFAULTS["C2"]
    C3: str = DEFAULTS["C3"]
    C4: str = DEFAULTS["C4"]
    D1: str = DEFAULTS["D1"]
    D2: str = DEFAULTS["D2"]
    D3: str = DEFAULTS["D3"]
    E1: str = DEFAULTS["E1"]
    E2: str = DEFAULTS["E2"]
    E3: str = DEFAULTS["E3"]
    E4: str = DEFAULTS["E4"]
    E5: str = DEFAULTS["E5"]
    F1: str = DEFAULTS["F1"]
    F2: str = DEFAULTS["F2"]
    F3: str = DEFAULTS["F3"]
    G1: str = DEFAULTS["G1"]
    G2: str = DEFAULTS["G2"]
    G3: str = DEFAULTS["G3"]

    def as_dict(self) -> dict[str, str]:
        """Все измерения в каноническом порядке (основа хэширования)."""
        return {code: getattr(self, code) for code in CORE_CODES + CONDITIONAL_CODES}

    def config_hash(self) -> str:
        """Стабильный идентификатор конфигурации (16 шестнадцатеричных знаков)."""
        return config_hash(self.as_dict())

    def validate(self) -> list[str]:
        """Ошибки конфигурации (значения и Φ). Пустой список означает допустимость."""
        return validate(self.as_dict())

    def is_valid(self) -> bool:
        return not self.validate()
