#!/usr/bin/env bash
# Operator helper: prints the Odoo 20 compose command. Does not start containers.
set -euo pipefail
echo "From repo root, an operator runs:"
echo "  docker compose -p odoo20-custom-dev -f docker/docker-compose.odoo20.yml up -d"
echo "Then wait for http://127.0.0.1:8073/web/login (Odoo 20 smoke)."
