#!/usr/bin/env bash
# TRUST-7 — supply-chain security gate (pip-audit, pnpm audit, secrets scan).

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "== secrets scan =="
bash "$ROOT/scripts/secrets_scan.sh"

echo "== pip-audit (apps/api) =="
uv pip install --quiet pip-audit
IGNORE_ARGS=()
if [[ -f "$ROOT/security/pip-audit-allowlist.json" ]]; then
  while IFS= read -r cve; do
    [[ -z "$cve" || "$cve" == \#* ]] && continue
    IGNORE_ARGS+=(--ignore-vuln "$cve")
  done < <(python3 - <<'PY'
import json
from pathlib import Path
data = json.loads(Path("security/pip-audit-allowlist.json").read_text())
for item in data.get("ignored_vulnerabilities", []):
    print(item)
PY
)
fi
uv run --directory apps/api pip-audit ${IGNORE_ARGS[@]+"${IGNORE_ARGS[@]}"}

echo "== pnpm audit (high+) =="
PNPM_AUDIT_OUT="$(mktemp)"
set +e
pnpm audit --audit-level=high >"$PNPM_AUDIT_OUT" 2>&1
PNPM_RC=$?
set -e
cat "$PNPM_AUDIT_OUT"
if [[ "$PNPM_RC" -ne 0 ]]; then
  FOUND="$(grep -oE 'GHSA-[a-z0-9-]+' "$PNPM_AUDIT_OUT" | sort -u || true)"
  UNALLOWED=()
  while IFS= read -r ghsa; do
    [[ -z "$ghsa" ]] && continue
    if ! python3 -c "import json,sys; d=json.load(open('$ROOT/security/pnpm-audit-allowlist.json')); sys.exit(0 if '$ghsa' in d.get('ignored_advisories',[]) else 1)"; then
      UNALLOWED+=("$ghsa")
    fi
  done <<< "$FOUND"
  if [[ "${#UNALLOWED[@]}" -gt 0 ]]; then
    echo "pnpm audit: unallowlisted advisories: ${UNALLOWED[*]}" >&2
    rm -f "$PNPM_AUDIT_OUT"
    exit 1
  fi
  echo "pnpm audit: high findings present but all allowlisted (review on dependency bump)"
fi
rm -f "$PNPM_AUDIT_OUT"

echo "supply-chain gate: OK"
