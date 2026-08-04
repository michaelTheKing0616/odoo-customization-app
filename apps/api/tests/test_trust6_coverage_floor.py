"""TRUST-6 mutation coverage floor gate (checker + documented test bundle)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "scripts" / "check_mutation_coverage.py"
FLOORS = ROOT / "mutation_coverage_floors.json"


def test_mutation_coverage_checker_accepts_synthetic_payload(tmp_path: Path) -> None:
    payload = {
        "files": {
            "app/safety_gate.py": {
                "summary": {"num_statements": 100, "covered_lines": 90, "missing_lines": 10}
            },
            "app/spec_apply_ui.py": {
                "summary": {"num_statements": 100, "covered_lines": 75, "missing_lines": 25}
            },
        }
    }
    cov_path = tmp_path / "cov.json"
    cov_path.write_text(json.dumps(payload), encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(CHECKER), str(cov_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode != 0
    assert "HIGH" in proc.stdout or "HIGH" in proc.stderr or "MEDIUM" in proc.stdout


def test_mutation_coverage_checker_passes_high_floor_modules(tmp_path: Path) -> None:
    cfg = json.loads(FLOORS.read_text(encoding="utf-8"))
    floors_path = tmp_path / "floors.json"
    mini = {
        **cfg,
        "medium_floor_modules": [],
        "medium_floor_ratchet_modules": [],
        "deferred_modules": [],
    }
    floors_path.write_text(json.dumps(mini), encoding="utf-8")
    files = {}
    for key in mini["high_floor_modules"]:
        files[key] = {
            "summary": {"num_statements": 50, "covered_lines": 45, "missing_lines": 5}
        }
    cov_path = tmp_path / "cov_ok.json"
    cov_path.write_text(json.dumps({"files": files}), encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(CHECKER), str(cov_path), str(floors_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
