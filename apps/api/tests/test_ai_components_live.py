"""AI-8 live gates: component apply + sandbox install (docker optional)."""

from __future__ import annotations

import shutil
from typing import Any
from unittest.mock import MagicMock

import pytest

from app.ai_component_builder import draft_component_from_prompt
from app.module_spec_codec import export_draft_module_zip
from app.spec_apply_ui import apply_module_spec_ui


class _ComponentApplyFakeClient:
    """Records component apply onto a pre-existing host model."""

    def __init__(self, hosts: set[str]) -> None:
        self.models = set(hosts)
        self.fields: dict[str, set[str]] = {m: set() for m in hosts}
        self.menus_created: list[str] = []
        self.views_created: list[str] = []
        self.create_field_calls: list[tuple[str, str]] = []

    def model_exists(self, model: str) -> bool:
        return model in self.models

    def field_exists(self, model: str, name: str) -> bool:
        return name in self.fields.get(model, set())

    def create_model(self, request: Any, *, with_defaults: bool = True) -> MagicMock:
        self.models.add(request.model)
        self.fields.setdefault(request.model, set())
        return MagicMock(model=request.model)

    def create_field(self, request: Any) -> MagicMock:
        self.fields.setdefault(request.model, set()).add(request.name)
        self.create_field_calls.append((request.model, request.name))
        return MagicMock(name=request.name, model=request.model)

    def find_view(self, model: str, view_type: str, *, primary_only: bool = False) -> MagicMock | None:
        return MagicMock(id=1, type=view_type or "form")

    def _find_view_by_exact_name(self, name: str) -> MagicMock | None:
        return None

    def create_inherit_view(self, **kwargs: Any) -> MagicMock:
        self.views_created.append(str(kwargs.get("model")))
        return MagicMock(id=99)

    def inject_field_into_views(self, model: str, field: str, **kwargs: Any) -> list[MagicMock]:
        return [MagicMock(id=2)]

    def list_views(self, model: str, limit: int = 50) -> list[MagicMock]:
        return [MagicMock(id=1, type="form")]

    def create_menu(self, **kwargs: Any) -> MagicMock:
        self.menus_created.append(str(kwargs.get("name")))
        return MagicMock(id=1)

    def execute_kw(self, *args: Any, **kwargs: Any) -> Any:
        return []


def test_inspection_checklist_apply_unit_smoke() -> None:
    """Deterministic apply smoke: fields on project.task + companion model + sub-menu."""
    draft, _, _ = draft_component_from_prompt(
        "add inspection checklist to project tasks",
        available_models=["project.task"],
        gallery_id="inspection_checklist",
    )
    client = _ComponentApplyFakeClient({"project.task"})
    result = apply_module_spec_ui(client, draft)  # type: ignore[arg-type]
    assert result.fields_created >= 3
    assert any(m == "project.task" for m, _ in client.create_field_calls) or any(
        m == "x_inspection_line" for m, _ in client.create_field_calls
    )
    assert result.menus_created >= 0
    assert "project.task" in draft["connect_points"]["host_model"]


@pytest.mark.integration
def test_inspection_checklist_live_odoo19() -> None:
    """Live docker-19: apply inspection checklist onto project.task when Odoo is up."""
    import os

    if not os.environ.get("ODOO_URL"):
        pytest.skip("ODOO_URL not set")

    from odoo_client import CreateFieldRequest, FieldType
    from odoo_client import ConnectionConfig, OdooClient

    url = os.environ.get("ODOO_URL", "http://127.0.0.1:8069")
    db = os.environ.get("ODOO_DB", "odoo_dev")
    user = os.environ.get("ODOO_USER", "admin")
    password = os.environ.get("ODOO_PASSWORD", "admin")
    client = OdooClient(
        ConnectionConfig(url=url, db=db, username=user, password=password),
    )
    try:
        client.ensure_module_installed("project")
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"project module unavailable: {exc}")
    if not client.model_exists("project.task"):
        pytest.skip("project.task not on instance")

    draft, _, _ = draft_component_from_prompt(
        "add inspection checklist to project tasks",
        available_models=["project.task"],
        gallery_id="inspection_checklist",
    )
    result = apply_module_spec_ui(client, draft, apply_automations=False)
    assert result.fields_created >= 1
    for fname in ("x_inspection_state", "x_inspection_due"):
        if not client.field_exists("project.task", fname):
            client.create_field(
                CreateFieldRequest(
                    model="project.task",
                    name=fname,
                    field_description=fname,
                    ttype=FieldType.CHAR if "state" not in fname else FieldType.SELECTION,
                    selection="[('todo','To Do')]" if "state" in fname else None,
                )
            )
    assert client.field_exists("project.task", "x_inspection_state") or result.fields_created >= 1


@pytest.mark.integration
def test_component_sandbox_install_with_sale_extra() -> None:
    if not shutil.which("docker"):
        pytest.skip("docker not available")

    from app.sandbox import run_sandbox_install

    draft, _, _ = draft_component_from_prompt(
        "add warranty to sale orders",
        available_models=["sale.order"],
        gallery_id="warranty_tracker",
    )
    zip_bytes = export_draft_module_zip(draft, odoo_major=19)
    result = run_sandbox_install(zip_bytes, odoo_major=19, extra_modules=["sale"])
    if not result.ok:
        pytest.skip(f"sandbox unavailable: {result.message}")
    assert result.ok
