#!/usr/bin/env bash
# Create (or ensure) the smoke-test database on the local Odoo 19 container.
# Odoo 19 CLI: `odoo db [connection opts] init [init opts] DATABASE`
# Default credentials are for local gates only — never for prod.
set -euo pipefail

CONTAINER="${ODOO_CONTAINER:-odoo-custom-odoo}"
DB_NAME="${ODOO_DB:-odoo_dev}"
ADMIN_USER="${ODOO_USER:-admin}"
ADMIN_PASSWORD="${ODOO_ADMIN_PASSWORD:-admin}"

if ! docker ps --format '{{.Names}}' | grep -qx "$CONTAINER"; then
  echo "Container ${CONTAINER} is not running. Start with:" >&2
  echo "  docker compose -f docker/docker-compose.yml up -d" >&2
  exit 1
fi

echo "Ensuring database '${DB_NAME}' exists via odoo db init..."
docker exec "$CONTAINER" odoo db \
  --db_host=db \
  -r odoo \
  -w odoo \
  init \
  --username="$ADMIN_USER" \
  --password="$ADMIN_PASSWORD" \
  --force \
  "$DB_NAME"

echo "Database '${DB_NAME}' ready. Login: ${ADMIN_USER} / ${ADMIN_PASSWORD}"
