.PHONY: help install install-dev test test-unit test-arch test-v test-ui \
        dev build lint format clean \
        collect update levels artifacts validate \
        db-migrate db-migrate-pending

PYTHON ?= .venv/bin/python
PIP    ?= .venv/bin/pip
PYTEST ?= .venv/bin/pytest

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

# ── Setup ────────────────────────────────────────────────────────────────────

install: ## Create venv + install runtime deps
	python3 -m venv .venv
	$(PIP) install -e .

install-dev: install ## Install runtime + dev deps (pytest, ruff)
	$(PIP) install -e ".[dev]"

# ── Tests ────────────────────────────────────────────────────────────────────

test: ## Run all Python tests
	$(PYTEST) tests/ -q

test-unit: ## Run unit tests only
	$(PYTEST) tests/unit -q

test-arch: ## Run architecture fitness tests
	$(PYTEST) tests/architecture -q

test-v: ## Run all tests verbosely
	$(PYTEST) tests/ -v

test-ui: ## Run UI tests (Vitest) — requires `npm install` in ui/
	cd ui && npm test

# ── Portal ───────────────────────────────────────────────────────────────────

dev: ## Start the portal dev server on :5174
	cd ui && npm run dev

build: ## Build the static portal into ui/dist
	cd ui && npm ci && npm run build

# ── Data pipeline ────────────────────────────────────────────────────────────
# Единая точка входа для человека и для расписания: автономный режим вызывает
# ровно эти цели, поэтому переход к автоматике не требует правок кода.

# Одна точка входа: ею пользуется и человек, и расписание, поэтому поведение
# автономного прогона совпадает с локальным по построению.
collect: ## Full update pass: collect, recompute, rebuild, validate, log the run
	$(PYTHON) scripts/update.py

update: collect ## Alias for `collect`

levels: ## Recompute maturity levels from stored evidence
	$(PYTHON) scripts/compute_levels.py

artifacts: ## Rebuild public/data/*.json and the changes feed
	$(PYTHON) scripts/build_artifacts.py

validate: ## Validate registry data: schema, link resolvability, provenance
	$(PYTHON) scripts/validate_data.py

# ── Quality ──────────────────────────────────────────────────────────────────

# Форматирование не навязывается: в схеме измерений и в каталогах значений
# выравнивание сделано вручную и несёт смысл (таблицу видно глазом), а
# автоформат его разрушает. Проверяются ошибки, а не расстановка пробелов.
lint: ## Run ruff checks
	.venv/bin/ruff check core services scripts tests

format: ## Auto-format with ruff (по желанию, не обязательно)
	.venv/bin/ruff format core services scripts tests

clean: ## Remove build artifacts and caches
	rm -rf .venv .pytest_cache .ruff_cache ui/node_modules ui/dist *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

# ── Registry database (локальная разработка) ─────────────────────────────────
# Реестр продакшена живёт в data/ под управлением git. PostgreSQL остаётся
# только для разовой миграции и локальных экспериментов; DATABASE_URL в .env.

db-migrate: ## Apply registry DB migrations (idempotent)
	$(PYTHON) -m services.db.migrator

db-migrate-pending: ## Show pending migrations without applying
	$(PYTHON) -m services.db.migrator --pending
