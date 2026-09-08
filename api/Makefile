VENV := .venv/bin
PORT ?= 8090

.PHONY: install migrate seed run worker test coverage fmt web web-dev retention prod-up prod-down backup

install:
	uv venv --python 3.12 .venv
	uv pip install -e ".[dev]"

migrate:
	$(VENV)/alembic upgrade head

revision:
	$(VENV)/alembic revision --autogenerate -m "$(m)"

seed:
	$(VENV)/python -m app.db.seed

run:
	$(VENV)/uvicorn app.main:app --reload --port $(PORT)

worker:
	$(VENV)/python -m app.workers.run

test:
	$(VENV)/python -m pytest -q

coverage:
	$(VENV)/python -m pytest -q --cov=app --cov-report=term-missing --cov-fail-under=70

# Build the dashboard into web/dist (served by FastAPI at /)
web:
	cd ../web && npm install && npm run build

# Run the dashboard dev server (proxies /api -> :8090)
web-dev:
	cd ../web && npm run dev

# Prune media for terminal jobs older than ARTIFACT_RETENTION_DAYS
retention:
	$(VENV)/python -m app.services.retention $(ARGS)

# Production stack (needs ../.env.prod)
prod-up:
	cd .. && docker compose -f docker-compose.prod.yml up -d --build

prod-down:
	cd .. && docker compose -f docker-compose.prod.yml down

backup:
	cd .. && ./scripts/backup.sh
