# Makefile for reflex-physical-ai

.PHONY: help sample check test demo lint format clean

help:
\t@echo "Available commands:"
\t@echo "  make sample   - Run pipeline offline on golden fixtures (no API key required)"
\t@echo "  make check    - Run linting, typechecking, and schema validation tests"
\t@echo "  make test     - Run full pytest test suite"
\t@echo "  make demo     - Run end-to-end demo (requires NEBIUS_API_KEY)"
\t@echo "  make clean    - Remove virtualenvs, caches, and build artifacts"

sample:
\tcd backend && python3 -m pytest tests/test_schemas.py -v

check:
\tcd backend && python3 -m pytest -v

test:
\tcd backend && python3 -m pytest tests/ -v

demo:
\tcd backend && python3 -m app.main

clean:
\tfind . -type d -name "__pycache__" -exec rm -rf {} +
\tfind . -type d -name ".pytest_cache" -exec rm -rf {} +
\tfind . -type d -name ".ruff_cache" -exec rm -rf {} +
\trm -rf backend/.venv frontend/node_modules
