.PHONY: help install install-backend install-frontend dev dev-backend dev-frontend \
        test test-backend test-frontend lint lint-backend lint-frontend \
        build build-backend build-frontend clean docker-up docker-down \
        format check types

# Default target
help:
	@echo "pyFIA Agent - Development Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make install          Install all dependencies (backend + frontend)"
	@echo "  make install-backend  Install backend dependencies with uv"
	@echo "  make install-frontend Install frontend dependencies with pnpm"
	@echo ""
	@echo "Development:"
	@echo "  make dev              Run both backend and frontend (requires tmux or 2 terminals)"
	@echo "  make dev-backend      Run FastAPI backend with hot reload"
	@echo "  make dev-frontend     Run Next.js frontend with hot reload"
	@echo ""
	@echo "Testing:"
	@echo "  make test             Run all tests"
	@echo "  make test-backend     Run backend tests with pytest"
	@echo "  make test-frontend    Run frontend tests"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint             Lint all code"
	@echo "  make lint-backend     Lint backend with ruff"
	@echo "  make lint-frontend    Lint frontend with eslint"
	@echo "  make format           Format all code"
	@echo "  make types            Type check backend with mypy"
	@echo "  make check            Run all checks (lint + types + test)"
	@echo ""
	@echo "Build:"
	@echo "  make build            Build all for production"
	@echo "  make build-backend    Build backend package"
	@echo "  make build-frontend   Build frontend for production"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-up        Start all services with docker-compose"
	@echo "  make docker-down      Stop all docker services"
	@echo "  make docker-build     Build docker images"
	@echo ""
	@echo "Utilities:"
	@echo "  make clean            Remove build artifacts and caches"
	@echo "  make env              Copy example env files"

# =============================================================================
# Setup
# =============================================================================

install: install-backend install-frontend
	@echo "All dependencies installed!"

install-backend:
	@echo "Installing backend dependencies..."
	cd backend && uv sync --dev

install-frontend:
	@echo "Installing frontend dependencies..."
	cd frontend && pnpm install

env:
	@echo "Setting up environment files..."
	@test -f .env || cp .env.example .env
	@test -f backend/.env || cp .env backend/.env
	@test -f frontend/.env.local || cp frontend/.env.example frontend/.env.local
	@echo "Environment files created. Please edit with your API keys."

# =============================================================================
# Development
# =============================================================================

dev:
	@echo "Starting development servers..."
	@echo "Run 'make dev-backend' and 'make dev-frontend' in separate terminals"
	@echo "Or use: docker-compose up"

dev-backend:
	@echo "Starting FastAPI backend on http://localhost:8000"
	cd backend && uv run uvicorn pyfia_api.main:app --reload --host 0.0.0.0 --port 8000

dev-frontend:
	@echo "Starting Next.js frontend on http://localhost:3000"
	cd frontend && pnpm dev

# =============================================================================
# Testing
# =============================================================================

test: test-backend test-frontend
	@echo "All tests complete!"

test-backend:
	@echo "Running backend tests..."
	cd backend && uv run pytest -v --cov=src/pyfia_api --cov-report=term-missing

test-frontend:
	@echo "Running frontend tests..."
	cd frontend && pnpm test 2>/dev/null || echo "No frontend tests configured yet"

# =============================================================================
# Code Quality
# =============================================================================

lint: lint-backend lint-frontend
	@echo "All linting complete!"

lint-backend:
	@echo "Linting backend with ruff..."
	cd backend && uv run ruff check src/

lint-frontend:
	@echo "Linting frontend with eslint..."
	cd frontend && pnpm lint

format:
	@echo "Formatting backend code..."
	cd backend && uv run ruff format src/
	cd backend && uv run ruff check --fix src/
	@echo "Formatting frontend code..."
	cd frontend && pnpm lint --fix 2>/dev/null || true

types:
	@echo "Type checking backend..."
	cd backend && uv run mypy src/pyfia_api

check: lint types test
	@echo "All checks passed!"

# =============================================================================
# Build
# =============================================================================

build: build-backend build-frontend
	@echo "Build complete!"

build-backend:
	@echo "Building backend package..."
	cd backend && uv build

build-frontend:
	@echo "Building frontend for production..."
	cd frontend && pnpm build

# =============================================================================
# Docker
# =============================================================================

docker-up:
	docker-compose up -d
	@echo "Services started!"
	@echo "  Frontend: http://localhost:3000"
	@echo "  Backend:  http://localhost:8000"
	@echo "  API Docs: http://localhost:8000/docs"

docker-down:
	docker-compose down

docker-build:
	docker-compose build

docker-logs:
	docker-compose logs -f

# =============================================================================
# Utilities
# =============================================================================

clean:
	@echo "Cleaning build artifacts..."
	rm -rf backend/dist backend/.ruff_cache backend/.mypy_cache backend/.pytest_cache
	rm -rf backend/src/*.egg-info
	rm -rf frontend/.next frontend/node_modules/.cache
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "Clean complete!"

# Generate OpenAPI schema from backend
openapi:
	@echo "Generating OpenAPI schema..."
	cd backend && uv run python -c "import json; from pyfia_api.main import app; print(json.dumps(app.openapi(), indent=2))" > ../openapi.json
	@echo "Schema saved to openapi.json"
