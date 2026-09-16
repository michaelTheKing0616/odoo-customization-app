"""Missing inherit hosts map to stock Community apps — not a new x_* app."""

from __future__ import annotations

from app.ai_host_install import (
    community_app_for_model,
    host_install_offers,
    model_from_finding,
)
from app.ai_option_a_author import seed_option_a_authored
from app.ai_option_a_gate import evaluate_authoring_gate
from app.ai_generation_engine import classify_generation
from app.ai_option_a_policy import rpc_verify_findings

MARKUP = (
    "The Client wants a Mark-up line added to every Sale. The Markup is calculated "
    "as a percentage of every sale made. A Withholding Tax, on the markup is to be "
    "calculated as well (if possible). The WT is made on the Markup only, and only "
    "for Sales, NOT Purchases."
)


class _MissingSaleClient:
    def execute_kw(self, model: str, method: str, args, kwargs=None):  # noqa: ANN001
        if model == "ir.model" and method == "search_count":
            domain = args[0] if args else []
            wanted = ""
            for term in domain:
                if isinstance(term, (list, tuple)) and term and term[0] == "model":
                    wanted = str(term[2])
            if wanted in {"sale.order", "sale.order.line"}:
                return 0
            return 1
        return 0


def test_sale_line_maps_to_sales_app() -> None:
    assert community_app_for_model("sale.order") == {"module": "sale", "label": "Sales"}
    assert community_app_for_model("sale.order.line") == {"module": "sale", "label": "Sales"}
    assert community_app_for_model("x_ticket") is None
    assert community_app_for_model("res.partner") is None


def test_pos_and_prefix_fallback_map_to_installable_apps() -> None:
    assert community_app_for_model("pos.config") == {
        "module": "point_of_sale",
        "label": "Point of Sale",
    }
    assert community_app_for_model("fleet.vehicle") == {"module": "fleet", "label": "Fleet"}
    assert community_app_for_model("maintenance.request") == {
        "module": "maintenance",
        "label": "Maintenance",
    }
    # Unknown snake_case prefix still gets an Install CTA.
    assert community_app_for_model("awesome_kit.thing") == {
        "module": "awesome_kit",
        "label": "Awesome Kit",
    }
    assert community_app_for_model("ir.ui.view") is None
    assert community_app_for_model("mail.message") is None


def test_model_missing_findings_group_into_one_sales_offer() -> None:
    offers = host_install_offers(
        [
            {
                "code": "model_missing",
                "message": "Inherit model sale.order is not on this connection.",
                "file": "models",
            },
            {
                "code": "model_missing",
                "message": "Inherit model sale.order.line is not on this connection.",
                "file": "models",
            },
            {
                "code": "tax_xmlid_missing",
                "message": "Tax xmlid l10n_ng.whatever is not on this connection.",
                "file": "data",
            },
        ]
    )
    assert len(offers) == 1
    assert offers[0]["module"] == "sale"
    assert offers[0]["label"] == "Sales"
    assert offers[0]["models"] == ["sale.order", "sale.order.line"]
    assert "custom zip" in offers[0]["message"]


def test_model_from_finding_reads_message() -> None:
    assert (
        model_from_finding(
            {"code": "model_missing", "message": "Inherit model sale.order is not on this connection."}
        )
        == "sale.order"
    )


def test_rpc_verify_stamps_install_module() -> None:
    draft = {
        "custom_code_blocks": [
            {
                "source_file": "models/sale_markup.py",
                "kind": "python",
                "content": (
                    "from odoo import fields, models\n\n"
                    "class SaleOrder(models.Model):\n"
                    "    _inherit = 'sale.order'\n"
                ),
            },
            {
                "source_file": "models/sale_line.py",
                "kind": "python",
                "content": (
                    "from odoo import fields, models\n\n"
                    "class SaleOrderLine(models.Model):\n"
                    "    _inherit = 'sale.order.line'\n"
                ),
            },
        ]
    }
    findings = rpc_verify_findings(draft, _MissingSaleClient())
    missing = [f for f in findings if f.get("code") == "model_missing"]
    assert {f.get("model") for f in missing} == {"sale.order", "sale.order.line"}
    assert all(f.get("install_module") == "sale" for f in missing)
    assert all(f.get("install_label") == "Sales" for f in missing)


def test_authoring_gate_stamps_host_install() -> None:
    draft = seed_option_a_authored(MARKUP, classify_generation(MARKUP))
    draft["custom_code_blocks"] = [
        {
            "source_file": "models/sale_markup.py",
            "kind": "python",
            "content": (
                "from odoo import fields, models\n\n"
                "class SaleOrder(models.Model):\n"
                "    _inherit = 'sale.order'\n"
                "    x_markup_percent = fields.Float(string='Markup %')\n"
            ),
        },
        {
            "source_file": "models/__init__.py",
            "kind": "python",
            "content": "from . import sale_markup\n",
        },
    ]
    payload = evaluate_authoring_gate(draft, client=_MissingSaleClient())
    assert payload["status"] == "fail"
    offers = payload.get("host_install") or []
    assert len(offers) == 1
    assert offers[0]["module"] == "sale"
    assert "sale.order" in offers[0]["models"]
    assert draft["_option_a_authoring"]["host_install"][0]["module"] == "sale"
