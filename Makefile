.PHONY: up down build migrate dev scheduler run test fmt logs

PROJECT = bruno

up:
	docker compose -p $(PROJECT) up -d --build

down:
	docker compose -p $(PROJECT) down

build:
	docker compose -p $(PROJECT) build

logs:
	docker compose -p $(PROJECT) logs -f --tail=100

# Run migrations inside the api container.
migrate:
	docker compose -p $(PROJECT) exec api alembic upgrade head

# Trigger one content cycle against the running api.
run:
	curl -fsS -X POST http://localhost:8001/run | python -m json.tool

dev:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

scheduler:
	python -m app.orchestrator.scheduler

migrate-local:
	alembic upgrade head

test:
	pytest -q

fmt:
	ruff format app tests
	ruff check --fix app tests
