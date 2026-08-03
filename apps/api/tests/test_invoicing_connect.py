"""Tests for CMP-8 invoicing connect + l10n."""

from __future__ import annotations

from typing import Any

from app.invoicing_connect import (
    connect_live_metadata,
    create_draft_invoice_linked,
    module_spec_fragment,
)
from app.invoicing_l10n import detect_l10n
from app.protected_enforcement import (
    check_field_create,
    check_invoicing_draft_create,
)
from app.protected_modules import community_manifest_for_version


class _FakeClient:
    def __init__(self) -> None:
        self.fields: set[tuple[str, str]] = set()
        self.created_fields: list[dict[str, Any]] = []
        self.actions: list[dict[str, Any]] = []
        self.records: dict[str, dict[int, dict[str, Any]]] = {
            "x_matter": {
                5: {
                    "x_partner_id": 42,
                    "x_amount": 120.0,
                    "x_name": "Legal retainer",
                    "x_invoice_ids": [],
                }
            }
        }
        self.moves: dict[int, dict[str, Any]] = {}
        self._move_seq = 900
        self.writes: list[tuple[str, list[int], dict[str, Any]]] = []

    def model_exists(self, model: str) -> bool:
        return model in {"account.move", "x_matter", "res.company", "res.country"}

    def list_installed_modules(self, *, name_prefix: str | None = None, limit: int = 400) -> list[Any]:
        return []

    def list_installed_modules(self, *, name_prefix: str | None = None, limit: int = 400) -> list[Any]:
        return []

    def field_exists(self, model: str, name: str) -> bool:
        return (model, name) in self.fields

    def create_field(self, request: Any) -> None:
        self.created_fields.append(request.model_dump())
        self.fields.add((request.model, request.name))

    def create_related_count_field(self, request: Any) -> Any:
        from types import SimpleNamespace

        self.fields.add((request.model, request.name))
        return SimpleNamespace(name=request.name, id=77)

    def inject_smart_buttons_into_form(self, model: str, buttons: list[Any], **kwargs: Any) -> Any:
        from types import SimpleNamespace

        return SimpleNamespace(id=501, name=f"{model}.studio.smart_buttons")

    def create_window_action(
        self,
        *,
        name: str,
        model: str,
        view_mode: str,
        domain: str,
        context: str,
    ) -> int:
        action_id = len(self.actions) + 1
        self.actions.append(
            {
                "id": action_id,
                "name": name,
                "model": model,
                "view_mode": view_mode,
                "domain": domain,
                "context": context,
            }
        )
        return action_id

    def execute_kw(
        self,
        model: str,
        method: str,
        args: list[Any],
        kwargs: dict[str, Any] | None = None,
    ) -> Any:
        if model == "x_matter" and method == "read":
            ids = args[0]
            return [self.records["x_matter"][i] for i in ids]
        if model == "account.move" and method == "create":
            self._move_seq += 1
            self.moves[self._move_seq] = {"state": "draft", "name": "DRAFT/001"}
            return self._move_seq
        if model == "account.move" and method == "read":
            return [self.moves[i] for i in args[0]]
        if model == "x_matter" and method == "write":
            rid, vals = args[0][0], args[1]
            self.writes.append((model, [rid], vals))
            return True
        if model == "res.company" and method == "search_read":
            return [{"country_id": [10, "Belgium"]}]
        if model == "res.country" and method == "read":
            return [{"code": "BE"}]
        raise AssertionError(f"{model}.{method}")


class _L10nClient(_FakeClient):
    def list_installed_modules(self, *, name_prefix: str | None = None, limit: int = 400) -> list[Any]:
        from types import SimpleNamespace

        return [SimpleNamespace(name="l10n_be")]


def test_module_spec_fragment_includes_account_depends() -> None:
    frag = module_spec_fragment(model="x_matter")
    assert "account" in frag["depends_add"]
    assert frag["smart_button"]["one2many_field"] == "x_invoice_ids"
    inherit = next(m for m in frag["models"] if m["model"] == "account.move")
    assert inherit["mode"] == "inherit"


def test_connect_live_metadata_m2m_only() -> None:
    client = _FakeClient()
    result = connect_live_metadata(client, model="x_matter")
    assert result["path"] == "live_metadata_m2m"
    assert client.created_fields[0]["ttype"] == "many2many"
    assert result["count_field"] == "x_invoice_count"
    assert result["form_view_id"] == 501
    assert client.actions[0]["domain"] == "[('id', 'in', x_invoice_ids)]"


def test_create_draft_invoice_linked_never_posts() -> None:
    client = _FakeClient()
    result = create_draft_invoice_linked(client, source_model="x_matter", record_id=5)
    assert result["state"] == "draft"
    assert client.writes[0][2]["x_invoice_ids"] == [(4, result["move_id"])]


def test_pcm_m2m_on_custom_allowed() -> None:
    m = community_manifest_for_version("19.0")
    assert (
        check_field_create(
            m,
            model="x_matter",
            ttype="many2many",
            relation="account.move",
            field_name="x_invoice_ids",
        )
        is None
    )


def test_pcm_invoicing_draft_from_custom_allowed() -> None:
    assert check_invoicing_draft_create(source_model="x_matter") is None
    viol = check_invoicing_draft_create(source_model="account.move")
    assert viol is not None


def test_l10n_detect_honest_when_missing() -> None:
    client = _FakeClient()
    data = detect_l10n(client)
    assert data["account_installed"] is True
    assert data["ok"] is False


def test_l10n_detect_ok_when_installed() -> None:
    data = detect_l10n(_L10nClient())
    assert data["ok"] is True
    assert "l10n_be" in data["l10n_modules"]
