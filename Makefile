.PHONY: up down test lint migrate seed reset-db
up:
	docker compose up --build -d
down:
	docker compose down
test:
	cd backend && uv run pytest
	cd frontend && npm test
	cd frontend && npm run test:e2e
lint:
	cd backend && uv run ruff check . && uv run mypy app
	cd frontend && npm run lint && npm run build
migrate:
	cd backend && uv run alembic upgrade head
seed:
	cd backend && uv run python -m app.seed
reset-db:
	docker compose down -v
