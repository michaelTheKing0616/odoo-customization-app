"""Checked-in plan cards for one op in each family.

T8-CARD floor: schema, UI, logic, security, settings, and data.
GATE-P3-10 still needs a reviewed snapshot for every other catalog op.

``expires_at`` is omitted. It follows the wall clock and the policy expiry:
production R2 and above is 24 hours; production R0 and R1, and staging, are 7 days.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app.changeset.ops import OP_CATALOG
from app.changeset.plan_card import PLAN_CARD_SECTIONS, compute_plan_hash, render_plan_card

pytestmark = pytest.mark.no_app_db

_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "plan_cards"
_REQUIRED_FAMILIES = ("schema", "ui", "logic", "security", "settings", "data")

# Family membership follows the op catalog in docs/plans/next-phase/T8_BOT_ENGINE.md.
# ``data.unlink`` is in the live catalog and belongs with the data family.
_FAMILY_OPS: dict[str, frozenset[str]] = {
    "schema": frozenset(
        {
            "model.create",
            "model.scaffold",
            "field.create",
            "field.update",
            "field.deprecate",
            "field.delete",
            "selection.update",
            "constraint.sql",
        }
    ),
    "ui": frozenset(
        {
            "view.inherit.create",
            "view.inherit.update",
            "view.archive",
            "view.create_base",
            "action.window.create",
            "action.window.update",
            "menu.create",
            "menu.update",
            "menu.archive",
            "filter.create",
            "filter.update",
            "report.inherit",
            "report.action.create",
            "report.action.update",
        }
    ),
    "logic": frozenset(
        {
            "server_action.create",
            "server_action.update",
            "automation.create",
            "automation.update",
            "automation.disable",
            "cron.create",
            "cron.update",
            "cron.disable",
            "sequence.create",
            "sequence.update",
            "mail_template.create",
            "mail_template.update",
            "activity_type.create",
            "activity_type.update",
            "stage.upsert",
            "stage.reorder",
            "stage.archive",
            "config_record.upsert",
        }
    ),
    "security": frozenset(
        {
            "group.create",
            "access.create",
            "access.update",
            "rule.create",
            "rule.update",
            "field.groups.set",
            "user.groups.assign",
            "user.create",
            "user.archive",
        }
    ),
    "settings": frozenset(
        {
            "setting.set",
            "config_param.set",
            "company.update",
            "module.install",
            "module.upgrade",
            "module.uninstall",
        }
    ),
    "data": frozenset(
        {
            "data.create_batch",
            "data.update_batch",
            "data.unlink",
            "data.archive_batch",
            "data.import_upsert",
            "data.merge",
            "data.delete",
            "translation.upsert",
        }
    ),
}


def _paths() -> list[Path]:
    """Golden files checked in under tests/fixtures/plan_cards.

    Inputs: none.
    Outputs: JSON paths, sorted by file name.
    Side effects: reads the directory listing.
    """
    return sorted(_FIXTURES.glob("*.json"))


def _load(path: Path) -> dict[str, Any]:
    """Load one golden snapshot.

    Inputs: path to a plan-card JSON file.
    Outputs: the decoded object.
    Side effects: reads the file. Raises AssertionError when the root is not an object.
    """
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise AssertionError(f"{path.name} is not an object")
    return loaded


def _render(spec: dict[str, Any]) -> dict[str, Any]:
    """Render the card the golden was taken from.

    Inputs: a snapshot object with changeset, goal, assumptions, and environment.
    Outputs: the live plan card, including expires_at.
    Side effects: none.
    """
    return render_plan_card(
        spec["changeset"],
        goal=spec["goal"],
        assumptions=spec["assumptions"],
        environment=spec["environment"],
    )


def _stable(card: dict[str, Any]) -> dict[str, Any]:
    """Drop the wall-clock expiry so the snapshot can be compared.

    Inputs: a rendered plan card.
    Outputs: every section except expires_at.
    Side effects: none.
    """
    return {key: value for key, value in card.items() if key != "expires_at"}


def test_family_map_matches_the_catalog() -> None:
    covered: set[str] = set()
    for name, ops in _FAMILY_OPS.items():
        assert name in _REQUIRED_FAMILIES
        overlap = covered & ops
        assert overlap == set()
        covered |= set(ops)
    assert set(_FAMILY_OPS) == set(_REQUIRED_FAMILIES)
    assert covered == set(OP_CATALOG)


def test_each_family_has_a_snapshot() -> None:
    found: dict[str, str] = {}
    for path in _paths():
        spec = _load(path)
        found[str(spec["family"])] = str(spec["op_type"])
    missing = [name for name in _REQUIRED_FAMILIES if name not in found]
    assert missing == []


@pytest.mark.parametrize("path", _paths(), ids=lambda path: path.name)
def test_rendered_plan_card_hash_matches_golden(path: Path) -> None:
    spec = _load(path)
    family = str(spec["family"])
    op_type = str(spec["op_type"])
    assert op_type in _FAMILY_OPS[family]
    assert spec["changeset"][0]["type"] == op_type
    rendered = _render(spec)
    assert set(PLAN_CARD_SECTIONS) <= set(rendered)
    assert "expires_at" in rendered
    assert "expires_at" not in spec["card"]
    expected_hash = spec["card"]["plan_hash"]
    assert rendered["plan_hash"] == expected_hash, (
        f"{path.name}: plan_hash drifted from {expected_hash} to {rendered['plan_hash']}"
    )
    assert rendered["plan_hash"] == compute_plan_hash(
        spec["changeset"],
        assumptions=spec["assumptions"],
    )
    assert _stable(rendered) == spec["card"]


@pytest.mark.parametrize("path", _paths(), ids=lambda path: path.name)
def test_changing_an_assumption_changes_the_hash(path: Path) -> None:
    spec = _load(path)
    assumptions = list(spec["assumptions"])
    assert assumptions
    revised = [*assumptions[:-1], f"{assumptions[-1]} (revised)"]
    changed = render_plan_card(
        spec["changeset"],
        goal=spec["goal"],
        assumptions=revised,
        environment=spec["environment"],
    )
    assert changed["plan_hash"] != spec["card"]["plan_hash"]
    assert changed["plan_hash"] == compute_plan_hash(
        spec["changeset"],
        assumptions=revised,
    )


def test_plan_card_expiry_follows_policy() -> None:
    from datetime import datetime, timezone

    low = render_plan_card(
        [{"type": "mail_template.create", "params": {"name": "Note", "model": "res.partner"}}],
        goal="template",
        assumptions=["The model exists"],
        environment="production",
    )
    high = render_plan_card(
        [{"type": "data.delete", "params": {"model": "res.partner"}}],
        goal="delete",
        assumptions=["The rows are listed"],
        environment="production",
    )
    staging = render_plan_card(
        [{"type": "field.create", "params": {"model": "sale.order", "name": "x_note", "ttype": "char"}}],
        goal="note",
        assumptions=["The host exists"],
        environment="staging",
    )
    now = datetime.now(timezone.utc)

    def hours_until(card: dict[str, Any]) -> float:
        return (datetime.fromisoformat(card["expires_at"]) - now).total_seconds() / 3600

    assert hours_until(low) > 24 * 6
    assert hours_until(staging) > 24 * 6
    assert 23 < hours_until(high) < 25
