VENV := .venv/bin
PORT ?= 8090

.PHONY: install migrate seed run worker test fmt

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
