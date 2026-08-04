#!/usr/bin/env bash
# TRUST-7 — lightweight secrets scan (grep-based; allowlist for known false positives).

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ALLOWLIST="$ROOT/security/secrets-allowlist.txt"
PATTERN='(password\s*=\s*["'"'"'][^"'"'"']{8,}|api[_-]?key\s*=\s*["'"'"'][^"'"'"']{12,}|sk_live_[a-zA-Z0-9]+|AKIA[0-9A-Z]{16})'

cd "$ROOT"

matches="$(rg -n -i --glob '!**/node_modules/**' --glob '!**/.venv/**' --glob '!**/uv.lock' --glob '!**/pnpm-lock.yaml' "$PATTERN" apps packages scripts 2>/dev/null || true)"

if [[ -z "$matches" ]]; then
  echo "secrets scan: no matches"
  exit 0
fi

if [[ ! -f "$ALLOWLIST" ]]; then
  echo "secrets scan: matches found but no allowlist at $ALLOWLIST" >&2
  echo "$matches" >&2
  exit 1
fi

_is_allowlisted() {
  local rel="$1"
  local prefix
  while IFS= read -r prefix; do
    [[ -z "$prefix" || "$prefix" == \#* ]] && continue
    if [[ "$rel" == "$prefix"* ]]; then
      return 0
    fi
  done < "$ALLOWLIST"
  return 1
}

violations=0
while IFS= read -r line; do
  [[ -z "$line" ]] && continue
  file="${line%%:*}"
  rel="${file#"$ROOT"/}"
  if _is_allowlisted "$rel"; then
    continue
  fi
  echo "SECRET? $line" >&2
  violations=$((violations + 1))
done <<< "$matches"

if [[ "$violations" -gt 0 ]]; then
  echo "secrets scan: $violations unallowlisted match(es). Add false positives to security/secrets-allowlist.txt" >&2
  exit 1
fi

echo "secrets scan: all matches allowlisted"
exit 0
