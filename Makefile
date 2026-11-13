.PHONY: help setup test lint backend demo seed ingest mcp terraform-validate smoke clean

# Default target when running 'make'
.DEFAULT_GOAL := help

PYTHON := uv run python
PYTEST := uv run pytest
UVICORN := uv run uvicorn
RUFF := uv run ruff

help:
	@echo "CloudDesk Support Platform — Available Commands:"
	@echo "  make setup    - Install dependencies and create .env from .env.example"
	@echo "  make test     - Run offline test suite with pytest"
	@echo "  make lint     - Run code quality and style checks using ruff"
	@echo "  make backend  - Run FastAPI server on http://localhost:8000"
	@echo "  make demo     - Run ticket resolution demo workflow in terminal"
	@echo "  make seed     - Load sample fixtures into database (Phase 2)"
	@echo "  make ingest   - Ingest knowledge base articles into vector store (Phase 5)"
	@echo "  make mcp      - Run MCP server for agent tool access (Phase 6)"
	@echo "  make smoke    - Run basic smoke test against running backend"
	@echo "  make clean    - Remove build, cache, and test artifacts"

setup:
	uv sync
	@if [ ! -f .env ]; then cp .env.example .env && echo "Created .env from .env.example"; else echo ".env already exists, skipping copy."; fi

test:
	$(PYTEST) -v

lint:
	$(RUFF) check .

backend:
	$(UVICORN) backend.app.main:app --host 0.0.0.0 --port 8000 --reload

demo:
	$(PYTHON) -m backend.app.demo $(if $(TICKET),--ticket $(TICKET),--ticket CD-1002)

seed:
	@echo "Database seed stub (Active in Phase 2)"

ingest:
	$(PYTHON) -m backend.app.rag.ingest

mcp:
	$(PYTHON) -m integrations.mcp.server

terraform-validate:
	@echo "Validating multi-cloud Terraform roots..."
	@which terraform >/dev/null 2>&1 || { echo "terraform not installed locally, skipping local execution"; exit 0; }
	@for cloud in aws azure gcp; do \
		echo "Validating deployment/$$cloud..."; \
		(cd deployment/$$cloud && terraform fmt -check && terraform init -backend=false && terraform validate) || exit 1; \
	done

smoke:
	@echo "Checking health endpoint at $${BASE_URL:-http://localhost:8000}/health/live"
	@curl -sf $${BASE_URL:-http://localhost:8000}/health/live || echo "Backend server is not running at $${BASE_URL:-http://localhost:8000}"

clean:
	rm -rf .pytest_cache htmlcov .coverage
	find . -type d -name "__pycache__" -exec rm -rf {} +
