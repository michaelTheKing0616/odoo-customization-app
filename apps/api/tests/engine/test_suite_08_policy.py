"""T8-S08. Point at the existing policy matrix. Do not copy its cases.

The ten-cell contract stays in ``tests/test_policy_matrix.py``. This module
loads that file, then calls ``policy_decision``, freeze (``apply_blocked``),
and expiry (``approval_expiry_hours``) the same way that file does.
Production R4 is deny. Production R3 asks for two approvers.

GATE-P3-06 is unrun. mutmut and cosmic-ray are not installed. This module
does not record a mutation score, and it does not call Odoo.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

from app.changeset.policy import apply_blocked, approval_expiry_hours, policy_decision

pytestmark = pytest.mark.no_app_db

_MATRIX_PATH = Path(__file__).resolve().parents[1] / "test_policy_matrix.py"
_RISKS = ("R0", "R1", "R2", "R3", "R4")
_ENVIRONMENTS = ("staging", "production")
_SKIP_REASON = "GATE-P3-06 stays unrun: mutmut and cosmic-ray are not installed"


def _load_policy_matrix() -> ModuleType:
    """Load the existing matrix module from its file.

    Inputs: none. The path is ``tests/test_policy_matrix.py``.
    Outputs: the loaded module.
    Side effects: executes that module's top-level constants. Does not call Odoo.
    Raises FileNotFoundError when the file is missing, or ImportError when
    Python cannot load it.
    """
    if not _MATRIX_PATH.is_file():
        raise FileNotFoundError(_MATRIX_PATH)
    spec = importlib.util.spec_from_file_location(
        "ingenium_existing_policy_matrix",
        _MATRIX_PATH,
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {_MATRIX_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_existing_policy_matrix_module_is_present() -> None:
    """The ten-cell contract module is on disk and importable.

    Inputs: none.
    Outputs: none.
    Side effects: loads ``test_policy_matrix.py``. Does not call Odoo.
    """
    module = _load_policy_matrix()
    matrix = module._MATRIX
    covered = {(row["risk"], row["environment"]) for row in matrix}
    expected = {(risk, env) for risk in _RISKS for env in _ENVIRONMENTS}
    assert covered == expected
    assert len(matrix) == 10
    assert callable(module.test_policy_matrix_cell)
    assert callable(module.test_matrix_covers_every_risk_and_environment)


def test_ten_cells_call_decision_freeze_and_expiry() -> None:
    """Call decision, freeze, and expiry once per existing cell.

    Inputs: the ten cells from the existing matrix module.
    Outputs: none.
    Side effects: none. Does not copy the matrix expectations into this file.
    """
    module = _load_policy_matrix()
    assert len(module._MATRIX) == 10
    for cell in module._MATRIX:
        risk = str(cell["risk"])
        environment = str(cell["environment"])
        decision = policy_decision(risk, environment)
        assert apply_blocked(decision, frozen=True) is True
        assert approval_expiry_hours(risk, environment) == decision["expiry_hours"]


def test_production_r4_is_deny() -> None:
    """Production R4 is denied, including while a freeze is off.

    Inputs: risk R4 and environment production.
    Outputs: none.
    Side effects: none.
    """
    decision = policy_decision("R4", "production")
    assert decision["deny"] is True
    assert decision["allow"] is False
    assert apply_blocked(decision, frozen=True) is True
    assert apply_blocked(decision, frozen=False) is True
    assert approval_expiry_hours("R4", "production") == decision["expiry_hours"]


def test_production_r3_asks_for_two_approvers() -> None:
    """Production R3 asks for two approvers, and a freeze still blocks apply.

    Inputs: risk R3 and environment production.
    Outputs: none.
    Side effects: none.
    """
    decision = policy_decision("R3", "production")
    assert decision["approvers"] == 2
    assert apply_blocked(decision, frozen=True) is True
    assert approval_expiry_hours("R3", "production") == decision["expiry_hours"]


def test_gate_p3_06_mutation_score_stays_unrun() -> None:
    """Leave the mutation gate unrun.

    Inputs: none.
    Outputs: none. The test is skipped.
    Side effects: none. Does not install a mutation tool and does not invent a score.
    """
    pytest.skip(_SKIP_REASON)
