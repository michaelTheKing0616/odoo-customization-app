"""PDF-04 — create from scratch, grounded (router + design gates)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.report_design import (
    compile_report_design,
    ground_design_against_schema,
    refuse_empty_design,
)
from app.routers import reports as reports_router


class _Field:
    def __init__(self, name: str, ttype: str = "char", relation: str | None = None):
        self.name = name
        self.ttype = ttype
        self.relation = relation


def _mock_client(*, models: set[str], fields: dict[str, list[_Field]]) -> MagicMock:
    client = MagicMock()
    client.model_exists.side_effect = lambda m: m in models
    client.list_fields.side_effect = lambda m: list(fields.get(m, []))
    return client


def test_ground_design_spec_refuses_unknown_field() -> None:
    client = _mock_client(
        models={"res.partner"},
        fields={"res.partner": [_Field("display_name"), _Field("email")]},
    )
    with pytest.raises(HTTPException) as exc:
        reports_router._ground_design_spec(
            client,
            {
                "model": "res.partner",
                "blocks": [{"type": "field", "field": "nope"}],
            },
            require_blocks=True,
        )
    assert exc.value.status_code == 422
    assert "unknown field" in str(exc.value.detail)


def test_ground_design_spec_refuses_empty_when_creating() -> None:
    client = _mock_client(
        models={"res.partner"},
        fields={"res.partner": [_Field("display_name")]},
    )
    with pytest.raises(HTTPException) as exc:
        reports_router._ground_design_spec(
            client,
            {"model": "res.partner", "blocks": []},
            require_blocks=True,
        )
    assert exc.value.status_code == 422
    assert "empty design" in str(exc.value.detail)


def test_ground_design_spec_loads_related_for_o2m() -> None:
    client = _mock_client(
        models={"sale.order", "sale.order.line"},
        fields={
            "sale.order": [
                _Field("display_name"),
                _Field("order_line", "one2many", "sale.order.line"),
            ],
            "sale.order.line": [_Field("product_id"), _Field("name")],
        },
    )
    reports_router._ground_design_spec(
        client,
        {
            "model": "sale.order",
            "blocks": [
                {
                    "type": "o2m_table",
                    "o2m_field": "order_line",
                    "columns": [{"field": "product_id", "label": "Product"}],
                }
            ],
        },
        require_blocks=True,
    )
    client.list_fields.assert_any_call("sale.order.line")


def test_default_qweb_uses_external_layout() -> None:
    assert "web.external_layout" in reports_router.DEFAULT_QWEB
    assert "web.html_container" not in reports_router.DEFAULT_QWEB


def test_compile_after_grounding_does_not_write_unknown() -> None:
    refuse_empty_design({"blocks": [{"type": "field", "field": "email"}]})
    ground_design_against_schema(
        {"blocks": [{"type": "field", "field": "email"}]},
        parent_field_names={"email", "display_name"},
        require_blocks=True,
    )
    arch = compile_report_design(
        {
            "report_key": "custom.report_partner",
            "blocks": [{"type": "field", "field": "email"}],
        }
    )["arch"]
    assert "email" in arch
    assert "nope" not in arch


def test_preview_probe_success_path_mocked(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sandbox render returns a PDF blob when probe + render succeed (no live Odoo)."""
    import base64

    fake_pdf = b"%PDF-1.4 mock"

    class _Client:
        def model_exists(self, model: str) -> bool:
            return model == "res.partner"

        def list_fields(self, model: str) -> list[_Field]:
            return [_Field("display_name")]

        def execute_kw(self, model: str, method: str, args: list[Any], kwargs: dict | None = None):
            if model == "ir.actions.report" and method == "read":
                return [{"report_name": "custom.report_partner"}]
            if model == "ir.ui.view" and method == "search_read":
                return [{"id": 9, "arch": "<t t-name='custom.report_partner'/>", "key": "custom.report_partner"}]
            if model == "ir.ui.view" and method == "write":
                return True
            raise AssertionError(f"unexpected {model}.{method}")

    class _Probe:
        primary_path = "http_report_pdf"
        message = "ok"

    monkeypatch.setattr(reports_router, "_client", lambda *_a, **_k: _Client())
    monkeypatch.setattr(
        "odoo_client.report_render.probe_report_render",
        lambda *a, **k: _Probe(),
    )
    monkeypatch.setattr(
        "odoo_client.report_render.render_report_pdf",
        lambda *a, **k: fake_pdf,
    )

    body = reports_router.ReportDesignPreviewBody(
        spec={
            "model": "res.partner",
            "report_key": "custom.report_partner",
            "use_external_layout": True,
            "blocks": [{"type": "field", "field": "display_name"}],
        },
        report_id=1,
        record_id=1,
    )
    out = reports_router.report_design_preview("conn-1", body, db=MagicMock())
    assert out.ok is True
    assert out.render_path == "http_report_pdf"
    assert base64.b64decode(out.content_base64) == fake_pdf


def test_ground_design_spec_table_totals_numeric_only_and_annotates_types() -> None:
    """PDF-07: router grounding refuses totals on non-numeric columns and
    re-annotates column ttype from the related model's schema."""
    client = _mock_client(
        models={"sale.order", "sale.order.line"},
        fields={
            "sale.order": [
                _Field("display_name"),
                _Field("order_line", "one2many", "sale.order.line"),
            ],
            "sale.order.line": [
                _Field("name", "char"),
                _Field("price_subtotal", "monetary"),
                _Field("product_uom_qty", "float"),
            ],
        },
    )
    bad = {
        "model": "sale.order",
        "blocks": [
            {
                "type": "o2m_table",
                "o2m_field": "order_line",
                "totals_row": True,
                "columns": [{"field": "name", "label": "Desc", "sum": True, "ttype": "float"}],
            }
        ],
    }
    with pytest.raises(HTTPException) as exc:
        reports_router._ground_design_spec(client, bad, require_blocks=True)
    assert exc.value.status_code == 422
    assert "numeric" in str(exc.value.detail)

    good = {
        "model": "sale.order",
        "report_key": "custom.report_lines",
        "blocks": [
            {
                "type": "o2m_table",
                "o2m_field": "order_line",
                "totals_row": True,
                "columns": [
                    {"field": "name", "label": "Desc", "width": "2fr"},
                    {"field": "price_subtotal", "label": "Subtotal", "sum": True, "ttype": "char"},
                ],
            }
        ],
    }
    out = reports_router._ground_design_spec(client, good, require_blocks=True)
    cols = out["blocks"][0]["columns"]
    assert cols[1]["ttype"] == "monetary"
    assert cols[0]["ttype"] == "char"
    arch = compile_report_design(out)["arch"]
    assert '<th class="text-end" style="text-align: right;">Subtotal</th>' in arch
    assert "sum(doc.order_line.mapped('price_subtotal'))" in arch


def test_ground_design_spec_table_unknown_column_still_refused_with_inspector_keys() -> None:
    client = _mock_client(
        models={"sale.order", "sale.order.line"},
        fields={
            "sale.order": [_Field("order_line", "one2many", "sale.order.line")],
            "sale.order.line": [_Field("name", "char")],
        },
    )
    with pytest.raises(HTTPException) as exc:
        reports_router._ground_design_spec(
            client,
            {
                "model": "sale.order",
                "blocks": [
                    {
                        "type": "o2m_table",
                        "o2m_field": "order_line",
                        "columns": [
                            {"field": "ghost", "label": "G", "align": "right", "width": 30, "sum": True}
                        ],
                    }
                ],
            },
            require_blocks=True,
        )
    assert exc.value.status_code == 422
    assert "unknown field on related model" in str(exc.value.detail)
