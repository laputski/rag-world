.PHONY: help install install-dev test test-unit test-arch test-v test-ui \
        dev build lint format smoke clean \
        collect update levels artifacts validate sources release \
        release-dry mutate mutate-list

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

sources: ## Regenerate docs/SOURCES.md from the collectors' own constants
	$(PYTHON) scripts/build_sources.py

# Выпуск фиксирует состояние навсегда: ссылка на него уходит в чужую работу, а
# описание подаётся во внешний архив и получает постоянный идентификатор.
# Артефакты пересобираются здесь же, чтобы в снимок не попало вчерашнее: сам
# выпуск это проверит и откажется, но чинить отказ вручную незачем.
release: artifacts ## Cut a dated, immutable snapshot and the deposit package
	$(PYTHON) scripts/make_release.py

release-dry: artifacts ## Show what a release would contain, writing nothing
	$(PYTHON) scripts/make_release.py --dry-run

# ── Quality ──────────────────────────────────────────────────────────────────

# Форматирование не навязывается: в схеме измерений и в каталогах значений
# выравнивание сделано вручную и несёт смысл (таблицу видно глазом), а
# автоформат его разрушает. Проверяются ошибки, а не расстановка пробелов.
smoke: ## Check the deployed portal (needs network)
	$(PYTHON) -m pytest tests/smoke -m network -q

# Мутационный прогон отвечает на вопрос, которого не задаёт покрытие: заметит
# ли кто-нибудь поломку правила. Идёт около двадцати пяти минут, поэтому в
# `make test` не входит и запускается отдельно. Годность самого перечня при
# этом проверяется обычным набором при каждой правке: портится он именно от
# правок кода, а не от времени.
mutate: ## Break each rule in turn and check that some test notices
	$(PYTHON) scripts/mutate.py

mutate-list: ## Show the catalogue of rules the mutation run protects
	$(PYTHON) scripts/mutate.py --list

lint: ## Run ruff checks
	.venv/bin/ruff check core services scripts tests

format: ## Auto-format with ruff (по желанию, не обязательно)
	.venv/bin/ruff format core services scripts tests

clean: ## Remove build artifacts and caches
	rm -rf .venv .pytest_cache .ruff_cache ui/node_modules ui/dist *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
