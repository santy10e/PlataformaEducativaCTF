# CYBERLAB

Plataforma educativa de CTF para una red escolar local.

## Inicio rápido
1. Copia `.env.example` a `.env` y cambia las contraseñas de ejemplo.
2. Ejecuta `docker compose up --build -d` (o `make up` si tienes GNU Make).
3. Ejecuta `docker compose exec backend uv run alembic upgrade head`.
4. Ejecuta `docker compose exec backend uv run python -m app.seed`.
5. Abre `http://localhost` o revisa la propuesta visual en `http://localhost/design`.

La cuenta inicial usa el usuario configurado en `ADMIN_USERNAME` y la contraseña de `ADMIN_PASSWORD` en tu `.env` local.

Consulta el estado de implementación en [PROGRESS.md](PROGRESS.md), el contrato técnico en [docs/CONTRACT.md](docs/CONTRACT.md), el formato portable de retos en [docs/CHALLENGE_FORMAT.md](docs/CHALLENGE_FORMAT.md) y las decisiones registradas en [docs/DECISIONS.md](docs/DECISIONS.md).

Para una instalación limpia, operación y recuperación, consulta [docs/INSTALLATION.md](docs/INSTALLATION.md), [docs/ADMIN_GUIDE.md](docs/ADMIN_GUIDE.md), [docs/SECURITY.md](docs/SECURITY.md) y [docs/BACKUP.md](docs/BACKUP.md).
