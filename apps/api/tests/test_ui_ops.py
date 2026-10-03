"""T8-OP-UI risk rules. Fakes only. No live Odoo."""

from __future__ import annotations

import pytest

from app.changeset.dispatch import DispatchError, dispatch_op
from app.changeset.handlers import apply_memory, handler_for
from app.changeset.ops import OP_CATALOG
from app.changeset.policy import risk_of
from app.changeset.ui_ops import XPATH_REPLACES_ROOT_OR_LARGE_SUBTREE

pytestmark = pytest.mark.no_app_db

_R1_OPS = (
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
)
_R2_OPS = ("report.inherit", "report.action.create", "report.action.update")
_INHERIT_OPS = ("view.inherit.create", "view.inherit.update", "report.inherit")
_ROOT_OR_LARGE = (
    "/",
    "/*",
    "//",
    "//*",
    "//form",
    "//form[1]",
    "//tree",
    "//list",
    "//kanban",
    "//search",
    "//sheet",
    "//notebook",
    "//t",
    "//t[@t-name='sale.report_saleorder_document']",
    "//t[@t-call='web.external_layout']",
    "//templates/t",
    "//div[@class='page']",
    '//div[@class="article"]',
    "//div[contains(@class, 'page')]",
    "//div[contains(@class, 'article')]",
    "//form/sheet",
    "//field",
    "//div",
)


class _Port:
    """In-memory port. A refused inherit must not call it."""

    def __init__(self) -> None:
        self.created: list[tuple[str, dict]] = []

    def create(self, model: str, values: dict) -> int:
        self.created.append((model, values))
        return len(self.created)

    def write(self, model: str, ids: list[int], values: dict) -> None:
        raise AssertionError("write")


def _inherit_params(op_type: str, **extra: object) -> dict:
    params: dict = {"xpath": "//field[@name='partner_id']"}
    if op_type.startswith("view."):
        params["model"] = "sale.order"
    params.update(extra)
    return params


def test_ui_family_risk_is_r1_except_reports_r2() -> None:
    assert len(_R1_OPS) + len(_R2_OPS) == 14
    for op_type in _R1_OPS:
        assert OP_CATALOG[op_type].risk_base == "R1"
        assert risk_of({"type": op_type, "params": {"model": "sale.order"}}) == "R1"
    for op_type in _R2_OPS:
        assert OP_CATALOG[op_type].risk_base == "R2"
        assert risk_of({"type": op_type, "params": {"model": "sale.order", "xpath": "//span"}}) == "R2"
    assert risk_of(
        {
            "type": "report.inherit",
            "risk": "R1",
            "params": {"xpath": "//span[@t-field='o.name']", "position": "inside"},
        }
    ) == "R2"
    assert risk_of(
        {"type": "view.inherit.create", "params": {"model": "sale.order", "xpath": "//field[@name='partner_id']"}}
    ) == "R1"


def test_view_inherit_update_requires_exactly_one_anchor() -> None:
    handler = handler_for("view.inherit.update")
    assert handler.issues({"model": "sale.order"})
    assert handler.issues({"model": "sale.order", "anchor": "field[@name='partner_id']", "expect_matches": 2})
    assert handler.issues({"model": "sale.order", "xpath": "//field[@name='partner_id']"}) == []


def test_report_inherit_requires_exactly_one_anchor() -> None:
    handler = handler_for("report.inherit")
    missing = handler.issues({"report": "sale.report_saleorder"})
    assert any("anchor" in item for item in missing)
    counted = handler.issues({"xpath": "//div[@class='page']", "position": "inside", "expect_matches": 2})
    assert any("exactly one" in item for item in counted)
    assert handler.issues({"xpath": "//span[@t-field='o.name']", "expect_matches": 0})
    assert handler.issues({"xpath": "//div[@class='page']", "position": "inside"}) == []
    for op_type in ("report.action.create", "report.action.update"):
        assert handler_for(op_type).issues({"name": "Quotation"}) == []


@pytest.mark.parametrize("op_type", _INHERIT_OPS)
@pytest.mark.parametrize("expr", _ROOT_OR_LARGE)
def test_xpath_that_replaces_root_or_large_subtree_is_refused(op_type: str, expr: str) -> None:
    handler = handler_for(op_type)
    params = _inherit_params(op_type, xpath=expr, position="replace")
    assert XPATH_REPLACES_ROOT_OR_LARGE_SUBTREE in handler.issues(params)
    assert handler.refuse_reason(params) == XPATH_REPLACES_ROOT_OR_LARGE_SUBTREE
    store: dict = {}
    with pytest.raises(PermissionError, match="root or a large subtree"):
        apply_memory(store, {"type": op_type, "params": params})
    assert store == {}
    port = _Port()
    with pytest.raises(DispatchError, match="root or a large subtree"):
        dispatch_op(port, {"type": op_type, "params": params})
    assert port.created == []


@pytest.mark.parametrize("op_type", _INHERIT_OPS)
def test_arch_replace_of_root_is_refused_when_position_param_is_safe(op_type: str) -> None:
    handler = handler_for(op_type)
    params = _inherit_params(
        op_type,
        position="after",
        arch=(
            "<data>"
            "<xpath position='replace' expr='/'><form/></xpath>"
            "<xpath expr=\"//sheet\" position=\"REPLACE\"/>"
            "</data>"
        ),
    )
    assert handler.issues(params) == [XPATH_REPLACES_ROOT_OR_LARGE_SUBTREE]
    assert handler.refuse_reason(params) == XPATH_REPLACES_ROOT_OR_LARGE_SUBTREE
    port = _Port()
    with pytest.raises(DispatchError, match="large subtree"):
        dispatch_op(port, {"type": op_type, "params": params})
    assert port.created == []


def test_view_position_replace_of_one_field_stays_forbidden_and_is_not_rt22() -> None:
    handler = handler_for("view.inherit.create")
    params = {"model": "sale.order", "xpath": "//field[@name='partner_id']", "position": "replace"}
    issues = handler.issues(params)
    assert "position replace is forbidden" in issues
    assert XPATH_REPLACES_ROOT_OR_LARGE_SUBTREE not in issues
    assert handler.refuse_reason(params) is None
    store: dict = {}
    with pytest.raises(ValueError, match="position replace is forbidden"):
        apply_memory(store, {"type": "view.inherit.create", "params": params})
    assert store == {}


def test_report_may_replace_one_small_node() -> None:
    handler = handler_for("report.inherit")
    params = {
        "report": "sale.report_saleorder",
        "xpath": "//span[@t-field='o.partner_id.name']",
        "position": "replace",
    }
    assert handler.issues(params) == []
    assert handler.refuse_reason(params) is None
    store: dict = {}
    apply_memory(store, {"type": "report.inherit", "params": params})
    assert store
    inside = {"model": "sale.order", "xpath": "//div[@class='page']", "position": "inside"}
    assert handler_for("view.inherit.create").issues(inside) == []
    assert handler_for("view.inherit.create").issues(
        {"model": "sale.order", "xpath": "//div[@id='total']", "position": "after"}
    ) == []


def test_safe_view_inherit_is_recorded_in_memory() -> None:
    store: dict = {}
    apply_memory(
        store,
        {
            "type": "view.inherit.create",
            "params": {"model": "sale.order", "xpath": "//field[@name='partner_id']"},
        },
    )
    assert store
    apply_memory(
        store,
        {"type": "report.inherit", "params": {"xpath": "//div[@class='page']", "position": "inside"}},
    )
    assert len(store) == 2
