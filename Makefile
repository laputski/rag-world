.PHONY: help install install-dev test test-unit test-arch test-v test-ui \
        dev build lint format smoke clean \
        collect update levels artifacts validate sources release \
        release-dry mutate mutate-list

# The tools are invoked as modules through the interpreter itself rather than
# through the launchers in .venv/bin. A launcher carries the path to the
# environment in its first line, so renaming the project directory breaks it in
# silence: `make test` fails with "no such file" while the environment is right
# where it was. Calling the interpreter does not depend on that path and
# survives a rename.
PYTHON ?= .venv/bin/python
PIP    ?= .venv/bin/pip
PYTEST ?= $(PYTHON) -m pytest

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
# One entry point for a person and for the schedule: the unattended run invokes
# exactly these targets, so moving to automation requires no change to the code.

# One entry point, used by a person and by the schedule alike, so what the
# unattended run does matches what a local run does by construction.
collect: ## Full update pass: collect, recompute, rebuild, validate, log the run
	$(PYTHON) scripts/update.py

update: collect ## Alias for `collect`

levels: ## Recompute maturity levels from stored evidence
	$(PYTHON) scripts/compute_levels.py

artifacts: ## Rebuild public/data/*.json and the changes feed
	$(PYTHON) scripts/build_artifacts.py

icons: ## Rebuild favicon, device icon and link preview image from the logo
	$(PYTHON) scripts/build_icons.py

validate: ## Validate registry data: schema, link resolvability, provenance
	$(PYTHON) scripts/validate_data.py

sources: ## Regenerate docs/SOURCES.md from the collectors' own constants
	$(PYTHON) scripts/build_sources.py

# A release fixes a state for ever: a link to it goes into somebody else's work,
# and its description is deposited in an external archive and receives a
# permanent identifier. The artefacts are rebuilt right here so that yesterday's
# state does not enter the snapshot: the release would catch that and refuse, but
# there is no reason to repair the refusal by hand.
release: artifacts ## Cut a dated, immutable snapshot and the deposit package
	$(PYTHON) scripts/make_release.py

release-dry: artifacts ## Show what a release would contain, writing nothing
	$(PYTHON) scripts/make_release.py --dry-run

# ── Quality ──────────────────────────────────────────────────────────────────

# Formatting is not imposed: in the dimension schema and in the value catalogues
# the alignment is done by hand and carries meaning, because it makes the table
# visible to the eye, and an automatic formatter destroys it. What is checked is
# errors, not the placement of spaces.
smoke: ## Check the deployed portal (needs network)
	$(PYTHON) -m pytest tests/smoke -m network -q

# The mutation run answers the question coverage does not ask: would anyone
# notice if a rule broke. It takes about twenty-five minutes, so it stays out of
# `make test` and is run separately. The soundness of the catalogue itself is
# checked by the ordinary suite on every edit: it is edits to the code that spoil
# it, not the passage of time.
mutate: ## Break each rule in turn and check that some test notices
	$(PYTHON) scripts/mutate.py

mutate-list: ## Show the catalogue of rules the mutation run protects
	$(PYTHON) scripts/mutate.py --list

lint: ## Run ruff checks
	$(PYTHON) -m ruff check core services scripts tests

format: ## Auto-format with ruff (optional, never required)
	$(PYTHON) -m ruff format core services scripts tests

clean: ## Remove build artifacts and caches
	rm -rf .venv .pytest_cache .ruff_cache ui/node_modules ui/dist *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
