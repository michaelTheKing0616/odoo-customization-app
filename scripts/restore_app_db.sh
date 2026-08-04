#!/usr/bin/env bash
# TRUST-7 — Restore the app Postgres database from a custom-format pg_dump.
#
# Usage:
#   export DATABASE_URL='postgresql+psycopg://user:pass@host:5432/dbname'
#   ./scripts/restore_app_db.sh /path/to/backup.dump
#
# WARNING: drops and recreates objects in the target database. Use on a copy first.

set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 /path/to/backup.dump" >&2
  exit 2
fi

BACKUP="$1"
if [[ ! -f "$BACKUP" ]]; then
  echo "Backup file not found: $BACKUP" >&2
  exit 2
fi

DATABASE_URL="${DATABASE_URL:-}"
if [[ -z "$DATABASE_URL" ]]; then
  echo "Set DATABASE_URL (postgresql+psycopg://... or postgresql://...)" >&2
  exit 2
fi

# Strip SQLAlchemy driver suffix for pg_restore/psql.
PG_URL="${DATABASE_URL/postgresql+psycopg/postgresql}"

echo "Restoring $BACKUP into $PG_URL"
echo "This is destructive. Ctrl+C within 5s to abort."
sleep 5

pg_restore --clean --if-exists --no-owner --no-acl --dbname="$PG_URL" "$BACKUP"
echo "Restore complete. Restart API and run GET /health."
