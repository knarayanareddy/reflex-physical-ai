# Makefile for reflex-physical-ai
#
# Every target here runs what it says it runs. If a capability does not exist yet,
# the target fails loudly rather than printing a cheerful no-op — a green `make` that
# proves nothing is worse than a red one that tells the truth.

SHELL := /bin/bash
.DEFAULT_GOAL := help
BACKEND := backend
RUN := cd $(BACKEND) && uv run --extra dev

.PHONY: help sample test lint format typecheck schema taxonomy check demo serve verify-envelope clean

help: ## Show the available targets
	@echo "Reflex — available commands"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  make %-16s %s\n", $$1, $$2}'
	@echo ""
	@echo "Offline (no API key needed): sample, test, lint, typecheck, schema, taxonomy, check"
	@echo "Network:                     demo  (serves the API; model calls land in Phase B)"

sample: ## Run the offline contract + fixture checks (no API key, no network)
	$(RUN) pytest tests/test_schema_meta.py tests/test_schema_laws.py tests/test_ledger.py -q

test: ## Run the full test suite
	$(RUN) pytest tests/ -q

lint: ## Lint with ruff (check + format check)
	$(RUN) ruff check app tests ../scripts
	$(RUN) ruff format --check app tests ../scripts

format: ## Auto-fix lint findings and format the code
	$(RUN) ruff check --fix app tests ../scripts
	$(RUN) ruff format app tests ../scripts

typecheck: ## Type-check the application package
	$(RUN) mypy app

schema: ## Validate the frozen contracts and every $ref
	$(RUN) python ../scripts/validate_schema.py

taxonomy: ## Validate rule structure and degraded-mode strictness
	$(RUN) python ../scripts/validate_taxonomy.py --allow-placeholders --allow-missing-fixtures

check: lint typecheck schema taxonomy test ## Everything CI runs
	@echo ""
	@echo "make check: PASS — lint, types, contracts, taxonomy and tests are green"

demo: ## Serve the API on :8000 (no API key required; envelope is not implemented yet)
	cd $(BACKEND) && uv run python -m app.main

serve: demo ## Alias for demo

verify-envelope: ## Purity + determinism proof for the envelope (SPEC §10) — Phase B
	@if [ -d "$(BACKEND)/app/envelope" ]; then \
		$(RUN) pytest tests/test_envelope_purity.py tests/test_envelope_determinism.py -q && echo "verify-envelope: PASS"; \
	else \
		echo "verify-envelope: NOT IMPLEMENTED"; \
		echo "  The deterministic envelope (V1-V10) has not been written yet."; \
		echo "  This target will run the purity and 500-replay determinism tests once it exists."; \
		echo "  See REVIEW.md (R-08) and docs/DECISIONS.md."; \
		exit 1; \
	fi

clean: ## Remove caches and virtualenvs
	find . -type d -name "__pycache__" -prune -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -prune -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -prune -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -prune -exec rm -rf {} +
	rm -rf $(BACKEND)/.venv frontend/node_modules
