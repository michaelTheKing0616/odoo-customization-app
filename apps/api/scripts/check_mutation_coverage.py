#!/usr/bin/env python3
"""TRUST-6 — enforce mutation-module coverage floors from coverage.py JSON."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FLOORS_PATH = ROOT / "mutation_coverage_floors.json"


def _line_percent(summary: dict) -> float:
    statements = int(summary.get("num_statements") or 0)
    if statements == 0:
        return 100.0
    covered = int(summary.get("covered_lines") or 0)
    return 100.0 * covered / statements


def check_coverage(coverage_json: Path, floors_path: Path = FLOORS_PATH) -> list[str]:
    cfg = json.loads(floors_path.read_text(encoding="utf-8"))
    data = json.loads(coverage_json.read_text(encoding="utf-8"))
    files: dict = data.get("files") or {}
    min_stmts = int(cfg.get("min_statements") or 0)
    high_pct = float(cfg["high_floor_percent"])
    medium_pct = float(cfg["medium_floor_percent"])
    deferred_pct = float(cfg.get("medium_floor_deferred_percent") or medium_pct)

    failures: list[str] = []

    def check_list(keys: list[str], floor: float, label: str) -> None:
        for key in keys:
            entry = files.get(key)
            if entry is None:
                failures.append(f"{label} missing coverage entry for {key}")
                continue
            summary = entry.get("summary") or {}
            stmts = int(summary.get("num_statements") or 0)
            if stmts < min_stmts:
                continue
            pct = _line_percent(summary)
            if pct + 1e-9 < floor:
                failures.append(f"{label} {key}: {pct:.1f}% < {floor:.0f}% ({stmts} stmts)")

    check_list(list(cfg.get("high_floor_modules") or []), high_pct, "HIGH")
    check_list(list(cfg.get("medium_floor_modules") or []), medium_pct, "MEDIUM")
    ratchet_keys = list(cfg.get("medium_floor_ratchet_modules") or [])
    check_list(ratchet_keys, deferred_pct, "RATCHET")
    check_list(list(cfg.get("deferred_modules") or []), deferred_pct, "DEFERRED")
    return failures


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        print("Usage: check_mutation_coverage.py coverage.json [floors.json]", file=sys.stderr)
        return 2
    path = Path(args[0])
    floors_path = Path(args[1]) if len(args) > 1 else FLOORS_PATH
    if not path.is_file():
        print(f"Coverage file not found: {path}", file=sys.stderr)
        return 2
    failures = check_coverage(path, floors_path=floors_path)
    if failures:
        print("Mutation coverage floor breach:")
        for line in failures:
            print(f"  - {line}")
        return 1
    print("Mutation coverage floors: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
