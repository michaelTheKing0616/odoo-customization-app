"""Odoo 20 version table, list root, JSON-2 default, and MCP absence."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable
from unittest.mock import patch
from urllib.parse import unquote
from urllib.request import Request, urlopen
from xmlrpc.client import Fault, ServerProxy

import pytest

from odoo_client import ConnectionConfig, OdooClient
from odoo_client.client import OdooClientError
from odoo_client.compat.registry import parse_major
from odoo_client.transport.json2 import Json2TransportError
from odoo_client.compat.adapters.views_v20 import list_arch_root, normalize_view_mode
from odoo_client.compat.version_table import (
    DIFFERENCES,
    V_ROW_KEYS,
    VersionFactUnavailable,
    difference,
    native_mcp_present,
    require_present,
)

# (V-id, older major) — older value is whatever the card encoded for that major.
_FAKE_ROW_CASES = [
    ("V01", 16),
    ("V02", 16),
    ("V03", 16),
    ("V04", 19),
    ("V05", 17),
    ("V06", 16),
    ("V07", 17),
    ("V08", 18),
    ("V09", 18),
    ("V10", 17),
    ("V11", 17),
    ("V12", 17),
    ("V13", 18),
    ("V14", 18),
    ("V15", 17),
    ("V16", 19),
    ("V17", 18),
    ("V18", 19),
    ("V19", 19),
    ("V20", 18),
    ("V21", 18),
    ("V22", 19),
    ("V23", 16),
    ("V24", 18),
    ("V25", 19),
    ("V26", 16),
    ("V27", 19),
    ("V28", 16),
    ("V29", 16),
    ("V30", 16),
    ("V31", 18),
    ("V32", 19),
]


def test_every_listed_difference_resolves() -> None:
    assert len(V_ROW_KEYS) == 32
    assert set(V_ROW_KEYS) == {f"V{i:02d}" for i in range(1, 33)}
    for v_id, area in V_ROW_KEYS.items():
        assert area in DIFFERENCES, v_id
        assert 20 in DIFFERENCES[area], v_id
    assert difference("access_model", 20) == "ir.access"
    assert difference("record_rule_model", 20) == "absent"
    assert difference("record_rule_model", 19) == "ir.rule"
    assert difference("name_search_kw", 20) == "domain"
    assert difference("name_search_kw", 17) == "args"
    assert difference("db_service", 20) == "removed"
    assert difference("json2_default", 20) == "default"
    assert difference("company_type", 20) == "removed"
    assert difference("pricelist_types", 20) == "fixed/discount/markup"
    assert difference("read_group", 20) == "aggregates and tuples"
    assert difference("user_groups_field", 19) == "group_ids"


@pytest.mark.parametrize("v_id,older_major", _FAKE_ROW_CASES, ids=[c[0] for c in _FAKE_ROW_CASES])
def test_fake_version_row(v_id: str, older_major: int) -> None:
    area = V_ROW_KEYS[v_id]
    row = DIFFERENCES[area]
    assert 20 in row
    assert older_major in row
    assert difference(area, 20) == row[20]
    assert difference(area, older_major) == row[older_major]
    assert difference(area, 20) != ""


def test_v25_company_type_on_20_fails_with_named_message() -> None:
    assert difference("company_type", 20) == "removed"
    assert difference("company_type", 19) == "present"
    with pytest.raises(VersionFactUnavailable, match="company_type is removed on Odoo 20") as caught:
        require_present("company_type", 20)
    assert not isinstance(caught.value, KeyError)


def test_removed_or_absent_on_20_does_not_fall_back_to_19() -> None:
    assert difference("company_type", 20) == "removed"
    assert difference("partner_mobile", 20) == "absent from base"
    assert difference("uom_po", 20) == "removed"
    assert difference("bom_consumption", 20) == "removed"
    assert difference("return_wizard", 20) == "removed"
    assert difference("tracking_values_model", 20) == "removed"
    assert difference("record_rule_model", 20) == "absent"
    assert difference("db_service", 20) == "removed"
    assert difference("cron_numbercall", 20) == "removed"
    assert difference("uom_categories_packaging", 20) == "removed"


def _env_json2_path() -> Path | None:
    starts = [Path(__file__).resolve(), Path.cwd().resolve()]
    seen: set[Path] = set()
    for start in starts:
        for parent in (start, *start.parents):
            candidate = parent / ".env.json2"
            if candidate in seen:
                continue
            seen.add(candidate)
            if candidate.is_file():
                return candidate
    return None


def _parse_env_file(path: Path) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        parsed[key.strip()] = value.strip().strip('"').strip("'")
    return parsed


def _scrub(text: str, secret: str) -> str:
    if secret and secret in text:
        return text.replace(secret, "[redacted]")
    return text


class _LiveTip:
    """Read-only cache. The API key stays off assertion messages."""

    def __init__(self, client: OdooClient, server_version: str, secret: str) -> None:
        self.client = client
        self.server_version = server_version
        self._secret = secret
        self._fields: dict[str, dict[str, Any]] = {}
        self._models: dict[str, bool] = {}

    def scrub(self, text: str) -> str:
        return _scrub(text, self._secret)

    def model_exists(self, model: str) -> bool:
        if model not in self._models:
            rows = self.client.execute_kw(
                "ir.model",
                "search_read",
                [[("model", "=", model)]],
                {"fields": ["id"], "limit": 1},
            )
            self._models[model] = bool(rows)
        return self._models[model]

    def fields(self, model: str) -> dict[str, Any]:
        if model not in self._fields:
            try:
                payload = self.client.execute_kw(
                    model,
                    "fields_get",
                    [],
                    {"attributes": ["type", "selection"]},
                )
            except OdooClientError as exc:
                raise AssertionError(self.scrub(str(exc))) from None
            if not isinstance(payload, dict):
                raise AssertionError(f"{model} fields_get did not return a mapping")
            self._fields[model] = payload
        return self._fields[model]

    def has_field(self, model: str, name: str) -> bool:
        return name in self.fields(model)

    def selection_keys(self, model: str, name: str) -> list[str]:
        meta = self.fields(model).get(name)
        if not isinstance(meta, dict):
            raise AssertionError(f"{model}.{name} is absent")
        selection = meta.get("selection")
        if not isinstance(selection, list):
            raise AssertionError(f"{model}.{name} has no selection")
        keys: list[str] = []
        for item in selection:
            if isinstance(item, (list, tuple)) and item:
                keys.append(str(item[0]))
            else:
                keys.append(str(item))
        return keys

    def require_model(self, model: str) -> None:
        if not self.model_exists(model):
            raise AssertionError(f"{model} is not in ir.model")

    def require_field(self, model: str, name: str) -> None:
        self.require_model(model)
        if name not in self.fields(model):
            raise AssertionError(f"{model}.{name} is absent")

    def require_absent_field(self, model: str, name: str) -> None:
        self.require_model(model)
        if name in self.fields(model):
            raise AssertionError(f"{model}.{name} is still present")

    def require_absent_model(self, model: str) -> None:
        if self.model_exists(model):
            raise AssertionError(f"{model} is still in ir.model")


def _concrete_fact(area: str) -> str:
    """Resolve a 20 ``same`` / ``same as N`` label to the earlier concrete fact."""
    fact = difference(area, 20)
    if fact == "same":
        for major in (19, 18, 17, 16):
            earlier = DIFFERENCES[area].get(major)
            if earlier and earlier != "same":
                return earlier
        raise AssertionError(f"{area} on 20 says same but has no earlier fact")
    if fact.startswith("same as "):
        major = int(fact.rsplit(" ", 1)[-1])
        return difference(area, major)
    return fact


def _slash_tokens(fact: str) -> list[str]:
    return [part.strip() for part in fact.split("/") if part.strip()]


_CHECKS: dict[str, Callable[[_LiveTip], None]] = {}


def _check(v_id: str) -> Callable[[Callable[[_LiveTip], None]], Callable[[_LiveTip], None]]:
    def decorate(fn: Callable[[_LiveTip], None]) -> Callable[[_LiveTip], None]:
        _CHECKS[v_id] = fn
        return fn

    return decorate


@_check("V01")
def _v01_routes(tip: _LiveTip) -> None:
    fact = difference("routes_model", 20)
    tip.require_model(fact)


@_check("V02")
def _v02_account_type(tip: _LiveTip) -> None:
    fact = difference("account_type", 20)
    tip.require_field("account.account", fact)


@_check("V03")
def _v03_account_company(tip: _LiveTip) -> None:
    fact = difference("account_company", 20)
    tip.require_field("account.account", fact)
    tip.require_absent_field("account.account", "company_id")


@_check("V04")
def _v04_analytic(tip: _LiveTip) -> None:
    fact = _concrete_fact("analytic")
    if "analytic_distribution" not in fact or "plan" not in fact:
        raise AssertionError(f"V04 concrete fact {fact!r} is not plans + analytic_distribution")
    tip.require_model("account.analytic.plan")
    tip.require_field("account.move.line", "analytic_distribution")


@_check("V05")
def _v05_tax_repartition(tip: _LiveTip) -> None:
    fact = _concrete_fact("tax_repartition")
    if "repartition_line_ids" not in fact or "document_type" not in fact:
        raise AssertionError(f"V05 concrete fact {fact!r} is not repartition_line_ids + document_type")
    tip.require_field("account.tax", "repartition_line_ids")
    tip.require_field("account.tax.repartition.line", "document_type")


@_check("V06")
def _v06_tax_included(tip: _LiveTip) -> None:
    fact = difference("tax_included", 20)
    if "override" not in fact or "document-level" not in fact:
        raise AssertionError(f"V06 fact {fact!r} is not an override plus a document-level switch")
    tip.require_field("account.tax", "price_include_override")
    keys = set(tip.selection_keys("account.move", "company_price_include"))
    if not {"tax_included", "tax_excluded"} <= keys:
        raise AssertionError(
            "account.move.company_price_include is not the document-level tax switch"
        )


@_check("V07")
def _v07_payment_term(tip: _LiveTip) -> None:
    fact = difference("payment_term_lines", 20)
    tip.require_field("account.payment.term.line", fact)


@_check("V08")
def _v08_product_type(tip: _LiveTip) -> None:
    fact = _concrete_fact("product_type")
    if "type" not in fact or "is_storable" not in fact:
        raise AssertionError(f"V08 concrete fact {fact!r} is not type + is_storable")
    tip.require_field("product.template", "type")
    tip.require_field("product.template", "is_storable")


@_check("V09")
def _v09_uom_po(tip: _LiveTip) -> None:
    fact = difference("uom_po", 20)
    if fact != "removed":
        raise AssertionError(f"V09 fact {fact!r} is not removed")
    tip.require_absent_field("product.template", "uom_po_id")


@_check("V10")
def _v10_stock_done(tip: _LiveTip) -> None:
    fact = _concrete_fact("stock_done_qty")
    if "quantity" not in fact or "picked" not in fact:
        raise AssertionError(f"V10 concrete fact {fact!r} is not quantity + picked")
    tip.require_field("stock.move", "quantity")
    tip.require_field("stock.move", "picked")


@_check("V11")
def _v11_automation(tip: _LiveTip) -> None:
    fact = _concrete_fact("automation")
    if "ir.actions.server" not in fact:
        raise AssertionError(f"V11 concrete fact {fact!r} is not a separate ir.actions.server")
    tip.require_model("base.automation")
    tip.require_model("ir.actions.server")
    tip.require_field("base.automation", "action_server_ids")


@_check("V12")
def _v12_cron_numbercall(tip: _LiveTip) -> None:
    fact = difference("cron_numbercall", 20)
    if fact != "removed":
        raise AssertionError(f"V12 fact {fact!r} is not removed")
    tip.require_absent_field("ir.cron", "numbercall")


@_check("V13")
def _v13_user_groups(tip: _LiveTip) -> None:
    fact = difference("user_groups_field", 20)
    tip.require_field("res.users", fact)
    tip.require_absent_field("res.users", "groups_id")


def _json2_call(tip: _LiveTip, model: str, method: str, body: dict[str, Any]) -> Any:
    transport = tip.client._json2
    if transport is None:
        raise AssertionError("JSON-2 transport is not connected")
    try:
        return transport.call(model, method, body)
    except Json2TransportError as exc:
        raise AssertionError(tip.scrub(f"{method} failed: {exc}")) from None


@_check("V14")
def _v14_name_search(tip: _LiveTip) -> None:
    fact = difference("name_search_kw", 20)
    if fact != "domain":
        raise AssertionError(f"V14 fact {fact!r} is not domain")
    found = _json2_call(
        tip,
        "res.partner",
        "name_search",
        {"name": "", "domain": [["id", "=", 0]], "limit": 1},
    )
    if not isinstance(found, list):
        raise AssertionError("name_search domain did not return a list")
    transport = tip.client._json2
    assert transport is not None
    try:
        transport.call(
            "res.partner",
            "name_search",
            {"name": "", "args": [["id", "=", 0]], "limit": 1},
        )
    except Json2TransportError as exc:
        message = tip.scrub(str(exc))
        if exc.status != 422 or "args" not in message:
            raise AssertionError("name_search args was not rejected as an unknown keyword") from None
    else:
        raise AssertionError("name_search still accepts args")


@_check("V15")
def _v15_web_urls(tip: _LiveTip) -> None:
    fact = difference("web_urls", 20)
    if "/odoo/" not in fact:
        raise AssertionError(f"V15 fact {fact!r} is not /odoo/...")
    transport = tip.client._json2
    if transport is None:
        raise AssertionError("JSON-2 transport is not connected")
    request = Request(transport.base_url.rstrip("/") + "/odoo", method="GET")
    with urlopen(request, timeout=30) as response:
        final = unquote(response.geturl())
        status = getattr(response, "status", 200)
    if status != 200 or "/odoo" not in final:
        raise AssertionError("the live web client did not serve /odoo/")


@_check("V16")
def _v16_api(tip: _LiveTip) -> None:
    fact = difference("api", 20)
    if "JSON-2" not in fact or "removed" not in fact:
        raise AssertionError(f"V16 fact {fact!r} is not JSON-2 with db removed")
    if parse_major(tip.server_version) != 20:
        raise AssertionError(f"live version {tip.server_version!r} is not major 20")
    if tip.client._rpc_protocol != "json2":
        raise AssertionError("the tip did not connect with JSON-2")
    transport = tip.client._json2
    if transport is None:
        raise AssertionError("JSON-2 transport is not connected")
    proxy = ServerProxy(transport.base_url.rstrip("/") + "/xmlrpc/2/db", allow_none=True)
    try:
        proxy.list()
    except Fault as exc:
        if "Invalid service name: db" not in (exc.faultString or ""):
            raise AssertionError("db service fault did not name db as an invalid service") from None
    else:
        raise AssertionError("db service still answers")


@_check("V17")
def _v17_fiscal_position(tip: _LiveTip) -> None:
    fact = difference("fiscal_position_tax_map", 20)
    if fact != "on the tax":
        raise AssertionError(f"V17 fact {fact!r} is not on the tax")
    tip.require_absent_model("account.fiscal.position.tax")
    tip.require_field("account.tax", "fiscal_position_ids")


@_check("V18")
def _v18_access(tip: _LiveTip) -> None:
    fact = difference("access", 20)
    tip.require_model(fact)
    tip.require_absent_model("ir.model.access")
    tip.require_absent_model("ir.rule")


@_check("V19")
def _v19_account_groups(tip: _LiveTip) -> None:
    fact = difference("account_groups", 20)
    if "parent_id" not in fact or "gone" not in fact:
        raise AssertionError(f"V19 fact {fact!r} is not parent_id with the group model gone")
    tip.require_field("account.account", "parent_id")
    tip.require_absent_model("account.group")


@_check("V20")
def _v20_root_categories(tip: _LiveTip) -> None:
    fact = _concrete_fact("root_product_category")
    expected = {token.strip().casefold() for token in _slash_tokens(fact)}
    if expected != {"goods", "services", "expenses"}:
        raise AssertionError(f"V20 concrete fact {fact!r} is not Goods/Services/Expenses")
    rows = tip.client.execute_kw(
        "product.category",
        "search_read",
        [[("parent_id", "=", False)]],
        {"fields": ["name"], "limit": 50},
    )
    names = {str(row.get("name") or "").casefold() for row in rows}
    if not expected <= names:
        raise AssertionError("root product categories are not Goods, Services, and Expenses")
    xmlids = tip.client.execute_kw(
        "ir.model.data",
        "search_read",
        [[("module", "=", "product"), ("model", "=", "product.category"), ("name", "=", "product_category_all")]],
        {"fields": ["name"], "limit": 1},
    )
    if xmlids:
        raise AssertionError("product.product_category_all is still present")


@_check("V21")
def _v21_uom_packaging(tip: _LiveTip) -> None:
    fact = difference("uom_categories_packaging", 20)
    if fact != "removed":
        raise AssertionError(f"V21 fact {fact!r} is not removed")
    tip.require_model("uom.uom")
    tip.require_model("product.template")
    tip.require_absent_model("uom.category")
    tip.require_absent_model("product.packaging")


@_check("V22")
def _v22_pricelist(tip: _LiveTip) -> None:
    fact = difference("pricelist_types", 20)
    expected = set(_slash_tokens(fact))
    keys = set(tip.selection_keys("product.pricelist.item", "compute_price"))
    if keys != expected:
        raise AssertionError("product.pricelist.item.compute_price does not match the 20 pricelist types")


@_check("V23")
def _v23_report_layouts(tip: _LiveTip) -> None:
    fact = difference("report_layouts", 20)
    layouts, separator, field_name = fact.partition("+")
    if not separator or "report_tables_id" not in field_name:
        raise AssertionError(f"V23 fact {fact!r} has no report_tables_id")
    tokens = [part.strip(" ,") for part in layouts.split(",") if part.strip(" ,")]
    xml_names = [f"external_layout_{token}" for token in tokens]
    rows = tip.client.execute_kw(
        "ir.model.data",
        "search_read",
        [[("module", "=", "web"), ("model", "=", "ir.ui.view"), ("name", "in", xml_names)]],
        {"fields": ["name"], "limit": len(xml_names)},
    )
    found = {row.get("name") for row in rows}
    missing = [name for name in xml_names if name not in found]
    if missing:
        raise AssertionError("web external layouts missing: " + ", ".join(missing))
    tip.require_field("res.company", "report_tables_id")


@_check("V24")
def _v24_payment_state(tip: _LiveTip) -> None:
    fact = difference("account_payment_state", 20)
    expected = set(_slash_tokens(fact))
    keys = set(tip.selection_keys("account.payment", "state"))
    if not expected <= keys or "in_process" in keys:
        raise AssertionError("account.payment.state does not match draft/paid/reconciled")


@_check("V25")
def _v25_company_type(tip: _LiveTip) -> None:
    fact = difference("company_type", 20)
    if fact != "removed":
        raise AssertionError(f"V25 fact {fact!r} is not removed")
    tip.require_absent_field("res.partner", "company_type")


@_check("V26")
def _v26_partner_mobile(tip: _LiveTip) -> None:
    fact = difference("partner_mobile", 20)
    if not fact.startswith("absent"):
        raise AssertionError(f"V26 fact {fact!r} is not absent from base")
    for name in ("mobile", "title"):
        rows = tip.client.execute_kw(
            "ir.model.fields",
            "search_read",
            [[("model", "=", "res.partner"), ("name", "=", name)]],
            {"fields": ["id"], "limit": 1},
        )
        if not rows:
            continue
        owners = tip.client.execute_kw(
            "ir.model.data",
            "search_read",
            [[("model", "=", "ir.model.fields"), ("res_id", "=", rows[0]["id"])]],
            {"fields": ["module"], "limit": 5},
        )
        if any(row.get("module") == "base" for row in owners) or not owners:
            raise AssertionError(f"res.partner.{name} is still defined by base")


@_check("V27")
def _v27_company_registry(tip: _LiveTip) -> None:
    fact = difference("company_registry", 20)
    if "additional_identifiers" not in fact or "JSON" not in fact:
        raise AssertionError(f"V27 fact {fact!r} is not additional_identifiers JSON")
    tip.require_absent_field("res.company", "company_registry")
    tip.require_absent_field("res.partner", "company_registry")
    meta = tip.fields("res.company").get("additional_identifiers")
    if not isinstance(meta, dict) or meta.get("type") != "json":
        raise AssertionError("res.company.additional_identifiers is not a JSON field")


@_check("V28")
def _v28_bom_consumption(tip: _LiveTip) -> None:
    fact = difference("bom_consumption", 20)
    if fact != "removed":
        raise AssertionError(f"V28 fact {fact!r} is not removed")
    tip.require_absent_field("mrp.bom", "consumption")


@_check("V29")
def _v29_return_wizard(tip: _LiveTip) -> None:
    fact = difference("return_wizard", 20)
    if fact != "removed":
        raise AssertionError(f"V29 fact {fact!r} is not removed")
    tip.require_model("stock.move")
    tip.require_absent_model("stock.return.picking")


@_check("V30")
def _v30_tracking_values(tip: _LiveTip) -> None:
    fact = difference("tracking_values_model", 20)
    if fact != "removed":
        raise AssertionError(f"V30 fact {fact!r} is not removed")
    tip.require_model("res.partner")
    tip.require_absent_model("mail.tracking.value")


@_check("V31")
def _v31_read_group(tip: _LiveTip) -> None:
    fact = difference("read_group", 20)
    if "aggregates" not in fact or "tuple" not in fact:
        raise AssertionError(f"V31 fact {fact!r} is not aggregates and tuples")
    # Call JSON-2 directly. OdooClient.execute_kw rewrites read_group to
    # formatted_read_group, which returns dicts rather than pairs.
    rows = _json2_call(
        tip,
        "ir.model",
        "read_group",
        {
            "domain": [["model", "=", "res.partner"]],
            "groupby": ["transient"],
            "aggregates": ["id:count"],
        },
    )
    if not isinstance(rows, list) or not rows:
        raise AssertionError("read_group aggregates did not return grouped rows")
    if any(not isinstance(row, (list, tuple)) or len(row) != 2 for row in rows):
        raise AssertionError("read_group aggregates did not return pairs")
    transport = tip.client._json2
    assert transport is not None
    try:
        transport.call(
            "ir.model",
            "read_group",
            {"domain": [["id", "=", 0]], "groupby": ["transient"], "fields": ["id"]},
        )
    except Json2TransportError as exc:
        message = tip.scrub(str(exc))
        if exc.status != 422 or "fields" not in message:
            raise AssertionError("read_group fields keyword was not rejected") from None
    else:
        raise AssertionError("read_group still accepts fields")


@_check("V32")
def _v32_user_role(tip: _LiveTip) -> None:
    fact = difference("user_role", 20)
    tokens = [part.strip().casefold() for part in fact.split("/") if part.strip()]
    if tokens != ["light", "regular", "system"]:
        raise AssertionError(f"V32 fact {fact!r} is not light / regular / system")
    keys = [key.casefold() for key in tip.selection_keys("res.users", "role")]
    missing = [token for token in tokens if not any(token in key for key in keys)]
    if missing:
        raise AssertionError("res.users.role is missing " + ", ".join(missing))


def test_live_checks_cover_every_v_row() -> None:
    assert set(_CHECKS) == set(V_ROW_KEYS)


@pytest.fixture(scope="module")
def live_tip() -> _LiveTip:
    path = _env_json2_path()
    if path is None:
        pytest.skip(".env.json2 is absent")
    env = _parse_env_file(path)
    url = env.get("JSON2_TIP_URL", "")
    database = env.get("JSON2_TIP_DB", "")
    api_key = env.get("JSON2_TIP_API_KEY", "")
    if not url or not database or not api_key:
        pytest.fail("JSON2 tip URL, database, or API key is missing from .env.json2")
    logging.getLogger("odoo_client").setLevel(logging.CRITICAL)
    client = OdooClient(
        ConnectionConfig(
            url=url,
            db=database,
            username="api",
            password=api_key,
            rpc_protocol="json2",
            timeout=60,
        )
    )
    try:
        client.connect()
        version = client._common.version()
    except Exception as exc:
        pytest.fail(_scrub(str(exc), api_key))
    server_version = str((version or {}).get("server_version") or "")
    if parse_major(server_version) != 20:
        pytest.fail(f"tip server_version {server_version!r} is not major 20")
    return _LiveTip(client, server_version, api_key)


@pytest.mark.parametrize("v_id", list(V_ROW_KEYS), ids=list(V_ROW_KEYS))
def test_live_version_row_matches_tip(v_id: str, live_tip: _LiveTip) -> None:
    checker = _CHECKS.get(v_id)
    if checker is None:
        pytest.fail(f"{v_id} has no live check")
    try:
        checker(live_tip)
    except Exception as exc:
        pytest.fail(live_tip.scrub(str(exc)))


def test_odoo20_list_root_is_list_not_tree() -> None:
    assert list_arch_root("list") == "list"
    assert list_arch_root("tree") == "list"
    assert normalize_view_mode("tree,form") == "list,form"


def test_major_20_auto_selects_json2_even_when_local() -> None:
    client = OdooClient(
        ConnectionConfig(url="http://127.0.0.1:9", db="t", username="u", password="p")
    )
    assert client._should_use_json2(major=20, hosting="local") is True
    assert client._should_use_json2(major=19, hosting="local") is False
    assert client._should_use_json2(major=19, hosting="online") is True


def test_major_20_json2_password_auth_error_does_not_suggest_auto_xmlrpc() -> None:
    client = OdooClient(
        ConnectionConfig(url="http://127.0.0.1:9", db="t", username="u", password="p")
    )
    with patch(
        "odoo_client.client.Json2Transport.context_get",
        side_effect=Json2TransportError(
            "Invalid apikey", status=401, body={"message": "Invalid apikey"}
        ),
    ):
        with pytest.raises(OdooClientError) as caught:
            client._connect_json2(major=20)
    msg = str(caught.value)
    assert "JSON-2 requires an API key" in msg
    assert "Odoo 19" not in msg
    assert "non-Online" not in msg
    assert "rpc_protocol=xmlrpc" in msg


def test_community_without_ai_modules_has_no_native_mcp() -> None:
    assert native_mcp_present(["sale", "account"]) is False
    assert native_mcp_present(["ai_agent"]) is True
