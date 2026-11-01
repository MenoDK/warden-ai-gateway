.DEFAULT_GOAL := help
PY ?= python

help: ## list targets
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-18s %s\n", $$1, $$2}'

install: ## create .venv and install with dev tools
	$(PY) -m venv .venv && .venv/bin/pip install -e '.[dev]'

lint: ## ruff (lint + format check)
	ruff check . && ruff format --check .

typecheck: ## mypy --strict
	mypy

test: ## unit + API tests (no external services)
	pytest -m "not integration"

test-integration: ## needs `docker compose up -d db redis`
	REDIS_URL=redis://localhost:$${REDIS_PORT:-6379}/0 \
	DATABASE_URL=postgresql://ai:$${DB_PASSWORD:-ai}@localhost:$${DB_PORT:-5432}/ai \
	pytest -m integration

check: lint typecheck test ## everything CI runs, minus Docker

up: ## start the full stack
	docker compose up --build

down: ## stop and remove containers (keeps volumes)
	docker compose down

.PHONY: help install lint typecheck test test-integration check up down
