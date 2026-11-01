.DEFAULT_GOAL := help
PY ?= python3
# Use the virtualenv made by `make install` when it exists (CI has none and uses what is on PATH).
BIN := $(wildcard .venv/bin/)
API_PORT ?= 8000
DEV_COMPOSE := docker compose -f docker-compose.yml -f compose.dev.yml

help: ## list targets
	@grep -E '^[a-z0-9-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-18s %s\n", $$1, $$2}'

demo: ## build and start everything with the lab on, then print the address
	LAB_MODE=true SITE_DIR=/app/site docker compose up --build --wait --detach
	@echo ""
	@echo "  Ready: http://localhost:$(API_PORT)   (sign in to the lab with the key it pre-fills)"
	@echo "  Stop:  make down      Start from nothing: make reset"

down: ## stop the stack (keeps the database volume)
	docker compose --profile e2e down --remove-orphans

reset: ## stop the stack and delete its database volume
	docker compose --profile e2e down --volumes --remove-orphans

logs: ## follow the API logs
	docker compose logs -f api

install: ## create .venv and install with dev tools
	$(PY) -m venv .venv && .venv/bin/pip install -e '.[dev]'

lint: ## ruff (lint + format check)
	$(BIN)ruff check . && $(BIN)ruff format --check .

typecheck: ## mypy --strict
	$(BIN)mypy

test: ## unit + API tests (no external services)
	$(BIN)pytest -m "not integration"

test-integration: ## starts PostgreSQL+pgvector and Redis on loopback, then runs the integration tests
	$(DEV_COMPOSE) up -d --wait db redis
	REDIS_URL=redis://localhost:$${REDIS_PORT:-16379}/0 \
	DATABASE_URL=postgresql://ai:$${DB_PASSWORD:-ai}@localhost:$${DB_PORT:-15432}/ai \
	$(BIN)pytest -m integration

check: lint typecheck test ## everything CI runs before the browser tests, minus Docker

transcripts: ## re-record site/transcripts.js from the running code (a test fails if it drifts)
	$(BIN)python scripts/record_transcripts.py

e2e: ## browser tests (Playwright in a container) against the demo, accessibility scans included
	LAB_MODE=true SITE_DIR=/app/site E2E_USER=$$(id -u):$$(id -g) docker compose --profile e2e run --build --rm e2e

.PHONY: help demo down reset logs install lint typecheck test test-integration check transcripts e2e
