#!/usr/bin/env bash
# TRUST-7 — Re-encrypt Odoo connection secrets after FERNET_KEY rotation.
#
# Usage (from repo root, app DB reachable):
#   export DATABASE_URL='postgresql+psycopg://...'
#   export OLD_FERNET_KEY='...'
#   export NEW_FERNET_KEY='...'
#   uv run --directory apps/api python ../../scripts/rotate_fernet_key.py --dry-run
#   uv run --directory apps/api python ../../scripts/rotate_fernet_key.py
#
# Procedure:
# 1. Take a pg_dump of the app DB (see docs/DEPLOY.md).
# 2. Run with --dry-run; confirm row count.
# 3. Run without --dry-run during a maintenance window.
# 4. Update deployment env NEW_FERNET_KEY only after all rows re-encrypted.
# 5. Spot-check one connection probe from the UI.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec uv run --directory "$SCRIPT_DIR/../apps/api" python "$SCRIPT_DIR/rotate_fernet_key.py" "$@"
