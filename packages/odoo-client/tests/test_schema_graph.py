"""Schema graph reads through the read plane and does not invent usages."""

from __future__ import annotations

import threading

import pytest

from odoo_client.read_plane import ReadPlane, ReadPlaneError
from odoo_client.schema_graph import SchemaGraph, xpath_matches


class _Tables:
    def __init__(self) -> None:
        self.fields = {
            "sale.order": {
                "partner_id": {"type": "many2one", "relation": "res.partner", "string": "Customer"},
                "amount_total": {"type": "float", "string": "Total"},
                "partner_identity": {"type": "char", "string": "Identity"},
            }
        }
        self.rows = {
            "ir.ui.view": [
                {
                    "id": 1,
                    "name": "sale form",
                    "model": "sale.order",
                    "arch_db": '<form><field name="partner_id"/></form>',
                },
                {
                    "id": 9,
                    "name": "identity",
                    "model": "sale.order",
                    "arch_db": '<form><field name="partner_identity"/></form>',
                },
                {
                    "id": 10,
                    "name": "conflict",
                    "model": "sale.order",
                    "model_name": "crm.lead",
                    "arch_db": '<form><field name="partner_id"/></form>',
                },
            ],
            "base.automation": [
                {
                    "id": 2,
                    "name": "big orders",
                    "model": "sale.order",
                    "filter_domain": "[('amount_total', '>', 1)]",
                }
            ],
            "ir.rule": [],
            "ir.actions.server": [
                {
                    "id": 3,
                    "name": "other app",
                    "model_name": "crm.lead",
                    "code": "record.partner_id",
                }
            ],
            "mail.template": [],
            "ir.filters": [],
        }

    def __call__(self, model: str, method: str, args: list, kwargs: dict):
        if method == "fields_get":
            return self.fields[model]
        if method == "get_view":
            return {"arch": '<form><field name="partner_id"/></form>'}
        if method == "search_read":
            limit = int(kwargs.get("limit") or 0)
            rows = list(self.rows.get(model, []))
            return rows[:limit] if limit else rows
        raise AssertionError(method)


def test_describe_and_usages_stay_on_real_rows() -> None:
    graph = SchemaGraph(ReadPlane(_Tables()))
    described = graph.describe_model("sale.order")
    assert described["relations"] == {"partner_id": "res.partner"}
    partner_hits = graph.find_usages("sale.order", "partner_id")
    assert [hit["id"] for hit in partner_hits] == ["1"]
    assert graph.find_usages("sale.order", "partner_identity")[0]["id"] == "9"
    assert graph.find_usages("sale.order", "amount_total")[0]["model"] == "base.automation"
    assert graph.find_usages("crm.lead", "partner_id")[0]["model"] == "ir.actions.server"
    assert xpath_matches(graph.combined_arch("sale.order"), "field[@name='partner_id']") == 1


def test_xpath_counts_and_rejects_entities() -> None:
    arch = '<form><field name="partner_id"/><field name="partner_id"/></form>'
    assert xpath_matches(arch, "field[@name='partner_id']") == 2
    assert xpath_matches('<form><field name="name"/></form>', "field[@name='partner_id']") == 0
    with pytest.raises(ValueError):
        xpath_matches('<!DOCTYPE form [<!ENTITY x "y">]><form/>', "form")


def test_search_read_caps_at_200() -> None:
    tables = _Tables()
    tables.rows["ir.filters"] = [{"id": index, "name": "f", "model": "sale.order", "domain": "[]"} for index in range(250)]
    page = SchemaGraph(ReadPlane(tables)).search_read("ir.filters", [], ["id"])
    assert len(page["rows"]) == 200
    assert page["truncated"] is True


