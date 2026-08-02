#!/usr/bin/env bash
# Create smoke-test DB on optional Odoo 17 container (M3).
# Stops the long-running odoo process during init to avoid partial registries
# (KeyError: ir.http) when -i base races with the live worker.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
COMPOSE=(docker compose -p odoo17 -f "$ROOT/docker/docker-compose.odoo17.yml")
CONTAINER="${ODOO17_CONTAINER:-odoo-custom-odoo17}"
DB_CONTAINER="${ODOO17_DB_CONTAINER:-odoo-custom-db17}"
DB_NAME="${ODOO17_DB:-odoo17_dev}"
ADMIN_PASSWORD="${ODOO_ADMIN_PASSWORD:-admin}"

if ! docker ps --format '{{.Names}}' | grep -qx "$DB_CONTAINER"; then
  echo "DB container ${DB_CONTAINER} is not running. Start with:" >&2
  echo "  docker compose -p odoo17 -f docker/docker-compose.odoo17.yml up -d" >&2
  exit 1
fi

echo "Stopping Odoo 17 worker for clean init..."
"${COMPOSE[@]}" stop odoo17 >/dev/null

echo "Dropping database '${DB_NAME}' if present..."
docker exec "$DB_CONTAINER" psql -U odoo -d postgres -c \
  "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='${DB_NAME}' AND pid <> pg_backend_pid();" \
  >/dev/null 2>&1 || true
docker exec "$DB_CONTAINER" psql -U odoo -d postgres -c \
  "DROP DATABASE IF EXISTS \"${DB_NAME}\";" >/dev/null

echo "Initializing database '${DB_NAME}' on Odoo 17 (base+web)..."
# One-shot init container (same image/network/volumes as the service).
"${COMPOSE[@]}" run --rm --no-deps odoo17 \
  odoo \
  --db_host=db17 \
  -r odoo \
  -w odoo \
  -d "$DB_NAME" \
  -i base,web \
  --without-demo=all \
  --stop-after-init \
  --load-language=en_US

echo "Starting Odoo 17 worker..."
"${COMPOSE[@]}" start odoo17 >/dev/null

echo "Database '${DB_NAME}' ready on http://127.0.0.1:8071 (admin / ${ADMIN_PASSWORD})."
echo "Note: set admin password via Odoo UI on first login if authenticate fails."
