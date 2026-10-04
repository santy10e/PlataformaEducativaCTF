# Instalación limpia

## Requisitos

- Docker Engine con Docker Compose v2 (Docker Desktop sirve para desarrollo).
- Una máquina Linux para despliegue estable en la red institucional.
- Acceso por navegador a esa máquina. La instalación expone HTTP en el puerto 80; para operar fuera de un laboratorio aislado, termina TLS en un gateway institucional confiable.

## Primera instalación

1. Clona o copia el repositorio en el servidor y entra en su carpeta.
2. Crea el archivo de entorno y genera claves aleatorias. No reutilices los valores de ejemplo:

   ```sh
   cp .env.example .env
   openssl rand -hex 32
   ```

   Usa valores distintos para `MYSQL_ROOT_PASSWORD`, `MYSQL_PASSWORD`, `BACKEND_SECRET_KEY`, `FLAG_HMAC_SECRET` y `ADMIN_PASSWORD`. Guarda `.env` fuera de Git y limita sus permisos (`chmod 600 .env`). Define `APP_ENV=production`.
3. Construye e inicia los contenedores: `docker compose up --build -d`.
4. Aplica las migraciones: `docker compose exec backend uv run alembic upgrade head`.
5. Crea los datos iniciales: `docker compose exec backend uv run python -m app.seed`.
6. Comprueba `docker compose ps`, `http://SERVIDOR/api/v1/health` y abre la plataforma desde un navegador.
7. Inicia sesión con `ADMIN_USERNAME` y `ADMIN_PASSWORD`; cambia o sustituye la contraseña inicial antes de abrir el servicio a estudiantes.

Los datos de MySQL y los adjuntos están en volúmenes Docker persistentes. `docker compose down` conserva esos volúmenes. **No uses `docker compose down -v` en una instalación con datos**, porque elimina la base y los archivos.

## Actualización

1. Crea una copia con `bash scripts/backup.sh`.
2. Actualiza el código y reconstruye: `docker compose up --build -d`.
3. Aplica las migraciones: `docker compose exec backend uv run alembic upgrade head`.
4. Comprueba salud, login y una ruta docente/estudiante antes de anunciar la actualización.

## Parada y reinicio

- Parar: `docker compose stop`.
- Iniciar: `docker compose start`.
- Ver registros operativos: `docker compose logs --since=15m nginx backend mysql`.

Consulta [TROUBLESHOOTING.md](TROUBLESHOOTING.md) si el chequeo de salud no responde.
