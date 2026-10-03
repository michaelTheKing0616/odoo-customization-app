"""Second apply of the same spec is a no-op."""

from __future__ import annotations

from app.config_as_code.apply import MemoryDb, apply_plan
from app.config_as_code.loader import compile_plan, load_spec

_SPEC = """
version: 1
project: demo
custom_fields:
  - model: res.partner
    name: x_rc_number
    ttype: char
"""


def test_second_apply_writes_nothing() -> None:
    plan = compile_plan(load_spec(_SPEC))
    db = MemoryDb()
    assert apply_plan(db, plan) == 1
    assert apply_plan(db, plan) == 0
    assert db.writes == 1
