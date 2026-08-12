#!/usr/bin/env bash
# Sync canonical Expert bridge addon from packages/ into docker/sandbox-addons.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/packages/odoo-expert-bridge"
DEST="$ROOT/docker/sandbox-addons/odoo_expert_bridge"
if [[ ! -d "$SRC" ]]; then
  echo "Missing $SRC" >&2
  exit 1
fi
rm -rf "$DEST"
mkdir -p "$DEST"
cp -R "$SRC/." "$DEST/"
echo "Synced odoo-expert-bridge → docker/sandbox-addons/odoo_expert_bridge"
