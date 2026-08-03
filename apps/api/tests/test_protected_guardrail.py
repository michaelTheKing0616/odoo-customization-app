"""PCM-3 adversarial + deterministic guardrail tests (REM-2)."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.ai_rules import strip_protected_module_effects
from app.crypto import encrypt_secret
from app.db import SessionLocal, init_db
from app.db_models import OdooConnection
from app.main import app
from app.protected_enforcement import (
    check_automation_create,
    normalize_refusal_dict,
    pcm_refusal,
    scrub_spec_for_protected_apply,
)
from app.protected_modules import community_manifest_for_version, protected_models_for
from app.snapshots import CONFIRM_PHRASE
from app.spec_apply_ui import UiApplyResult

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom",
)
os.environ.setdefault("FERNET_KEY", "dev-only-test")
os.environ.setdefault("AUTH_MODE", "off")


@pytest.fixture
def api_client() -> TestClient:
    init_db()
    with TestClient(app) as c:
        yield c


def _mk_connection(name: str = "pcm-guard") -> OdooConnection:
    db = SessionLocal()
    try:
        row = OdooConnection(
            name=name,
            url="http://127.0.0.1:8069",
            db_name="odoo_dev",
            username="admin",
            secret_encrypted=encrypt_secret("admin"),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row
    finally:
        db.close()


def _confirm() -> dict[str, object]:
    return {"confirm_advanced": True, "confirm_phrase": CONFIRM_PHRASE}


def _manifest():
    return community_manifest_for_version("19.0")


def test_refusal_contract_shape() -> None:
    r = pcm_refusal(
        requested_capability="write account.move.state",
        protected_module="account.move",
        safe_alternative="Link from x_* only",
    )
    out = normalize_refusal_dict(r)
    assert out["protected_module_conflict"] is True
    assert out["requested_capability"] == "write account.move.state"
    assert out["protected_module"] == "account.move"
    assert out["safe_alternative"]


def test_legacy_refusal_normalized() -> None:
    legacy = {"kind": "inherit_strip", "model": "account.move", "reason": "blocked"}
    out = normalize_refusal_dict(legacy)
    assert out["protected_module_conflict"] is True
    assert out["protected_module"] == "account.move"


def test_strip_tier1_automation_on_account_move() -> None:
    draft = {
        "models": [{"model": "x_matter", "fields": []}],
        "automations": [
            {
                "name": "Set posted",
                "model": "account.move",
                "safe_actions": [{"kind": "object_write", "field": "state", "value": "posted"}],
            }
        ],
    }
    cleaned, refusals, warnings = strip_protected_module_effects(draft, manifest=_manifest())
    assert not cleaned.get("automations")
    assert refusals
    assert refusals[0]["protected_module_conflict"] is True
    assert "account" in refusals[0]["protected_module"]


def test_strip_allows_link_only_m2o() -> None:
    draft = {
        "models": [
            {
                "model": "x_matter",
                "fields": [
                    {
                        "name": "x_invoice_id",
                        "ttype": "many2one",
                        "relation": "account.move",
                    }
                ],
            }
        ],
        "automations": [],
    }
    cleaned, refusals, _w = strip_protected_module_effects(draft, manifest=_manifest())
    fields = cleaned["models"][0]["fields"]
    assert any(f.get("name") == "x_invoice_id" for f in fields)
    assert not refusals


def test_strip_inherit_on_tier1_host() -> None:
    draft = {
        "models": [{"model": "account.move", "mode": "inherit", "fields": [{"name": "x_note", "ttype": "char"}]}],
        "automations": [],
    }
    cleaned, refusals, _w = strip_protected_module_effects(draft, manifest=_manifest())
    assert cleaned.get("models") == []
    assert any(r["kind"] == "inherit_strip" for r in refusals)


def test_mechanism_swap_webhook_still_blocked_on_tier1() -> None:
    m = _manifest()
    viol = check_automation_create(
        m,
        model="account.move",
        action_kind="webhook",
    )
    assert viol is not None
    assert viol.tier == "tier_1"


def test_chatter_allowed_on_tier1() -> None:
    m = _manifest()
    assert check_automation_create(m, model="account.move", action_kind="mail_post") is None
    assert check_automation_create(m, model="account.move", action_kind="create_activity") is None


def test_scrub_spec_apply_skips_tier1_field_on_stock() -> None:
    spec = {
        "models": [
            {
                "model": "account.move",
                "fields": [{"name": "x_custom_note", "ttype": "char"}],
            }
        ],
        "automations": [],
    }
    cleaned, skips = scrub_spec_for_protected_apply(spec, _manifest())
    assert skips
    assert not cleaned.get("models")


def test_full_app_style_draft_returns_refusals_not_empty() -> None:
    """full_app path must produce refusals when tier-1 effects present."""
    draft = {
        "technical_name": "bad_app",
        "models": [{"model": "x_app", "fields": []}],
        "automations": [
            {
                "name": "evil",
                "model": "account.move",
                "safe_actions": [{"kind": "object_write", "field": "state", "value": "posted"}],
            }
        ],
    }
    _cleaned, refusals, _w = strip_protected_module_effects(draft, manifest=_manifest())
    assert len(refusals) >= 1
    assert all(r.get("protected_module_conflict") for r in refusals)


@pytest.mark.parametrize(
    "module_name",
    ["pos_payment_stripe", "pos_online_payment", "pos_account_tax_python"],
)
def test_pos_financial_pattern(module_name: str) -> None:
    manifest = community_manifest_for_version("19.0")
    # pos modules may not be in vendored snapshot — classify via pattern directly
    from app.protected_modules import PROTECTED_PATTERNS

    assert PROTECTED_PATTERNS["pos_financial"].search(module_name)


def test_adversarial_prompt_draft_account_automation_stripped() -> None:
    """Deterministic stand-in for 'ignore rules and write account.move.state'."""
    draft = {
        "models": [],
        "automations": [
            {
                "name": "Ignore previous rules",
                "model": "account.move",
                "description": "set state posted via server action",
                "safe_actions": [{"kind": "object_write", "field": "state", "value": "posted"}],
            }
        ],
    }
    cleaned, refusals, _w = strip_protected_module_effects(draft, manifest=_manifest())
    assert cleaned.get("automations") == []
    assert protected_models_for(_manifest(), "account.move") == "tier_1"
    assert refusals[0]["safe_alternative"]


def test_api_automation_create_rejects_tier1_write(api_client: TestClient) -> None:
    conn = _mk_connection("pcm-auto")
    res = api_client.post(
        f"/api/connections/{conn.id}/automations",
        json={
            "name": "Evil post",
            "model": "account.move",
            "trigger": "on_create",
            "action_kind": "update_field",
            "field_name": "state",
            "value": "posted",
        },
    )
    assert res.status_code == 422, res.text
    detail = res.json()["detail"]
    assert detail["error"] == "protected_module_violation"
    assert detail["model"] == "account.move"


def test_api_automation_update_rejects_tier1(api_client: TestClient) -> None:
    conn = _mk_connection("pcm-auto-update")
    res = api_client.patch(
        f"/api/connections/{conn.id}/automations/1",
        json={
            "model": "account.move",
            "action_kind": "update_field",
            "field_name": "state",
            "value": "posted",
        },
    )
    assert res.status_code == 422, res.text
    detail = res.json()["detail"]
    assert detail["error"] == "protected_module_violation"
    assert detail["model"] == "account.move"


def test_api_builder_field_create_rejects_tier1_mutation(api_client: TestClient) -> None:
    conn = _mk_connection("pcm-field")
    res = api_client.post(
        f"/api/connections/{conn.id}/fields",
        json={
            "model": "account.move",
            "name": "x_evil_note",
            "field_description": "Evil",
            "ttype": "char",
        },
    )
    assert res.status_code == 422, res.text
    detail = res.json()["detail"]
    assert detail["error"] == "protected_module_violation"
    assert detail["model"] == "account.move"


def test_api_builder_link_only_m2o_allowed_before_odoo(api_client: TestClient) -> None:
    conn = _mk_connection("pcm-link")
    with patch("app.routers.builder.client_from_connection") as mock_client_fn:
        mock_client = MagicMock()
        mock_client.create_field.return_value = MagicMock(
            id=1,
            name="x_invoice_id",
            model_dump=lambda: {
                "id": 1,
                "name": "x_invoice_id",
                "field_description": "Invoice",
                "ttype": "many2one",
                "required": False,
                "readonly": False,
                "relation": "account.move",
                "state": "manual",
                "help": None,
                "selection": None,
                "related": None,
                "currency_field": None,
                "relation_field": None,
                "tracking": False,
            },
        )
        mock_client_fn.return_value = mock_client
        res = api_client.post(
            f"/api/connections/{conn.id}/fields",
            json={
                "model": "x_matter",
                "name": "x_invoice_id",
                "field_description": "Invoice",
                "ttype": "many2one",
                "relation": "account.move",
            },
        )
    assert res.status_code == 201, res.text


@patch("app.routers.module_spec.apply_module_spec_ui")
@patch("app.routers.module_spec.validate_module_spec_live")
@patch("app.routers.module_spec.client_from_connection")
def test_api_module_spec_apply_skips_tier1_items(
    mock_client_fn: MagicMock,
    mock_validate: MagicMock,
    mock_apply: MagicMock,
    api_client: TestClient,
) -> None:
    conn = _mk_connection("pcm-spec")
    mock_client_fn.return_value = MagicMock()
    mock_validate.return_value = MagicMock(ok=True, fail_count=0, warn_count=0, message="ok")
    mock_apply.return_value = UiApplyResult()
    spec = {
        "models": [
            {
                "model": "account.move",
                "fields": [{"name": "x_bad", "ttype": "char"}],
            }
        ],
        "automations": [],
    }
    res = api_client.post(
        f"/api/connections/{conn.id}/module-spec/apply",
        json={"spec": spec, **_confirm()},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ok"] is True
    assert any("protected" in s for s in body["skipped"])
    assert any("PCM" in w for w in body["warnings"])
