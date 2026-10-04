#!/usr/bin/env bash
set -Eeuo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
backup_root="${CYBERLAB_BACKUP_DIR:-$repo_root/backups}"
retention_days="${CYBERLAB_BACKUP_RETENTION_DAYS:-14}"
if ! [[ "$retention_days" =~ ^[0-9]+$ ]] || (( retention_days < 1 )); then
  echo "CYBERLAB_BACKUP_RETENTION_DAYS must be a positive integer" >&2
  exit 2
fi
mkdir -p -- "$backup_root"
case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*) ;; # Windows access control lists protect the backup directory.
  *) chmod 700 "$backup_root" ;;
esac
backup_root="$(cd "$backup_root" && pwd)"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup_dir="$backup_root/cyberlab-$stamp"
mkdir -- "$backup_dir"
cleanup_on_error() { rm -rf -- "$backup_dir"; }
trap cleanup_on_error ERR
case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*) ;;
  *) chmod 700 "$backup_dir" ;;
esac

docker compose exec -T mysql sh -ec \
  'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysqldump -uroot --single-transaction --routines --triggers --events "$MYSQL_DATABASE"' \
  | gzip -9 > "$backup_dir/database.sql.gz"
docker compose exec -T backend sh -ec 'tar -C /app/storage -czf - .' > "$backup_dir/challenge-files.tar.gz"
gzip -t "$backup_dir/database.sql.gz" "$backup_dir/challenge-files.tar.gz"
(cd "$backup_dir" && sha256sum database.sql.gz challenge-files.tar.gz > SHA256SUMS)
printf 'CYBERLAB backup\nCreated UTC: %s\n' "$stamp" > "$backup_dir/README.txt"
trap - ERR

# Rotate only backup directories created by this script, beneath the configured root.
find "$backup_root" -mindepth 1 -maxdepth 1 -type d -name 'cyberlab-*' -mtime "+$retention_days" -print0 \
  | while IFS= read -r -d '' old_backup; do
      name="$(basename "$old_backup")"
      if [[ "$name" =~ ^cyberlab-[0-9]{8}T[0-9]{6}Z$ && "$(dirname "$old_backup")" == "$backup_root" ]]; then
        rm -rf -- "$old_backup"
      fi
    done
echo "Backup created: $backup_dir"