def test_read_plane_allows_only_two_calls_in_flight() -> None:
    entered = threading.Semaphore(0)
    release = threading.Event()

    seen: list[str] = []

    def transport(model: str, method: str, args: list, kwargs: dict) -> list:
        seen.append(method)
        entered.release()
        assert release.wait(timeout=2)
        return []

    plane = ReadPlane(transport)

    def run() -> None:
        plane.call("sale.order", "search_read")

    first = threading.Thread(target=run)
    second = threading.Thread(target=run)
    first.start()
    second.start()
    assert entered.acquire(timeout=2)
    assert entered.acquire(timeout=2)
    with pytest.raises(ReadPlaneError):
        plane.call("sale.order", "fields_get")
    assert seen == ["search_read", "search_read"]
    release.set()
    first.join(timeout=2)
    second.join(timeout=2)
    assert plane.call("sale.order", "search_count") == []


def _messy_fields() -> dict[str, dict[str, str]]:
    fields = {
        f"x_messy_{index:03d}": {"type": "char", "string": f"Messy {index}"}
        for index in range(1, 151)
    }
    fields["partner_id"] = {"type": "many2one", "relation": "res.partner", "string": "Partner"}
    return fields


class _MessyTables:
    """In-memory messy_client slice. Not a live database."""

    def __init__(self) -> None:
        self.fields = {"x.messy": _messy_fields()}
        views = []
        for index in range(1, 51):
            views.append(
                {
                    "id": index,
                    "name": f"messy form {index}",
                    "model": "x.messy",
                    "arch_db": '<form><field name="x_messy_001"/></form>',
                }
            )
        views.append(
            {
                "id": 90,
                "name": "substring trap",
                "model": "x.messy",
                "arch_db": '<form><field name="x_messy_0010"/></form>',
            }
        )
        views.append(
            {
                "id": 91,
                "name": "other model",
                "model": "crm.lead",
                "arch_db": '<form><field name="x_messy_001"/></form>',
            }
        )
        self.rows = {
            "ir.ui.view": views,
            "base.automation": [
                {
                    "id": 7,
                    "name": "messy rule",
                    "model_name": "x.messy",
                    "filter_domain": "[('x_messy_001', '!=', False)]",
                }
            ],
            "ir.rule": [],
            "ir.actions.server": [],
            "mail.template": [],
            "ir.filters": [
                {"id": index, "name": "pad", "model_id": [1, "x.messy"], "domain": "[]"}
                for index in range(1, 12)
            ],
        }

    def __call__(self, model: str, method: str, args: list, kwargs: dict):
        if method == "fields_get":
            return self.fields[model]
        if method == "search_read":
            limit = int(kwargs.get("limit") or 0)
            rows = list(self.rows.get(model, []))
            return rows[:limit] if limit else rows
        raise AssertionError(method)


def test_messy_client_graph_caps_sample_and_keeps_a_stable_fingerprint() -> None:
    graph = SchemaGraph(ReadPlane(_MessyTables()))
    first = graph.describe_model("x.messy")
    second = graph.describe_model("x.messy")
    assert len(first["fields"]) == 151
    assert first["fields"][0] == "partner_id"
    assert first["relations"] == {"partner_id": "res.partner"}
    assert first["fingerprint"] == second["fingerprint"]
    sample = graph.sample_rows("ir.filters", [], ["id"])
    assert len(sample) == 5
    assert [row["id"] for row in sample] == [1, 2, 3, 4, 5]


def test_find_usages_precision_and_recall_on_a_labeled_set() -> None:
    """Labels are the rows that truly mention x_messy_001 on x.messy.

    The substring trap x_messy_0010 and the crm.lead row are true negatives.
    """
    labeled_true = {("ir.ui.view", str(index)) for index in range(1, 51)}
    labeled_true.add(("base.automation", "7"))
    hits = SchemaGraph(ReadPlane(_MessyTables())).find_usages("x.messy", "x_messy_001")
    predicted = {(hit["model"], hit["id"]) for hit in hits}
    true_positive = predicted & labeled_true
    false_positive = predicted - labeled_true
    false_negative = labeled_true - predicted
    precision = len(true_positive) / (len(true_positive) + len(false_positive))
    recall = len(true_positive) / (len(true_positive) + len(false_negative))
    assert precision >= 0.98, precision
    assert recall >= 0.95, recall
    assert ("ir.ui.view", "90") not in predicted
    assert ("ir.ui.view", "91") not in predicted
