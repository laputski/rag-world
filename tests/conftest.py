"""Корневой conftest для pytest.

STAGE-7 Ф7: разделение тестов на быстрые (CI) и интеграционные (живые бэкенды).
Unit/architecture/contract-тесты запускаются в CI без внешних хранилищ.
Integration-тесты (tests/integration/) требуют Qdrant/OpenSearch/LLM и
запускаются отдельно (см. Makefile test-integration, если добавлен).

Реестр технологий (registry) и эндпоинты /radar, /registry честно деградируют
без DATABASE_URL (services/db/connection.py): возвращают 503, не падая.
"""

import pytest


# Маркер для integration-тестов (живые бэкенды). CI их не запускает.
def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "integration: требует живых бэкендов (Qdrant/OpenSearch/LLM); "
        "не запускается в CI по умолчанию.",
    )
