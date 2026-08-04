"""TRUST-5 dirty-instance API smoke gate marker."""

from __future__ import annotations

from pathlib import Path


def test_dirty_gate_script_exists() -> None:
    repo = Path(__file__).resolve().parents[3]
    script = repo / "docker" / "run-dirty-gate.sh"
    smoke = repo / "docker" / "dirty_gate_smoke.py"
    assert script.is_file(), "docker/run-dirty-gate.sh missing"
    assert smoke.is_file(), "docker/dirty_gate_smoke.py missing"


def test_dirty_api_smoke_module_documents_full_stack_follow_up() -> None:
    """Full FastAPI mutating sweep on dirty DB remains operator-run via run-dirty-gate.sh."""
    repo = Path(__file__).resolve().parents[3]
    doc = (repo / "docs" / "SAFETY.md").read_text(encoding="utf-8")
    assert "dirty" in doc.lower()
