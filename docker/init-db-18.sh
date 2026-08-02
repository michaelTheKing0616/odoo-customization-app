#!/usr/bin/env bash
# Create smoke-test DB on the optional Odoo 18 container (M2/GA).
# Hardened like 16/17: stop worker → DROP DATABASE → compose run -i base,web → start.
# Never -i base while the long-running worker has the DB open (KeyError: ir.http).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
COMPOSE=(docker compose -p odoo18 -f "$ROOT/docker/docker-compose.odoo18.yml")
CONTAINER="${ODOO18_CONTAINER:-odoo-custom-odoo18}"
DB_CONTAINER="${ODOO18_DB_CONTAINER:-odoo-custom-db18}"
DB_NAME="${ODOO18_DB:-odoo18_dev}"
ADMIN_PASSWORD="${ODOO_ADMIN_PASSWORD:-admin}"

if ! docker ps --format '{{.Names}}' | grep -qx "$DB_CONTAINER"; then
  echo "DB container ${DB_CONTAINER} is not running. Start with:" >&2
  echo "  docker compose -p odoo18 -f docker/docker-compose.odoo18.yml up -d" >&2
  exit 1
fi

echo "Stopping Odoo 18 worker for clean init..."
"${COMPOSE[@]}" stop odoo18 >/dev/null

echo "Dropping database '${DB_NAME}' if present..."
docker exec "$DB_CONTAINER" psql -U odoo -d postgres -c \
  "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='${DB_NAME}' AND pid <> pg_backend_pid();" \
  >/dev/null 2>&1 || true
docker exec "$DB_CONTAINER" psql -U odoo -d postgres -c \
  "DROP DATABASE IF EXISTS \"${DB_NAME}\";" >/dev/null

echo "Initializing database '${DB_NAME}' on Odoo 18 (base+web)..."
"${COMPOSE[@]}" run --rm --no-deps odoo18 \
  odoo \
  --db_host=db18 \
  -r odoo \
  -w odoo \
  -d "$DB_NAME" \
  -i base,web \
  --without-demo=all \
  --stop-after-init \
  --load-language=en_US

echo "Starting Odoo 18 worker..."
"${COMPOSE[@]}" start odoo18 >/dev/null

echo "Database '${DB_NAME}' ready on http://127.0.0.1:8070 (admin / ${ADMIN_PASSWORD})."
echo "Note: set admin password via Odoo UI on first login if authenticate fails."
echo "Power Ops accounting: ./docker/ensure-account-18.sh (installs account when needed)."
