# =============================================================================
# SocraticAI — Makefile
# Common management commands for development, testing, and operations.
# =============================================================================

.PHONY: help install test test-unit test-integration test-cov lint format run-backend run-frontend verify init-db clean docker-up docker-down

PYTHON ?= uv run python
PYTEST ?= uv run pytest
UVICORN ?= uv run uvicorn
STREAMLIT ?= uv run streamlit
RUFF ?= uv run ruff

help:
	@echo "SocraticAI — Available commands:"
	@echo "  make install           Install development dependencies via uv"
	@echo "  make test              Run the complete pytest test suite (unit + integration)"
	@echo "  make test-unit         Run unit tests only"
	@echo "  make test-integration  Run integration tests only"
	@echo "  make test-cov          Run tests with coverage reporting"
	@echo "  make lint              Lint codebase using ruff"
	@echo "  make format            Format code using ruff"
	@echo "  make run-backend       Run FastAPI backend on port 8000 (hot reload)"
	@echo "  make run-frontend      Run Streamlit frontend on port 8501"
	@echo "  make verify            Run end-to-end subsystem verification"
	@echo "  make init-db           Initialize database tables and schemas"
	@echo "  make clean             Clean temporary files, caches, and build artifacts"
	@echo "  make docker-up         Start backend and frontend services via Docker Compose"
	@echo "  make docker-down       Stop Docker Compose services"

install:
	uv pip install -r requirements-dev.txt

test:
	$(PYTEST)

test-unit:
	$(PYTEST) apps/backend/tests/unit

test-integration:
	$(PYTEST) apps/backend/tests/integration

test-cov:
	$(PYTEST) --cov=apps/backend/app --cov-report=term-missing

lint:
	$(RUFF) check apps/backend/app apps/frontend apps/backend/tests

format:
	$(RUFF) format apps/backend/app apps/frontend apps/backend/tests

run-backend:
	$(UVICORN) app.main:app --host 0.0.0.0 --port 8000 --reload --app-dir apps/backend

run-frontend:
	$(STREAMLIT) run apps/frontend/app.py --server.port 8501 --server.address 0.0.0.0

verify:
	$(PYTHON) scripts/development/e2e_verify.py

init-db:
	$(PYTHON) scripts/migration/init_db.py

clean:
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@rm -rf build dist .coverage htmlcov 2>/dev/null || true

docker-up:
	docker compose up --build

docker-down:
	docker compose down

