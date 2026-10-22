"""B0-GREEN oracle. Fails when web `tsc --noEmit` does not exit 0.

This file does not replace AC1–AC4. Those counts stay in the Worker packet.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.no_app_db

_REPO = Path(__file__).resolve().parents[3]
_TSC_COMMAND = (
    "pnpm",
    "--filter",
    "@odoo-custom/web",
    "exec",
    "tsc",
    "--noEmit",
)


def test_b0_green_web_tsc_no_emit_exits_zero() -> None:
    """`pnpm --filter @odoo-custom/web exec tsc --noEmit` exits 0."""
    completed = subprocess.run(
        _TSC_COMMAND,
        cwd=_REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    detail = (completed.stdout + "\n" + completed.stderr).strip()
    assert completed.returncode == 0, detail or f"tsc exited {completed.returncode}"
