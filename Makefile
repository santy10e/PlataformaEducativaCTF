COMPOSE ?= docker compose
.PHONY: up down test e2e lint migrate seed reset-db
up:
	$(COMPOSE) up --build -d
down:
	$(COMPOSE) down
test:
	cd backend && uv run pytest
	cd frontend && npm test
# Browser journeys against a running, seeded stack. Requires an ADMIN account; it never skips silently.
e2e:
	@test -n "$(CYBERLAB_E2E_USERNAME)" && test -n "$(CYBERLAB_E2E_PASSWORD)" || { echo "Set CYBERLAB_E2E_USERNAME and CYBERLAB_E2E_PASSWORD (ADMIN account) and optionally CYBERLAB_E2E_BASE_URL (default http://localhost)"; exit 1; }
	cd frontend && CYBERLAB_E2E_BASE_URL=$${CYBERLAB_E2E_BASE_URL:-http://localhost} npm run test:e2e
lint:
	cd backend && uv run ruff check . && uv run mypy app
	cd frontend && npm run lint && npm run build
# The backend applies migrations on start; this target is for running them by hand (for example after `git pull`).
migrate:
	$(COMPOSE) exec -T backend uv run alembic upgrade head
# Creates roles, permissions, settings, taxonomy, the admin account (ADMIN_USERNAME/ADMIN_PASSWORD) and the demo event. Safe to repeat.
seed:
	$(COMPOSE) exec -T backend uv run python -m app.seed
# Destroys the database AND uploaded files, then rebuilds an empty, seeded system.
reset-db:
	@test "$(CONFIRM)" = "yes" || { echo "reset-db deletes ALL data (database and uploads). Re-run as: make reset-db CONFIRM=yes"; exit 1; }
	$(COMPOSE) down -v
	$(COMPOSE) up --build -d
	@until $(COMPOSE) exec -T backend python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health')" >/dev/null 2>&1; do echo "waiting for backend..."; sleep 3; done
	$(MAKE) seed
