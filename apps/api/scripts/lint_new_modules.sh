#!/usr/bin/env bash
# Report-only lint slot for new API modules (not repo-wide).
# Lints app/request_id.py and app/logging_config.py when present; exits 0 if none exist.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FILES=()
REQ="$ROOT/app/request_id.py"
LOG="$ROOT/app/logging_config.py"
RB="$ROOT/app/rollback_tiers.py"
if [[ -f "$REQ" ]]; then FILES+=("$REQ"); fi
if [[ -f "$LOG" ]]; then FILES+=("$LOG"); fi
if [[ -f "$RB" ]]; then FILES+=("$RB"); fi
if [[ ${#FILES[@]} -eq 0 ]]; then
  exit 0
fi
cd "$ROOT"
uv run --extra dev ruff check "${FILES[@]}"
uv run --extra dev mypy "${FILES[@]}"
