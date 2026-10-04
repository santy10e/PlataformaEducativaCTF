# Diagnóstico

## Un contenedor no arranca

```sh
docker compose ps
docker compose logs --tail=100 mysql backend nginx frontend
```

Verifica que `.env` exista, que las contraseñas obligatorias estén definidas y que el puerto 80 esté libre. No pegues salidas con valores de entorno o contraseñas en reportes públicos.

## Health devuelve 503

Comprueba `docker compose ps mysql`, espera a que MySQL termine su inicialización y revisa `docker compose logs --tail=100 mysql backend`. Confirma que `MYSQL_DATABASE`, `MYSQL_USER` y `MYSQL_PASSWORD` coincidan con las credenciales de `DATABASE_URL`. Para cambios de esquema aplica `docker compose exec backend uv run alembic upgrade head`.

## Login no funciona

Confirma `ADMIN_USERNAME`/`ADMIN_PASSWORD` y que el seed haya terminado. La limitación temporal de intentos devuelve 429; espera cinco minutos. No restaures ni reinicies la base para solucionar un bloqueo de login.

## Adjuntos no cargan

Revisa que backend esté saludable y el volumen `challenge_files` exista. El proxy admite solicitudes de API de hasta 21 MB; un adjunto individual puede tener límites menores definidos por su operación.

## Interfaz desactualizada tras desplegar

Confirma `docker compose up --build -d frontend nginx` y haz una recarga completa del navegador. Inspecciona `docker compose logs --tail=100 frontend nginx`.

## Espacio en disco o restauración

Comprueba el tamaño de volúmenes y copias antes de borrar nada. Consulta [BACKUP.md](BACKUP.md). No uses `docker compose down -v` para liberar espacio en una instalación que deba conservar datos.
