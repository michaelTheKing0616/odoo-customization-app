"""Read-only Odoo 20 tip checks for the six drift cells the fake table leaves unknown.

The fake answers in ``odoo_client.compat.drift`` stay unknown. This module records
what the tip returned. A call that does not return an observable payload fails
the cell as unknown.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

import pytest

from odoo_client import ConnectionConfig, OdooClient
from odoo_client.client import OdooClientError
from odoo_client.compat.registry import parse_major

_CELLS = (
    "kanban",
    "name_get",
    "company_dependent_fields",
    "selection_storage",
    "mail_template_syntax",
    "translations",
)


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
        text = text.replace(secret, "[redacted]")
    return re.sub(r"Bearer\s+\S+", "Bearer [redacted]", text)


class _Tip:
    """One read-only JSON-2 session. The API key stays off failure text."""

    def __init__(self, client: OdooClient, secret: str) -> None:
        self.client = client
        self._secret = secret

    def scrub(self, text: str) -> str:
        return _scrub(text, self._secret)

    def call(self, cell: str, model: str, method: str, args: list[Any] | None = None, kwargs: dict[str, Any] | None = None) -> Any:
        try:
            return self.client.execute_kw(model, method, args or [], kwargs or {})
        except Exception as exc:
            pytest.fail(self.scrub(f"{cell} stayed unknown: {exc}"))


@pytest.fixture(scope="module")
def tip() -> _Tip:
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
            write_mode="observer",
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
    if client._rpc_protocol != "json2":
        pytest.fail("tip did not stay on json2")
    return _Tip(client, api_key)


def _guard(tip: _Tip) -> None:
    def _check(fn):  # noqa: ANN001, ANN202
        try:
            fn()
        except Exception as exc:
            pytest.fail(tip.scrub(str(exc)))

    return _check


def test_cells_match_the_unknown_drift_rows() -> None:
    from odoo_client.compat.drift import DRIFT_ROWS, UNKNOWN, drift_answer

    assert set(_CELLS) <= set(DRIFT_ROWS)
    for row in _CELLS:
        assert drift_answer(row, 20) == UNKNOWN


def test_kanban_tip(tip: _Tip) -> None:
    def body() -> None:
        meta = tip.call("kanban", "ir.ui.view", "fields_get", [], {"attributes": ["selection"]})
        type_meta = meta.get("type") if isinstance(meta, dict) else None
        selection = type_meta.get("selection") if isinstance(type_meta, dict) else None
        if not isinstance(selection, list):
            pytest.fail("kanban stayed unknown: ir.ui.view.type has no selection")
        keys = [item[0] if isinstance(item, (list, tuple)) and item else item for item in selection]
        if "kanban" not in keys:
            pytest.fail("kanban stayed unknown: ir.ui.view.type omitted kanban")
        rows = tip.call(
            "kanban",
            "ir.ui.view",
            "search_read",
            [[("type", "=", "kanban"), ("inherit_id", "=", False), ("model", "=", "res.partner")]],
            {"fields": ["type", "model"], "limit": 1},
        )
        if not isinstance(rows, list) or not rows or rows[0].get("type") != "kanban":
            pytest.fail("kanban stayed unknown: no primary res.partner kanban")
        payload = tip.call(
            "kanban",
            "res.partner",
            "get_views",
            [],
            {"views": [[False, "kanban"]], "options": {"toolbar": False}},
        )
        views = payload.get("views") if isinstance(payload, dict) else None
        bucket = views.get("kanban") if isinstance(views, dict) else None
        arch = bucket.get("arch") if isinstance(bucket, dict) else None
        if not isinstance(arch, str) or not arch.startswith("<kanban"):
            pytest.fail("kanban stayed unknown: get_views did not return a kanban arch")
        names = re.findall(r"""t-name=["']([^"']+)["']""", arch)
        if names != ["card"] or "kanban-box" in arch:
            pytest.fail(f"kanban stayed unknown: t-name values were {names!r}")

    _guard(tip)(body)


def test_name_get_tip(tip: _Tip) -> None:
    def body() -> None:
        ids = tip.call("name_get", "res.partner", "search", [[["id", ">", 0]]], {"limit": 1, "order": "id"})
        if not isinstance(ids, list) or not ids:
            pytest.fail("name_get stayed unknown: no res.partner id")
        partner_id = ids[0]
        try:
            tip.client.execute_kw("res.partner", "name_get", [[partner_id]])
        except OdooClientError as exc:
            message = tip.scrub(str(exc))
            if "name_get" not in message or "does not exist" not in message:
                pytest.fail(f"name_get stayed unknown: {message}")
        else:
            pytest.fail("name_get stayed unknown: the method returned instead of missing")
        rows = tip.call("name_get", "res.partner", "read", [[partner_id]], {"fields": ["display_name"]})
        if not isinstance(rows, list) or not rows or not isinstance(rows[0], dict):
            pytest.fail("name_get stayed unknown: display_name read was empty")
        display_name = rows[0].get("display_name")
        if not isinstance(display_name, str) or not display_name.strip():
            pytest.fail("name_get stayed unknown: display_name was not a nonempty string")

    _guard(tip)(body)


def test_company_dependent_fields_tip(tip: _Tip) -> None:
    def body() -> None:
        meta = tip.call(
            "company_dependent_fields",
            "ir.model.fields",
            "fields_get",
            [],
            {"attributes": ["type", "store"]},
        )
        flag = meta.get("company_dependent") if isinstance(meta, dict) else None
        if not isinstance(flag, dict) or flag.get("type") != "boolean" or flag.get("store") is not True:
            pytest.fail("company_dependent_fields stayed unknown: flag metadata was not a stored boolean")
        rows = tip.call(
            "company_dependent_fields",
            "ir.model.fields",
            "search_read",
            [[("model", "=", "res.partner"), ("name", "=", "property_payment_term_id")]],
            {"fields": ["model", "name", "ttype", "company_dependent", "store", "related"], "limit": 1},
        )
        if not isinstance(rows, list) or not rows:
            pytest.fail("company_dependent_fields stayed unknown: property_payment_term_id was absent")
        row = rows[0]
        if (
            row.get("company_dependent") is not True
            or row.get("ttype") != "many2one"
            or row.get("store") is not True
            or row.get("related") is not False
        ):
            pytest.fail("company_dependent_fields stayed unknown: property_payment_term_id metadata differed")
        models = tip.call(
            "company_dependent_fields",
            "ir.model",
            "search_read",
            [[["model", "=", "ir.property"]]],
            {"fields": ["model"], "limit": 1},
        )
        if models != []:
            pytest.fail("company_dependent_fields stayed unknown: ir.property was present")
        partners = tip.call(
            "company_dependent_fields",
            "res.partner",
            "search",
            [[["id", ">", 0]]],
            {"limit": 1, "order": "id"},
        )
        if not isinstance(partners, list) or not partners:
            pytest.fail("company_dependent_fields stayed unknown: no partner to read")
        read = tip.call(
            "company_dependent_fields",
            "res.partner",
            "read",
            [[partners[0]]],
            {"fields": ["property_payment_term_id"]},
        )
        if not isinstance(read, list) or not read or not isinstance(read[0], dict):
            pytest.fail("company_dependent_fields stayed unknown: value read was empty")
        value = read[0].get("property_payment_term_id")
        if value is not False:
            pytest.fail("company_dependent_fields stayed unknown: value read was not false")

    _guard(tip)(body)


def test_selection_storage_tip(tip: _Tip) -> None:
    def body() -> None:
        models = tip.call(
            "selection_storage",
            "ir.model",
            "search_read",
            [[["model", "=", "ir.model.fields.selection"]]],
            {"fields": ["model"], "limit": 1},
        )
        if not isinstance(models, list) or not models:
            pytest.fail("selection_storage stayed unknown: ir.model.fields.selection was absent")
        meta = tip.call(
            "selection_storage",
            "ir.model.fields",
            "fields_get",
            [],
            {"attributes": ["type", "relation", "store"]},
        )
        selection = meta.get("selection") if isinstance(meta, dict) else None
        selection_ids = meta.get("selection_ids") if isinstance(meta, dict) else None
        if (
            not isinstance(selection, dict)
            or selection.get("type") != "char"
            or selection.get("store") is not False
            or not isinstance(selection_ids, dict)
            or selection_ids.get("type") != "one2many"
            or selection_ids.get("relation") != "ir.model.fields.selection"
            or selection_ids.get("store") is not True
        ):
            pytest.fail("selection_storage stayed unknown: field metadata differed")
        rows = tip.call(
            "selection_storage",
            "ir.model.fields",
            "search_read",
            [[("model", "=", "res.partner"), ("name", "=", "type")]],
            {"fields": ["ttype", "selection", "selection_ids"], "limit": 1},
        )
        if not isinstance(rows, list) or not rows:
            pytest.fail("selection_storage stayed unknown: res.partner.type was absent")
        row = rows[0]
        if row.get("ttype") != "selection" or row.get("selection") != (
            "[('contact', 'Contact'), ('invoice', 'Invoice'), "
            "('delivery', 'Delivery'), ('other', 'Other')]"
        ):
            pytest.fail("selection_storage stayed unknown: selection char differed")
        ids = row.get("selection_ids")
        if not isinstance(ids, list) or len(ids) != 4:
            pytest.fail("selection_storage stayed unknown: selection_ids was not four rows")
        options = tip.call(
            "selection_storage",
            "ir.model.fields.selection",
            "read",
            [ids],
            {"fields": ["value"]},
        )
        if not isinstance(options, list):
            pytest.fail("selection_storage stayed unknown: option read was empty")
        values = [item.get("value") for item in options if isinstance(item, dict)]
        if values != ["contact", "invoice", "delivery", "other"]:
            pytest.fail(f"selection_storage stayed unknown: option values were {values!r}")

    _guard(tip)(body)


def test_mail_template_syntax_tip(tip: _Tip) -> None:
    def body() -> None:
        meta = tip.call("mail_template_syntax", "mail.template", "fields_get", [], {"attributes": ["type"]})
        if not isinstance(meta, dict):
            pytest.fail("mail_template_syntax stayed unknown: fields_get was empty")
        missing = [name for name in ("body_html", "subject", "email_from", "render_model") if name not in meta]
        if missing:
            pytest.fail(f"mail_template_syntax stayed unknown: missing {missing}")
        rows = tip.call(
            "mail_template_syntax",
            "mail.template",
            "search_read",
            [[["model", "=", "account.move"], ["body_html", "!=", False]]],
            {"fields": ["subject", "body_html"], "limit": 5},
        )
        if not isinstance(rows, list) or not rows:
            pytest.fail("mail_template_syntax stayed unknown: no account.move template")
        bodies = [row.get("body_html") or "" for row in rows if isinstance(row, dict)]
        subjects = [row.get("subject") or "" for row in rows if isinstance(row, dict)]
        qweb = [
            body
            for body in bodies
            if isinstance(body, str) and "t-out" in body and "object." in body and "${" not in body and "{{" not in body
        ]
        if not qweb:
            pytest.fail("mail_template_syntax stayed unknown: no account.move body used t-out without braces or mako")
        expressions = re.findall(r't-out="([^"]+)"', qweb[0])
        if "object.name or ''" not in expressions or "object.partner_id.name or ''" not in expressions:
            pytest.fail("mail_template_syntax stayed unknown: t-out expressions differed")
        if not any(isinstance(subject, str) and "{{" in subject and "object." in subject and "${" not in subject for subject in subjects):
            pytest.fail("mail_template_syntax stayed unknown: account.move subject had no object braces")
        mixed = tip.call(
            "mail_template_syntax",
            "mail.template",
            "search_read",
            [[["body_html", "ilike", "{{ object."]]],
            {"fields": ["body_html"], "limit": 1},
        )
        if not isinstance(mixed, list) or not mixed or not isinstance(mixed[0], dict):
            pytest.fail("mail_template_syntax stayed unknown: no template body contained object braces")
        mixed_body = mixed[0].get("body_html") or ""
        if not isinstance(mixed_body, str) or "t-out" not in mixed_body or "{{ object." not in mixed_body or "${" in mixed_body:
            pytest.fail("mail_template_syntax stayed unknown: brace template was not also t-out")

    _guard(tip)(body)


def test_translations_tip(tip: _Tip) -> None:
    def body() -> None:
        models = tip.call(
            "translations",
            "ir.model",
            "search_read",
            [[["model", "=", "ir.translation"]]],
            {"fields": ["model"], "limit": 1},
        )
        if models != []:
            pytest.fail("translations stayed unknown: ir.translation was present")
        meta = tip.call(
            "translations",
            "ir.model.fields",
            "fields_get",
            [],
            {"attributes": ["selection"]},
        )
        translate = meta.get("translate") if isinstance(meta, dict) else None
        selection = translate.get("selection") if isinstance(translate, dict) else None
        if not isinstance(selection, list):
            pytest.fail("translations stayed unknown: translate selection was absent")
        keys = [item[0] if isinstance(item, (list, tuple)) and item else item for item in selection]
        if set(keys) != {"standard", "html_translate", "xml_translate"}:
            pytest.fail(f"translations stayed unknown: translate keys were {keys!r}")
        langs = tip.call(
            "translations",
            "res.lang",
            "search_read",
            [[["active", "=", True]]],
            {"fields": ["code"], "limit": 8},
        )
        codes = [row.get("code") for row in langs if isinstance(row, dict) and isinstance(row.get("code"), str)]
        if codes != ["en_US"]:
            pytest.fail(f"translations stayed unknown: active languages were {codes!r}")
        menus = tip.call("translations", "ir.ui.menu", "search", [[["name", "!=", False]]], {"limit": 1})
        if not isinstance(menus, list) or not menus:
            pytest.fail("translations stayed unknown: no menu to read")
        menu = tip.call(
            "translations",
            "ir.ui.menu",
            "read",
            [[menus[0]]],
            {"fields": ["name"], "context": {"lang": "en_US"}},
        )
        menu_name = menu[0].get("name") if isinstance(menu, list) and menu and isinstance(menu[0], dict) else None
        if not isinstance(menu_name, str) or not menu_name.strip():
            pytest.fail("translations stayed unknown: en_US menu name was not a string")
        fields = tip.call(
            "translations",
            "ir.model.fields",
            "search_read",
            [[("model", "=", "res.partner"), ("name", "=", "name")]],
            {"fields": ["field_description"], "limit": 1, "context": {"lang": "en_US"}},
        )
        description = (
            fields[0].get("field_description")
            if isinstance(fields, list) and fields and isinstance(fields[0], dict)
            else None
        )
        if not isinstance(description, str) or not description.strip():
            pytest.fail("translations stayed unknown: en_US field_description was not a string")
        try:
            tip.client.execute_kw(
                "ir.ui.menu",
                "read",
                [[menus[0]]],
                {"fields": ["name"], "context": {"lang": "fr_FR"}},
            )
        except OdooClientError as exc:
            message = tip.scrub(str(exc))
            if "Invalid language code: fr_FR" not in message:
                pytest.fail(f"translations stayed unknown: {message}")
        else:
            pytest.fail("translations stayed unknown: fr_FR read returned a value")

    _guard(tip)(body)
