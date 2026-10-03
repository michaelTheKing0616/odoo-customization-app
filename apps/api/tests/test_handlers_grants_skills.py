"""Handlers cover the catalog. Grants narrow. Skills are content."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.agent_runtime.runtime import AgentRuntime
from app.bots.grant import BotGrant, decide, install_template_grant
from app.changeset.dispatch import DispatchError, dispatch_op
from app.changeset.handlers import all_handlers, apply_memory, compensate_memory, handler_for
from app.changeset.ops import OP_CATALOG
from app.skills.catalog import all_skills, lint_markdown, narrow_grant_ops, write_packages


class _Port:
    def __init__(self) -> None:
        self.created: list[tuple[str, dict]] = []

    def create(self, model: str, values: dict) -> int:
        self.created.append((model, values))
        return len(self.created)

    def write(self, model: str, ids: list[int], values: dict) -> None:
        return None


def test_every_catalog_op_has_a_handler() -> None:
    handlers = all_handlers()
    assert set(handlers) == set(OP_CATALOG)
    assert len(handlers) >= 55


def test_field_create_round_trip_restores_memory() -> None:
    op = {"type": "field.create", "params": {"model": "sale.order", "name": "x_po_reference", "ttype": "char"}}
    store: dict = {}
    apply_memory(store, op)
    assert store
    compensate_memory(store, op)
    assert store == {}


def test_view_inherit_requires_exactly_one_anchor() -> None:
    handler = handler_for("view.inherit.create")
    assert handler.issues({"model": "sale.order"})
    assert handler.issues({"model": "sale.order", "anchor": "field[@name='partner_id']", "expect_matches": 2})
    assert handler.issues({"model": "sale.order", "xpath": "//field[@name='partner_id']"}) == []


def test_prohibited_ops_have_no_inverse_and_do_not_dispatch() -> None:
    port = _Port()
    for op_type in ("module.uninstall", "data.delete"):
        handler = handler_for(op_type)
        assert handler.refuse_reason({"model": "res.partner"})
        assert handler.inverse({"model": "res.partner"}) is None
        with pytest.raises(DispatchError):
            dispatch_op(port, {"type": op_type, "params": {"model": "res.partner"}})
    assert port.created == []


def test_module_install_has_no_automatic_inverse() -> None:
    handler = handler_for("module.install")
    assert handler.inverse({"module": "sale"}) is None
    with pytest.raises(PermissionError):
        compensate_memory({"module.install::sale": {}}, {"type": "module.install", "params": {"module": "sale"}})


def test_groupless_access_is_rejected_before_create() -> None:
    port = _Port()
    with pytest.raises(PermissionError):
        apply_memory({}, {"type": "access.create", "params": {"model": "sale.order"}})
    with pytest.raises(DispatchError):
        dispatch_op(port, {"type": "access.create", "params": {"model": "sale.order"}})
    assert port.created == []


def test_cascade_and_protected_param_are_refused() -> None:
    with pytest.raises(ValueError):
        apply_memory(
            {},
            {"type": "field.create", "params": {"model": "sale.order", "name": "x_a", "ttype": "many2one", "relation": "res.partner", "on_delete": "cascade"}},
        )
    with pytest.raises(PermissionError):
        apply_memory({}, {"type": "config_param.set", "params": {"key": "database.secret", "value": "x"}})


def test_grant_intersection_blocks_a_wider_request() -> None:
    grant = BotGrant("studio", frozenset({"field.*", "view.*"}), "R2")
    op = {"type": "module.install", "params": {"module": "sale"}}
    assert decide(grant, op) == "grant"
    assert decide(grant, {"type": "field.create", "params": {"model": "sale.order", "name": "x_po_reference"}}) is None
    assert decide(
        grant,
        {"type": "field.create", "params": {"model": "sale.order", "name": "x_po_reference"}},
        requester_ops=frozenset({"view.*"}),
    ) == "requester"


def test_grant_cannot_permit_r4() -> None:
    with pytest.raises(ValueError):
        BotGrant("bad", frozenset({"data.delete"}), "R4")
    grant = BotGrant("data", frozenset({"data.*"}), "R3")
    assert decide(grant, {"type": "data.delete", "params": {"model": "res.partner"}}) == "prohibited"


def test_template_grant_is_not_installed_without_a_human() -> None:
    requested = BotGrant("front-desk", frozenset({"field.*"}), "R1")
    assert install_template_grant(requested, human_approved=False) is None
    assert install_template_grant(requested, human_approved=True) == requested


def test_runtime_drops_an_op_outside_the_grant() -> None:
    grant = BotGrant("studio", frozenset({"field.*"}), "R2")
    runtime = AgentRuntime(grant=grant)
    state = runtime.start()
    runtime.complete_phase(state, "DISCOVER")
    runtime.complete_phase(state, "PLAN")
    result = runtime.call_tool(
        state,
        "changeset_add_op",
        {"op": {"type": "access.create", "params": {"model": "sale.order", "group": "sales"}}},
    )
    assert "GRANT_DENIED" in result["untrusted_data"]
    assert state.changeset == []


def test_skill_lint_rejects_either_fence_style() -> None:
    assert lint_markdown("---\nid: SK-X\n---\n```python\nprint(1)\n```")
    assert lint_markdown("---\nid: SK-X\n---\n~~~\nprint(1)\n~~~")
    skills = all_skills()
    ids = [skill.skill_id for skill in skills]
    assert len(ids) == len(set(ids))
    assert len(skills) >= 180
    for skill in skills:
        errors = lint_markdown(skill.markdown())
        assert errors == [], skill.skill_id
    narrowed = narrow_grant_ops(frozenset({"field.create", "module.install"}), ("field.*",))
    assert narrowed == frozenset({"field.create"})


def test_skill_packages_write_markdown_files(tmp_path: Path) -> None:
    count = write_packages(tmp_path)
    assert count >= 180
    sample = (tmp_path / "SK-META-GROUND" / "SKILL.md").read_text(encoding="utf-8")
    assert "schema_search" in sample
    assert "```" not in sample
