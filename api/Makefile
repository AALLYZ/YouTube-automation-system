VENV := .venv/bin
PORT ?= 8090

.PHONY: install migrate seed run worker test fmt web web-dev

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

# Build the dashboard into web/dist (served by FastAPI at /)
web:
	cd ../web && npm install && npm run build

# Run the dashboard dev server (proxies /api -> :8090)
web-dev:
	cd ../web && npm run dev
