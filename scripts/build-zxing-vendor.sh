#!/usr/bin/env bash
# Regenerate the vendored @zxing/browser IIFE bundled into exported Odoo modules (REM-11).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/packages/module-generator/src/module_generator/vendor/zxing-browser.min.js"
mkdir -p "$(dirname "$OUT")"
cd "$ROOT/apps/web"
npx --yes esbuild@0.25.0 node_modules/@zxing/browser/esm/index.js \
  --bundle \
  --format=iife \
  --global-name=ZXingBrowser \
  --minify \
  --outfile="$OUT"
echo "Wrote $(wc -c < "$OUT") bytes -> $OUT"
