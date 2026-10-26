# Makefile for reflex-physical-ai

.PHONY: help sample check test demo lint format clean

help:
	@echo "Available commands:"
	@echo "  make sample   - Run pipeline offline on golden fixtures with uv"
	@echo "  make check    - Run linting, typechecking, and schema validation tests"
	@echo "  make test     - Run full pytest test suite"
	@echo "  make demo     - Run end-to-end demo (requires NEBIUS_API_KEY)"
	@echo "  make clean    - Remove virtualenvs, caches, and build artifacts"

sample:
	cd backend && uv run --extra dev pytest tests/test_schemas.py -v

check:
	cd backend && uv run --extra dev pytest -v

test:
	cd backend && uv run --extra dev pytest tests/ -v

demo:
	cd backend && uv run python -m app.main

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +
	rm -rf backend/.venv frontend/node_modules
