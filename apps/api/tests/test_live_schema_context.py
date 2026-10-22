"""GND-PKT: schema packet from fixture client + SchemaGraph. No live Odoo."""

from __future__ import annotations

import time
from types import SimpleNamespace

import pytest

from app.ai_schema_client import SCHEMA_CATALOG_TTL_S, FakeSchemaClient
from app.live_schema_context import ConnectionRequiredError, build_schema_packet
from odoo_client.read_plane import ReadPlane
from odoo_client.schema_graph import SchemaGraph

pytestmark = pytest.mark.no_app_db

_FORM_ARCH = (
    "<form><sheet><group>"
    '<field name="partner_id"/>'
    '<field name="partner_invoice_id"/>'
    '<field name="date_order"/>'
    "</group></sheet></form>"
)
_LIST_ARCH = '<list><field name="name"/><field name="partner_id"/></list>'
_SEARCH_ARCH = '<search><field name="name"/><field name="partner_id"/></search>'


class _SaleViewTables:
    """In-memory get_view slice. Not a live database."""

    def __call__(self, model: str, method: str, args: list, kwargs: dict):
        if method != "get_view" or model != "sale.order":
            raise AssertionError((model, method))
        view_type = str(kwargs.get("view_type") or "form")
        arches = {"form": _FORM_ARCH, "list": _LIST_ARCH, "search": _SEARCH_ARCH}
        return {"arch": arches.get(view_type, "<form/>")}


def _sale_client() -> FakeSchemaClient:
    return FakeSchemaClient(
        models={"sale.order", "res.partner"},
        fields={
            "sale.order": {
                "partner_id": {
                    "type": "many2one",
                    "ttype": "many2one",
                    "relation": "res.partner",
                    "required": True,
                    "readonly": False,
                    "store": True,
                    "groups": "",
                },
                "partner_invoice_id": {
                    "type": "many2one",
                    "ttype": "many2one",
                    "relation": "res.partner",
                    "required": False,
                },
                "date_order": {"type": "datetime", "ttype": "datetime"},
                "name": {"type": "char", "ttype": "char"},
            }
        },
        methods={"sale.order": {"action_confirm", "formatted_read_group"}},
    )


def _connection(*, major: int = 19) -> SimpleNamespace:
    return SimpleNamespace(
        id="fixture-sale",
        server_version=f"{major}.0",
        odoo_major=major,
        installed_modules=[{"name": "sale", "state": "installed"}],
    )


def _graph() -> SchemaGraph:
    return SchemaGraph(ReadPlane(_SaleViewTables()))


def _packet(*, major: int = 19, client: FakeSchemaClient | None = None):
    return build_schema_packet(
        _connection(major=major),
        models=["sale.order"],
        schema_client=client or _sale_client(),
        schema_graph=_graph(),
    )


def test_sale_order_packet_lists_partner_id_and_form_siblings_in_arch_order() -> None:
    packet = _packet()
    sale = packet.models["sale.order"]
    assert sale.views["form"] == ("partner_id", "partner_invoice_id", "date_order")
    assert "partner_id" in sale.fields
    assert sale.fields["partner_id"].relation == "res.partner"


def test_field_not_on_the_model_is_absent() -> None:
    packet = _packet()
    sale = packet.models["sale.order"]
    assert "x_not_on_sale" not in sale.fields
    assert "x_not_on_sale" not in sale.views["form"]


def test_method_absent_from_version_table_for_major_is_absent() -> None:
    packet = _packet(major=17)
    sale = packet.models["sale.order"]
    assert "formatted_read_group" not in sale.methods
    assert "action_confirm" in sale.methods


def test_stale_catalog_yields_empty_packet_not_stale_yes() -> None:
    now = time.time()
    draft = {
        "_connection_catalog": {
            "available_models": ["sale.order"],
            "stock": [{"model": "sale.order"}],
            "installed_modules": ["sale"],
            "loaded_at": now - SCHEMA_CATALOG_TTL_S - 10,
        },
        "_schema_fields": {
            "sale.order": {
                "partner_id": {"type": "many2one", "relation": "res.partner"},
            }
        },
        "_schema_client": _sale_client(),
    }
    packet = build_schema_packet(
        _connection(),
        models=["sale.order"],
        draft=draft,
        schema_client=_sale_client(),
        schema_graph=_graph(),
        now=now,
    )
    assert packet.is_empty()
    assert packet.models == {}
    assert "partner_id" not in packet.as_dict().get("models", {})


def test_no_connection_raises_and_does_not_guess_community_defaults() -> None:
    with pytest.raises(ConnectionRequiredError, match="connection"):
        build_schema_packet(None, models=["sale.order"])
    with pytest.raises(ConnectionRequiredError):
        build_schema_packet("", models=["sale.order"])
