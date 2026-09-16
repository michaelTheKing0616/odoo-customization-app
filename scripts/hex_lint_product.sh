#!/usr/bin/env bash
# UI DESIGN BOT hard reject: no #714B67 nostalgia; no raw hex on freeze-scoped surfaces.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STRICT="${1:-}"

fail=0

purple="$(
  grep -RIn --include='*.tsx' --include='*.ts' --include='*.css' '714B67\|#714[Bb]67' \
    "$ROOT/apps/web/src" 2>/dev/null | grep -v node_modules || true
)"
if [[ -n "$purple" ]]; then
  echo "hex_lint_product: Odoo purple nostalgia (#714B67) found:"
  echo "$purple"
  fail=1
fi

SCOPED=(
  "$ROOT/apps/web/src/app/connections/[id]/page.tsx"
  "$ROOT/apps/web/src/components/shell"
  "$ROOT/apps/web/src/components/designer"
  "$ROOT/apps/web/src/components/CapabilityProbePanel.tsx"
  "$ROOT/apps/web/src/components/brand"
)

PATTERN='\[#[0-9a-fA-F]{3,8}\]'
hits=""
for target in "${SCOPED[@]}"; do
  if [[ -e "$target" ]]; then
    hits+=$(grep -RInE --include='*.tsx' --include='*.ts' "$PATTERN" "$target" 2>/dev/null || true)
    hits+=$'\n'
  fi
done
hits="$(echo "$hits" | grep -v '^$' | grep -v '\.test\.' || true)"
if [[ -n "$hits" ]]; then
  echo "hex_lint_product: Tailwind arbitrary hex on freeze-scoped surfaces:"
  echo "$hits"
  fail=1
fi

if [[ "$STRICT" == "--strict" ]]; then
  all="$(
    grep -RInE --include='*.tsx' --include='*.ts' "$PATTERN" \
      "$ROOT/apps/web/src/app" "$ROOT/apps/web/src/components" 2>/dev/null \
      | grep -v '\.test\.' | grep -v '\.spec\.' || true
  )"
  if [[ -n "$all" ]]; then
    echo "hex_lint_product (--strict): remaining arbitrary hex:"
    echo "$all"
    fail=1
  fi
fi

if [[ "$fail" -ne 0 ]]; then
  exit 1
fi
echo "hex_lint_product: clean (scoped). Use --strict for full tree."
