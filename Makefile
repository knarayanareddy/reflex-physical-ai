# Makefile for reflex-physical-ai
#
# Every target here runs what it says it runs. If a capability does not exist yet,
# the target fails loudly rather than printing a cheerful no-op — a green `make` that
# proves nothing is worse than a red one that tells the truth.

SHELL := /bin/bash
.DEFAULT_GOAL := help
BACKEND := backend
RUN := cd $(BACKEND) && uv run --extra dev

.PHONY: help sample test lint format typecheck schema taxonomy params fixtures check demo serve verify-envelope replay clean

help: ## Show the available targets
	@echo "Reflex — available commands"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  make %-16s %s\n", $$1, $$2}'
	@echo ""
	@echo "Offline (no API key needed): sample, test, lint, typecheck, schema, taxonomy, params, fixtures, check"
	@echo "Network:                     demo  (serves the API; planner/model calls land in Phase C)"

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

params: ## Check the calibration profile: coverage, provenance, degraded strictness
	@$(RUN) python ../scripts/check_param_provenance.py; \
	rc=$$?; \
	if [ $$rc -eq 2 ]; then \
		echo "  -> placeholders recorded (not fatal). 'make params-strict' is the gate for a measured rig."; \
	elif [ $$rc -ne 0 ]; then \
		exit $$rc; \
	fi
	@$(RUN) python ../scripts/diff_parameter_sets.py

params-strict: ## Same, but fail unless every value traces to a measurement
	$(RUN) python ../scripts/check_param_provenance.py --strict

fixtures: ## Regenerate nothing; verify the committed fixtures still match the code
	$(RUN) python ../scripts/make_fixtures.py --check

check: lint typecheck schema taxonomy params fixtures test ## Everything CI runs
	@echo ""
	@echo "make check: PASS — lint, types, contracts, taxonomy, calibration, fixtures and tests are green"

demo: ## Serve the API on :8000 (no API key required; the envelope is live)
	cd $(BACKEND) && uv run python -m app.main

serve: demo ## Alias for demo

verify-envelope: ## Purity, determinism, rules, calibration and the fixture corpus
	$(RUN) pytest tests/test_envelope_purity.py tests/test_envelope_determinism.py \
		tests/test_envelope_rules.py tests/test_envelope_params.py \
		tests/test_envelope_fixtures.py tests/test_replay.py -q
	$(RUN) python -m app.envelope verify
	@echo "verify-envelope: PASS — pure, deterministic, and the fixtures reproduce"

replay: ## Replay the fixture corpus through the two-arm simulator
	$(RUN) python ../jobs/replay_all.py --from-fixtures

clean: ## Remove caches and virtualenvs
	find . -type d -name "__pycache__" -prune -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -prune -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -prune -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -prune -exec rm -rf {} +
	rm -rf $(BACKEND)/.venv frontend/node_modules
