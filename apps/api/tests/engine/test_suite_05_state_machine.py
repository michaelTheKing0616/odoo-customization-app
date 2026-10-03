"""T8-S05. The phase table allows only its legal edges.

Each edge returned by ``legal_targets`` is one case and must pass
``assert_transition``. INTAKE to EXECUTE is not an edge and must raise
``IllegalTransition``. ``test_model_cannot_skip_to_execute`` stays as written.

This module reads the table. It does not call Odoo and does not change a phase.
"""

from __future__ import annotations

import pytest

from app.agent_runtime.phases import PHASES, IllegalTransition, assert_transition, legal_targets

pytestmark = pytest.mark.no_app_db


def _legal_edges() -> tuple[tuple[str, str], ...]:
    """Every allowed (current, next) pair on the phase table.

    Inputs: none. Reads ``PHASES`` and ``legal_targets``.
    Outputs: pairs sorted by next phase within each current phase.
    Side effects: none.
    Raises AssertionError when a phase name is repeated, a target is not
    itself a phase, or the table has no edges. Raises IllegalTransition
    when a name in ``PHASES`` has no row.
    """
    if len(PHASES) != len(set(PHASES)):
        raise AssertionError("PHASES lists the same name twice")
    phase_names = frozenset(PHASES)
    edges: list[tuple[str, str]] = []
    for phase in PHASES:
        targets = legal_targets(phase)
        outside = targets - phase_names
        if outside:
            raise AssertionError(
                f"{phase} targets phases that are not in PHASES: {sorted(outside)}"
            )
        edges.extend((phase, nxt) for nxt in sorted(targets))
    if not edges:
        raise AssertionError("the phase table has no legal edges")
    return tuple(edges)


_EDGES = _legal_edges()


@pytest.mark.parametrize(
    ("current", "nxt"),
    _EDGES,
    ids=[f"{current}-to-{nxt}" for current, nxt in _EDGES],
)
def test_legal_edge_is_allowed(current: str, nxt: str) -> None:
    """One legal edge is allowed.

    Inputs: the current phase and the next phase from the table.
    Outputs: none. ``assert_transition`` returns when the edge is legal.
    Side effects: none.
    """
    assert nxt in legal_targets(current)
    assert_transition(current, nxt)


def test_intake_skip_to_execute_is_refused() -> None:
    """INTAKE to EXECUTE is refused.

    Inputs: none.
    Outputs: none.
    Side effects: none. The call raises and does not record a transition.
    """
    assert "EXECUTE" not in legal_targets("INTAKE")
    with pytest.raises(IllegalTransition) as caught:
        assert_transition("INTAKE", "EXECUTE")
    message = str(caught.value)
    assert "INTAKE" in message
    assert "EXECUTE" in message
