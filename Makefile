# Makefile for reflex-physical-ai
#
# Every target here runs what it says it runs. If a capability does not exist yet,
# the target fails loudly rather than printing a cheerful no-op — a green `make` that
# proves nothing is worse than a red one that tells the truth.

SHELL := /bin/bash
.DEFAULT_GOAL := help
BACKEND := backend
RUN := cd $(BACKEND) && uv run --extra dev
# The Pages export is a runtime job: it needs fastapi and the envelope, not pytest. Using the plain
# environment means a CI job that synced without the dev extra can still build the site.
RUN_RUNTIME := cd $(BACKEND) && uv run

.PHONY: help sample test lint format typecheck schema taxonomy params fixtures check demo demo-check serve \
        verify-envelope replay batch pages-data pages-check build-pages pages-serve record-demo clean

help: ## Show the available targets
	@echo "Reflex — available commands"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  make %-16s %s\n", $$1, $$2}'
	@echo ""
	@echo "Offline (no API key needed): sample, test, lint, typecheck, schema, taxonomy, params, fixtures, check"
	@echo "Demo:                        demo  (10-second simulated session, then API + dashboard on :8000/:5173)"
	@echo "Pages:                       pages-data, build-pages, pages-serve  (GitHub Pages build, no backend)"
	@echo "Video:                       record-demo  (Playwright take of video/script.md, 2:45)"
	@echo "Network:                     nothing here needs it; planner/model calls land in Phase C"

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

demo: ## 10-second offline session: V2 veto, interlock, ledger line, then serve API + dashboard
	$(RUN) python ../jobs/offline_demo.py --serve

demo-check: ## Same session and probes, then exit 0 (for CI; leaves no server running)
	$(RUN) python ../jobs/offline_demo.py --check

serve: ## Serve the API on :8000 and nothing else (no API key required; the envelope is live)
	cd $(BACKEND) && uv run python -m app.main

verify-envelope: ## Purity, determinism, rules, calibration and the fixture corpus
	$(RUN) pytest tests/test_envelope_purity.py tests/test_envelope_determinism.py \
		tests/test_envelope_rules.py tests/test_envelope_params.py \
		tests/test_envelope_fixtures.py tests/test_replay.py -q
	$(RUN) python -m app.envelope verify
	@echo "verify-envelope: PASS — pure, deterministic, and the fixtures reproduce"

replay: ## Replay the fixture corpus through the two-arm simulator
	$(RUN) python ../jobs/replay_all.py --from-fixtures

batch: ## Run the 1,000-action session, write runs/headline_statistics.json and the sandbox pack
	$(RUN) python ../jobs/batch_1000_eval.py

pages-data: ## Record the 10-second demo session as the static replay bundle (no server needed)
	$(RUN_RUNTIME) python ../jobs/export_static_replay.py

pages-check: ## Validate the committed static replay bundle without rewriting it
	$(RUN_RUNTIME) python ../jobs/export_static_replay.py --check

build-pages: pages-data ## Build the GitHub Pages site (base /reflex-physical-ai/) into frontend/dist
	cd frontend && npm run build -- --mode pages
	@echo ""
	@echo "build-pages: PASS — frontend/dist carries the replay bundle; 'make pages-serve' reproduces the sub-path"

pages-serve: ## Serve the Pages build the way Pages does, under /reflex-physical-ai/
	@test -f frontend/dist/index.html || (echo "no build — run 'make build-pages' first" && exit 1)
	node scripts/serve-pages.mjs

record-demo: ## Record the 2:45 demo video from video/script.md into docs/media/ (needs Playwright)
	node scripts/record-demo.ts

clean: ## Remove caches and virtualenvs
	find . -type d -name "__pycache__" -prune -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -prune -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -prune -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -prune -exec rm -rf {} +
	rm -rf $(BACKEND)/.venv frontend/node_modules
