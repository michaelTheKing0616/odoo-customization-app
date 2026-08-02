"""API integration tests against local app-db + Odoo 19."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

# Ensure settings point at local containers before app import side effects.
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom",
)
os.environ.setdefault("FERNET_KEY", "dev-only-test")
os.environ.setdefault("AUTH_MODE", "off")

from app.main import app  # noqa: E402


@pytest.fixture(scope="module")
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


def test_health(client: TestClient) -> None:
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["odoo_target_version"] == "19"


@pytest.mark.integration
def test_connection_and_introspection(client: TestClient) -> None:
    create = client.post(
        "/api/connections",
        json={
            "name": "Gate Local",
            "url": os.environ.get("ODOO_URL", "http://127.0.0.1:8069"),
            "db_name": os.environ.get("ODOO_DB", "odoo_dev"),
            "username": os.environ.get("ODOO_USER", "admin"),
            "password": os.environ.get("ODOO_PASSWORD", "admin"),
            "verify": True,
        },
    )
    if create.status_code >= 400:
        pytest.skip(f"Odoo/app-db not ready: {create.text}")
    assert create.status_code == 201
    body = create.json()
    assert body["server_version"].startswith("19")
    cid = body["id"]

    modules = client.get(f"/api/connections/{cid}/modules", params={"applications_only": True})
    assert modules.status_code == 200

    models = client.get(f"/api/connections/{cid}/models")
    assert models.status_code == 200
    assert any(m["model"] == "res.partner" for m in models.json())

    fields = client.get(f"/api/connections/{cid}/models/res.partner/fields")
    assert fields.status_code == 200
    assert any(f["name"] == "name" for f in fields.json())

    views = client.get(f"/api/connections/{cid}/models/res.partner/views")
    assert views.status_code == 200
    assert isinstance(views.json(), list)

    deleted = client.delete(f"/api/connections/{cid}")
    assert deleted.status_code == 204


@pytest.mark.integration
def test_builder_create_model_and_field(client: TestClient) -> None:
    import uuid

    create = client.post(
        "/api/connections",
        json={
            "name": "Builder Gate",
            "url": os.environ.get("ODOO_URL", "http://127.0.0.1:8069"),
            "db_name": os.environ.get("ODOO_DB", "odoo_dev"),
            "username": os.environ.get("ODOO_USER", "admin"),
            "password": os.environ.get("ODOO_PASSWORD", "admin"),
            "verify": True,
        },
    )
    if create.status_code >= 400:
        pytest.skip(f"Odoo/app-db not ready: {create.text}")
    cid = create.json()["id"]
    suffix = uuid.uuid4().hex[:8]
    model = f"x_builder_{suffix}"

    created_model = client.post(
        f"/api/connections/{cid}/models",
        json={"name": f"Builder {suffix}", "model": model, "with_defaults": True},
    )
    assert created_model.status_code == 201, created_model.text
    assert created_model.json()["model"] == model

    fields = client.get(f"/api/connections/{cid}/models/{model}/fields")
    assert fields.status_code == 200
    assert any(f["name"] == "x_name" for f in fields.json())

    rights = client.get(f"/api/connections/{cid}/access/rights", params={"model": model})
    assert rights.status_code == 200
    assert len(rights.json()) >= 1
    assert any(r["perm_read"] and r["perm_write"] for r in rights.json())

    created_field = client.post(
        f"/api/connections/{cid}/fields",
        json={
            "model": model,
            "name": "x_priority",
            "field_description": "Priority",
            "ttype": "selection",
            "selection": [
                {"value": "low", "label": "Low"},
                {"value": "high", "label": "High"},
            ],
        },
    )
    assert created_field.status_code == 201, created_field.text
    assert created_field.json()["ttype"] == "selection"

    conflict = client.post(
        f"/api/connections/{cid}/models",
        json={"name": "Dup", "model": model},
    )
    assert conflict.status_code == 400

    client.delete(f"/api/connections/{cid}")


@pytest.mark.integration
def test_view_designer_preview_and_save(client: TestClient) -> None:
    import uuid

    create = client.post(
        "/api/connections",
        json={
            "name": "Designer Gate",
            "url": os.environ.get("ODOO_URL", "http://127.0.0.1:8069"),
            "db_name": os.environ.get("ODOO_DB", "odoo_dev"),
            "username": os.environ.get("ODOO_USER", "admin"),
            "password": os.environ.get("ODOO_PASSWORD", "admin"),
            "verify": True,
        },
    )
    if create.status_code >= 400:
        pytest.skip(f"Odoo/app-db not ready: {create.text}")
    cid = create.json()["id"]
    suffix = uuid.uuid4().hex[:8]
    model = f"x_view_{suffix}"

    assert (
        client.post(
            f"/api/connections/{cid}/models",
            json={"name": f"View {suffix}", "model": model, "with_defaults": True},
        ).status_code
        == 201
    )

    preview = client.post(
        f"/api/connections/{cid}/views/preview",
        json={
            "view_type": "form",
            "spec": {
                "string": "Designed",
                "children": [
                    {
                        "kind": "group",
                        "string": "Main",
                        "children": [
                            {"kind": "field", "name": "x_name", "required": True},
                        ],
                    },
                    {
                        "kind": "notebook",
                        "pages": [
                            {
                                "string": "Extra",
                                "children": [{"kind": "field", "name": "x_name"}],
                            }
                        ],
                    },
                ],
            },
        },
    )
    assert preview.status_code == 200, preview.text
    arch = preview.json()["arch"]
    assert "notebook" in arch
    assert "x_name" in arch

    saved = client.post(
        f"/api/connections/{cid}/views/save",
        json={
            "model": model,
            "view_type": "form",
            "spec": {
                "string": "Designed",
                "children": [
                    {
                        "kind": "group",
                        "children": [{"kind": "field", "name": "x_name"}],
                    }
                ],
            },
        },
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["id"] > 0
    assert "x_name" in (saved.json().get("arch") or "")

    client.delete(f"/api/connections/{cid}")


@pytest.mark.integration
def test_kanban_designer_save_parse_round_trip(client: TestClient) -> None:
    """Live Odoo 19: preview → save inherit → parse preserves card field order + group-by."""
    import uuid

    create = client.post(
        "/api/connections",
        json={
            "name": "Kanban Designer Gate",
            "url": os.environ.get("ODOO_URL", "http://127.0.0.1:8069"),
            "db_name": os.environ.get("ODOO_DB", "odoo_dev"),
            "username": os.environ.get("ODOO_USER", "admin"),
            "password": os.environ.get("ODOO_PASSWORD", "admin"),
            "verify": True,
        },
    )
    if create.status_code >= 400:
        pytest.skip(f"Odoo/app-db not ready: {create.text}")
    cid = create.json()["id"]
    suffix = uuid.uuid4().hex[:8]
    model = f"x_kan_{suffix}"

    assert (
        client.post(
            f"/api/connections/{cid}/models",
            json={"name": f"Kanban {suffix}", "model": model, "with_defaults": True},
        ).status_code
        == 201
    )

    # Selection field for group-by columns
    sel = client.post(
        f"/api/connections/{cid}/fields",
        json={
            "model": model,
            "name": "x_stage",
            "field_description": "Stage",
            "ttype": "selection",
            "selection": [
                {"value": "todo", "label": "Todo"},
                {"value": "done", "label": "Done"},
            ],
        },
    )
    assert sel.status_code == 201, sel.text

    ordered = ["x_name", "x_stage"]
    preview = client.post(
        f"/api/connections/{cid}/views/preview",
        json={
            "view_type": "kanban",
            "spec": {
                "string": "Board",
                "records_fields": ordered,
                "default_group_by": "x_stage",
            },
        },
    )
    assert preview.status_code == 200, preview.text
    arch = preview.json()["arch"]
    assert 'default_group_by="x_stage"' in arch
    assert arch.index('name="x_name"') < arch.index('name="x_stage"')

    saved = client.post(
        f"/api/connections/{cid}/views/save",
        json={
            "model": model,
            "view_type": "kanban",
            "strategy": "inherit",
            "spec": {
                "string": "Board",
                "records_fields": ordered,
                "default_group_by": "x_stage",
            },
        },
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["id"] > 0
    saved_arch = saved.json().get("arch") or ""
    assert "x_name" in saved_arch
    assert "x_stage" in saved_arch

    # Reorder + re-save (UI ↑↓ path)
    reordered = ["x_stage", "x_name"]
    saved2 = client.post(
        f"/api/connections/{cid}/views/save",
        json={
            "model": model,
            "view_type": "kanban",
            "strategy": "inherit",
            "spec": {
                "string": "Board",
                "records_fields": reordered,
                "default_group_by": "x_stage",
            },
        },
    )
    assert saved2.status_code == 200, saved2.text

    parsed = client.post(
        f"/api/connections/{cid}/views/parse",
        json={"view_type": "kanban", "arch": saved2.json().get("arch") or ""},
    )
    assert parsed.status_code == 200, parsed.text
    spec = parsed.json()["spec"]
    assert spec["records_fields"] == reordered
    assert spec["default_group_by"] == "x_stage"

    client.delete(f"/api/connections/{cid}")


@pytest.mark.integration
def test_automation_create(client: TestClient) -> None:
    create = client.post(
        "/api/connections",
        json={
            "name": "Auto Gate",
            "url": os.environ.get("ODOO_URL", "http://127.0.0.1:8069"),
            "db_name": os.environ.get("ODOO_DB", "odoo_dev"),
            "username": os.environ.get("ODOO_USER", "admin"),
            "password": os.environ.get("ODOO_PASSWORD", "admin"),
            "verify": True,
        },
    )
    if create.status_code >= 400:
        pytest.skip(f"Odoo/app-db not ready: {create.text}")
    cid = create.json()["id"]

    fields = client.get(f"/api/connections/{cid}/models/res.partner/fields")
    names = {f["name"] for f in fields.json()}
    if "x_auto_note" not in names:
        created_field = client.post(
            f"/api/connections/{cid}/fields",
            json={
                "model": "res.partner",
                "name": "x_auto_note",
                "field_description": "Auto Note",
                "ttype": "char",
            },
        )
        assert created_field.status_code == 201, created_field.text

    auto = client.post(
        f"/api/connections/{cid}/automations",
        json={
            "name": "API auto set note",
            "model": "res.partner",
            "trigger": "on_create",
            "action_kind": "update_field",
            "field_name": "x_auto_note",
            "value": "via-api",
        },
    )
    assert auto.status_code == 201, auto.text
    assert auto.json()["trigger"] == "on_create"

    listed = client.get(f"/api/connections/{cid}/automations")
    assert listed.status_code == 200
    assert any(a["id"] == auto.json()["id"] for a in listed.json())

    client.delete(f"/api/connections/{cid}")


@pytest.mark.integration
def test_python_module_export_and_code_live_requires_confirm(client: TestClient) -> None:
    create = client.post(
        "/api/connections",
        json={
            "name": "Code Path Gate",
            "url": os.environ.get("ODOO_URL", "http://127.0.0.1:8069"),
            "db_name": os.environ.get("ODOO_DB", "odoo_dev"),
            "username": os.environ.get("ODOO_USER", "admin"),
            "password": os.environ.get("ODOO_PASSWORD", "admin"),
            "verify": True,
        },
    )
    if create.status_code >= 400:
        pytest.skip(f"Odoo/app-db not ready: {create.text}")
    cid = create.json()["id"]

    mod = client.post(
        f"/api/connections/{cid}/automations",
        json={
            "name": "Packaged code",
            "model": "res.partner",
            "trigger": "on_create",
            "action_kind": "python_module",
            "python_code": "True",
            "module_technical_name": "gate_auto_code",
        },
    )
    assert mod.status_code == 201, mod.text
    body = mod.json()
    assert "content_base64" in body
    assert body["filename"].endswith(".zip")

    denied = client.post(
        f"/api/connections/{cid}/automations",
        json={
            "name": "Live code",
            "model": "res.partner",
            "trigger": "on_create",
            "action_kind": "code_live",
            "python_code": "True",
        },
    )
    assert denied.status_code == 403
    assert denied.json()["detail"]["requires_confirmation"] is True

    client.delete(f"/api/connections/{cid}")


@pytest.mark.integration
def test_export_module_from_custom_models(client: TestClient) -> None:
    import uuid

    create = client.post(
        "/api/connections",
        json={
            "name": "Export Gate",
            "url": os.environ.get("ODOO_URL", "http://127.0.0.1:8069"),
            "db_name": os.environ.get("ODOO_DB", "odoo_dev"),
            "username": os.environ.get("ODOO_USER", "admin"),
            "password": os.environ.get("ODOO_PASSWORD", "admin"),
            "verify": True,
        },
    )
    if create.status_code >= 400:
        pytest.skip(f"Odoo/app-db not ready: {create.text}")
    cid = create.json()["id"]
    model = f"x_exp_{uuid.uuid4().hex[:8]}"

    built = client.post(
        f"/api/connections/{cid}/models",
        json={"name": "Export Model", "model": model, "with_defaults": True},
    )
    assert built.status_code == 201, built.text

    field = client.post(
        f"/api/connections/{cid}/fields",
        json={
            "model": model,
            "name": f"x_note_{uuid.uuid4().hex[:6]}",
            "field_description": "Note",
            "ttype": "char",
            "inject_into_views": True,
        },
    )
    assert field.status_code == 201, field.text
    assert "injected_view_ids" in field.json()

    exported = client.post(
        f"/api/connections/{cid}/export-module",
        json={
            "technical_name": f"exp_{uuid.uuid4().hex[:8]}",
            "display_name": "Export Gate Module",
            "model_filter": [model],
        },
    )
    assert exported.status_code == 200, exported.text
    body = exported.json()
    assert body["model_count"] >= 1
    assert body["content_base64"]

    saved = client.post(
        f"/api/connections/{cid}/views/save",
        json={
            "model": model,
            "view_type": "form",
            "spec": {
                "string": "Form",
                "children": [
                    {
                        "kind": "group",
                        "string": "Main",
                        "children": [{"kind": "field", "name": "x_name"}],
                    }
                ],
            },
        },
    )
    assert saved.status_code == 200, saved.text
    assert saved.json().get("snapshot_id")

    client.delete(f"/api/connections/{cid}")


def test_sandbox_smoke_zip_unit() -> None:
    from module_generator import FieldSpec, ModelSpec, ModuleSpec, build_module_zip

    raw = build_module_zip(
        ModuleSpec(
            technical_name="unit_sandbox",
            display_name="Unit",
            models=[
                ModelSpec(
                    model="x_unit",
                    description="Unit",
                    fields=[FieldSpec(name="x_name", ttype="char", string="Name")],
                )
            ],
        )
    )
    assert raw[:2] == b"PK"


@pytest.mark.integration
def test_promote_requires_confirm_and_validation(client: TestClient) -> None:
    import base64
    import uuid

    from module_generator import FieldSpec, ModelSpec, ModuleSpec, build_module_zip

    create = client.post(
        "/api/connections",
        json={
            "name": "Promote Gate",
            "url": os.environ.get("ODOO_URL", "http://127.0.0.1:8069"),
            "db_name": os.environ.get("ODOO_DB", "odoo_dev"),
            "username": os.environ.get("ODOO_USER", "admin"),
            "password": os.environ.get("ODOO_PASSWORD", "admin"),
            "verify": True,
        },
    )
    if create.status_code >= 400:
        pytest.skip(f"Odoo/app-db not ready: {create.text}")
    cid = create.json()["id"]

    tech = f"promo_{uuid.uuid4().hex[:8]}"
    raw = build_module_zip(
        ModuleSpec(
            technical_name=tech,
            display_name="Promo",
            models=[
                ModelSpec(
                    model=f"x_{tech}",
                    description="Promo",
                    fields=[FieldSpec(name="x_name", ttype="char", string="Name", required=True)],
                )
            ],
        )
    )
    z64 = base64.b64encode(raw).decode()

    denied = client.post(
        f"/api/connections/{cid}/modules/promote",
        json={"zip_base64": z64, "run_sandbox": False, "validation_id": "nope"},
    )
    assert denied.status_code == 403
    assert denied.json()["detail"]["requires_confirmation"] is True

    # Missing validation after confirm
    missing = client.post(
        f"/api/connections/{cid}/modules/promote",
        json={
            "zip_base64": z64,
            "confirm_advanced": True,
            "confirm_phrase": "I understand the risks",
        },
    )
    assert missing.status_code == 422

    client.delete(f"/api/connections/{cid}")


@pytest.mark.integration
def test_access_rights_and_record_rule(client: TestClient) -> None:
    import uuid

    create = client.post(
        "/api/connections",
        json={
            "name": "Access Gate",
            "url": os.environ.get("ODOO_URL", "http://127.0.0.1:8069"),
            "db_name": os.environ.get("ODOO_DB", "odoo_dev"),
            "username": os.environ.get("ODOO_USER", "admin"),
            "password": os.environ.get("ODOO_PASSWORD", "admin"),
            "verify": True,
        },
    )
    if create.status_code >= 400:
        pytest.skip(f"Odoo/app-db not ready: {create.text}")
    cid = create.json()["id"]
    model = f"x_acl_{uuid.uuid4().hex[:8]}"

    built = client.post(
        f"/api/connections/{cid}/models",
        json={"name": "ACL Model", "model": model, "with_defaults": True},
    )
    assert built.status_code == 201, built.text

    groups = client.get(f"/api/connections/{cid}/access/groups")
    assert groups.status_code == 200
    assert len(groups.json()) >= 1
    group_id = groups.json()[0]["id"]

    right = client.post(
        f"/api/connections/{cid}/access/rights",
        json={
            "model": model,
            "name": f"{model} user",
            "group_id": group_id,
            "perm_read": True,
            "perm_write": True,
            "perm_create": True,
            "perm_unlink": False,
        },
    )
    assert right.status_code == 201, right.text
    assert right.json()["model"] == model
    assert right.json()["perm_read"] is True

    listed = client.get(f"/api/connections/{cid}/access/rights", params={"model": model})
    assert listed.status_code == 200
    assert any(r["id"] == right.json()["id"] for r in listed.json())

    rule = client.post(
        f"/api/connections/{cid}/access/rules",
        json={
            "model": model,
            "name": f"{model} own records",
            "domain_force": "[('create_uid', '=', user.id)]",
            "group_ids": [group_id],
            "perm_read": True,
            "perm_write": True,
            "perm_create": True,
            "perm_unlink": True,
        },
    )
    assert rule.status_code == 201, rule.text
    assert "create_uid" in (rule.json().get("domain_force") or "")

    rules = client.get(f"/api/connections/{cid}/access/rules", params={"model": model})
    assert rules.status_code == 200
    assert any(r["id"] == rule.json()["id"] for r in rules.json())

    client.delete(f"/api/connections/{cid}")


@pytest.mark.integration
def test_uninstall_requires_confirm(client: TestClient) -> None:
    create = client.post(
        "/api/connections",
        json={
            "name": "Uninstall Gate",
            "url": os.environ.get("ODOO_URL", "http://127.0.0.1:8069"),
            "db_name": os.environ.get("ODOO_DB", "odoo_dev"),
            "username": os.environ.get("ODOO_USER", "admin"),
            "password": os.environ.get("ODOO_PASSWORD", "admin"),
            "verify": True,
        },
    )
    if create.status_code >= 400:
        pytest.skip(f"Odoo/app-db not ready: {create.text}")
    cid = create.json()["id"]

    denied = client.post(
        f"/api/connections/{cid}/modules/uninstall",
        json={"module_name": "promote_fs"},
    )
    assert denied.status_code == 403
    assert denied.json()["detail"]["requires_confirmation"] is True

    listed = client.get(f"/api/connections/{cid}/modules/promoted")
    assert listed.status_code == 200
    assert isinstance(listed.json(), list)

    client.delete(f"/api/connections/{cid}")


@pytest.mark.integration
def test_wave_b_destructive_confirm_gates(client: TestClient) -> None:
    """DELETE field/model/automation/access without confirm → 403 before mutate."""
    import uuid

    create = client.post(
        "/api/connections",
        json={
            "name": "Wave B Confirm Gate",
            "url": os.environ.get("ODOO_URL", "http://127.0.0.1:8069"),
            "db_name": os.environ.get("ODOO_DB", "odoo_dev"),
            "username": os.environ.get("ODOO_USER", "admin"),
            "password": os.environ.get("ODOO_PASSWORD", "admin"),
            "verify": True,
        },
    )
    if create.status_code >= 400:
        pytest.skip(f"Odoo/app-db not ready: {create.text}")
    cid = create.json()["id"]
    suffix = uuid.uuid4().hex[:8]
    model = f"x_waveb_{suffix}"

    built = client.post(
        f"/api/connections/{cid}/models",
        json={"name": f"WaveB {suffix}", "model": model, "with_defaults": True},
    )
    assert built.status_code == 201, built.text

    field = client.post(
        f"/api/connections/{cid}/fields",
        json={
            "model": model,
            "name": f"x_tmp_{suffix}",
            "field_description": "Temp",
            "ttype": "char",
            "inject_into_views": False,
        },
    )
    assert field.status_code == 201, field.text
    field_id = field.json()["id"]

    denied_field = client.request(
        "DELETE",
        f"/api/connections/{cid}/fields/{field_id}",
        json={},
    )
    assert denied_field.status_code == 403
    assert denied_field.json()["detail"]["requires_confirmation"] is True
    assert denied_field.json()["detail"]["confirm_phrase"] == "I understand the risks"

    denied_model = client.request(
        "DELETE",
        f"/api/connections/{cid}/models/{model}",
        json={"confirm_advanced": True, "confirm_phrase": "wrong"},
    )
    assert denied_model.status_code == 403

    patched = client.patch(
        f"/api/connections/{cid}/fields/{field_id}",
        json={"help": "wave-b", "required": False},
    )
    assert patched.status_code == 200, patched.text

    rights = client.get(f"/api/connections/{cid}/access/rights", params={"model": model})
    assert rights.status_code == 200
    if rights.json():
        aid = rights.json()[0]["id"]
        denied_access = client.request(
            "DELETE",
            f"/api/connections/{cid}/access/rights/{aid}",
            json={},
        )
        assert denied_access.status_code == 403
        assert denied_access.json()["detail"]["requires_confirmation"] is True

    denied_auto = client.request(
        "DELETE",
        f"/api/connections/{cid}/automations/999999",
        json={},
    )
    assert denied_auto.status_code == 403

    client.delete(f"/api/connections/{cid}")
