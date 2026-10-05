#!/usr/bin/env sh
set -eu

retention_days=14
if [ "${1:-}" = "--retention-days" ]; then
  retention_days=${2:-}
  shift 2
fi
[ "$#" -eq 0 ] || { echo "Usage: $0 [--retention-days DAYS]" >&2; exit 2; }
case "$retention_days" in
  ''|*[!0-9]*) echo "Retention days must be a positive integer." >&2; exit 2 ;;
esac
[ "$retention_days" -ge 1 ] || { echo "Retention days must be at least 1." >&2; exit 2; }

config=/etc/ncc/server.env
backup_root=/var/lib/no0bz/ncc/backups
[ -r "$config" ] || { echo "NCC server configuration is not readable: $config" >&2; exit 1; }

set -a
# The file is managed by NCC's service installer and contains only environment assignments.
. "$config"
set +a

database_url=${NCC_SERVER_DATABASE_URL:-}
[ -n "$database_url" ] || { echo "NCC_SERVER_DATABASE_URL is missing." >&2; exit 1; }
database_url=$(printf '%s' "$database_url" | sed 's#^postgresql+psycopg:#postgresql:#')

umask 077
install -d -m 0700 "$backup_root"
timestamp=$(date -u +%Y%m%dT%H%M%SZ)
temporary="$backup_root/ncc-$timestamp.dump.partial"
destination="$backup_root/ncc-$timestamp.dump"

trap 'rm -f "$temporary"' EXIT HUP INT TERM
pg_dump --format=custom --file="$temporary" --dbname="$database_url"
mv "$temporary" "$destination"
find "$backup_root" -maxdepth 1 -type f -name 'ncc-*.dump' -mtime "+$retention_days" -delete
trap - EXIT HUP INT TERM
echo "NCC database backup complete: $destination"
