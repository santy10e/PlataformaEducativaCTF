# Diagnóstico

## Un contenedor no arranca

```sh
docker compose ps
docker compose logs --tail=100 mysql backend nginx frontend
```

Verifica que `.env` exista, que las contraseñas obligatorias estén definidas y que el puerto 80 esté libre. No pegues salidas con valores de entorno o contraseñas en reportes públicos.

## Health devuelve 503

Comprueba `docker compose ps mysql`, espera a que MySQL termine su inicialización y revisa `docker compose logs --tail=100 mysql backend`. Confirma que `MYSQL_DATABASE`, `MYSQL_USER` y `MYSQL_PASSWORD` coincidan con las credenciales de `DATABASE_URL`. El backend aplica las migraciones al arrancar; si una falla, el contenedor se detiene y el error aparece en `docker compose logs backend`.

## Login no funciona

Confirma `ADMIN_USERNAME`/`ADMIN_PASSWORD` y que el seed haya terminado (`make seed`). La limitación temporal de intentos devuelve 429 tras 8 fallos desde el mismo equipo para la misma cuenta; espera cinco minutos o entra desde otro equipo. Si la cuenta tiene contraseña temporal, la aplicación pide cambiarla antes de mostrar nada más. No restaures ni reinicies la base para solucionar un bloqueo de login.

## Adjuntos no cargan

Revisa que backend esté saludable y el volumen `challenge_files` exista. El proxy admite solicitudes de API de hasta 21 MB; un adjunto individual puede tener límites menores definidos por su operación.

## Interfaz desactualizada tras desplegar

Confirma `docker compose up --build -d frontend nginx` y haz una recarga completa del navegador. Inspecciona `docker compose logs --tail=100 frontend nginx`.

## Espacio en disco o restauración

Comprueba el tamaño de volúmenes y copias antes de borrar nada. Consulta [BACKUP.md](BACKUP.md). No uses `docker compose down -v` para liberar espacio en una instalación que deba conservar datos.
