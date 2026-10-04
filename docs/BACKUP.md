# Copias y restauración

`scripts/backup.sh` crea una copia coherente de MySQL y otra de todo el volumen de adjuntos. Genera sumas SHA-256, limita permisos del directorio en Linux y rota copias antiguas. En Windows usa las ACL de la carpeta; almacena las copias en una ruta privada. El valor predeterminado conserva 14 días en `./backups`.

```sh
bash scripts/backup.sh
CYBERLAB_BACKUP_DIR=/srv/cyberlab-backups CYBERLAB_BACKUP_RETENTION_DAYS=30 bash scripts/backup.sh
```

Guarda `CYBERLAB_BACKUP_DIR` en un disco separado del servidor y cifra ese destino con la herramienta institucional. Las sumas detectan corrupción accidental; no autentican copias contra una persona que pueda modificar tanto el archivo como su suma. Protege el acceso a ambos.

## Programación con cron

Ejemplo diario a las 02:15 UTC. Sustituye la ruta por la ubicación real del checkout y asegúrate de que el usuario tenga acceso al daemon Docker:

```cron
15 2 * * * cd /srv/cyberlab && /usr/bin/env CYBERLAB_BACKUP_DIR=/srv/cyberlab-backups /bin/bash scripts/backup.sh >> /var/log/cyberlab-backup.log 2>&1
```

## Programación con systemd

`cyberlab-backup.service` (ajusta `WorkingDirectory` y destino):

```ini
[Unit]
Description=Backup de Cyberlab
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
WorkingDirectory=/srv/cyberlab
Environment=CYBERLAB_BACKUP_DIR=/srv/cyberlab-backups
ExecStart=/bin/bash /srv/cyberlab/scripts/backup.sh
```

`cyberlab-backup.timer`:

```ini
[Unit]
Description=Backup diario de Cyberlab

[Timer]
OnCalendar=*-*-* 02:15:00 UTC
Persistent=true

[Install]
WantedBy=timers.target
```

Instala ambas unidades en `/etc/systemd/system`, luego ejecuta `systemctl daemon-reload`, `systemctl enable --now cyberlab-backup.timer` y verifica con `systemctl list-timers cyberlab-backup.timer`.

## Restauración

La restauración **reemplaza** el contenido actual de la base de datos y de los adjuntos. Primero conserva el estado actual y detén cualquier tarea que cambie datos. Comprueba la fecha/nombre de la copia y ejecuta desde el checkout correcto:

```sh
bash scripts/backup.sh
bash scripts/restore.sh --confirm /srv/cyberlab-backups/cyberlab-20261002T021500Z
docker compose ps
docker compose exec backend uv run alembic upgrade head
```

El script exige `--confirm`, verifica sumas y formato, rechaza rutas inseguras del archivo de adjuntos, detiene backend mientras restaura y lo vuelve a iniciar al terminar. Tras restaurar, valida `/api/v1/health`, login, clases, retos y descarga de un adjunto. Haz el primer ensayo de restauración en un entorno aislado con una copia de prueba.

## Alcance y recuperación

La copia incluye MySQL y el volumen `/app/storage`; no incluye `.env`, imágenes Docker, registros del host ni certificados del gateway. Resguarda esos elementos por separado. Las copias diarias dan un RPO máximo aproximado de 24 horas; el RTO depende del tamaño de los datos y debe medirse durante el ensayo institucional.
