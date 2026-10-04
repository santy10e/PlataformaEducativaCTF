#!/usr/bin/env bash
set -Eeuo pipefail

usage() { echo "Usage: $0 --confirm /absolute/path/to/cyberlab-YYYYMMDDTHHMMSSZ" >&2; exit 2; }
[[ "${1:-}" == "--confirm" && -n "${2:-}" && $# == 2 ]] || usage
backup_dir="$(cd "$2" && pwd)"
name="$(basename "$backup_dir")"
[[ "$name" =~ ^cyberlab-[0-9]{8}T[0-9]{6}Z$ ]] || { echo "Invalid backup directory name" >&2; exit 2; }
for file in database.sql.gz challenge-files.tar.gz SHA256SUMS; do
  [[ -f "$backup_dir/$file" && ! -L "$backup_dir/$file" ]] || { echo "Missing or unsafe backup file: $file" >&2; exit 2; }
done
(cd "$backup_dir" && sha256sum --check --status SHA256SUMS) || { echo "Backup checksum verification failed" >&2; exit 1; }
gzip -t "$backup_dir/database.sql.gz" "$backup_dir/challenge-files.tar.gz"

# The backup contains only regular files/directories. Reject links and traversal before replacing uploads.
docker compose run --rm -T --no-deps backend python -c 'import posixpath,sys,tarfile; archive=tarfile.open(fileobj=sys.stdin.buffer, mode="r|gz"); bad=next((m for m in archive if (lambda p: p == ".." or p.startswith("../") or p.startswith("/"))(posixpath.normpath(m.name)) or not (m.isfile() or m.isdir())), None); sys.exit(f"Unsafe archive entry: {bad.name!r}" if bad else 0)' \
  < "$backup_dir/challenge-files.tar.gz"

echo "This replaces the current CYBERLAB database and uploaded challenge files."
echo "Create a backup of the current installation before continuing."
backend_was_running="$(docker compose ps --status running --services | grep -cx backend || true)"
docker compose stop backend
restart_backend() {
  if [[ "$backend_was_running" == "1" ]]; then docker compose start backend; fi
}
trap restart_backend EXIT

docker compose run --rm -T --no-deps backend sh -ec 'find /app/storage -mindepth 1 -maxdepth 1 -exec rm -rf -- {} + && tar -C /app/storage -xzf -' \
  < "$backup_dir/challenge-files.tar.gz"
gzip -dc "$backup_dir/database.sql.gz" \
  | docker compose exec -T mysql sh -ec 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -uroot "$MYSQL_DATABASE"'
docker compose start backend
trap - EXIT
echo "Restore completed. Check: docker compose ps"
