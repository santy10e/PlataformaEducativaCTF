FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv && uv sync --no-dev --frozen
COPY app ./app
COPY alembic.ini ./
COPY migrations ./migrations
# Migrations are idempotent and run on every start so `make up` never serves a database without a schema.
# Only Nginx can reach this port (no published port, internal network), and it overwrites X-Forwarded-For
# with the real peer address, so trusting the forwarded headers here is safe.
CMD ["sh", "-c", "uv run alembic upgrade head && exec uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*'"]
