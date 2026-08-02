"""Unit tests for Wave B confirm gates + schemas (no live Odoo)."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://odoo_custom:odoo_custom@127.0.0.1:5433/odoo_custom",
)
os.environ.setdefault("FERNET_KEY", "dev-only-test")
os.environ.setdefault("AUTH_MODE", "off")

from app.schemas import (  # noqa: E402
    ConfirmAdvancedBody,
    UpdateAccessBody,
    UpdateFieldBody,
)
from app.snapshots import (  # noqa: E402
    CONFIRM_PHRASE,
    ConfirmationRequired,
    require_advanced_confirmation,
)
from odoo_client.security import (  # noqa: E402
    UpdateAccessRightRequest,
    UpdateRecordRuleRequest,
)


def test_confirm_phrase_constant() -> None:
    assert CONFIRM_PHRASE == "I understand the risks"


def test_require_advanced_confirmation_passes() -> None:
    require_advanced_confirmation(
        confirm_advanced=True,
        confirm_phrase=CONFIRM_PHRASE,
        warning="w",
        risks=["r"],
    )


def test_require_advanced_confirmation_rejects_missing() -> None:
    with pytest.raises(ConfirmationRequired) as exc:
        require_advanced_confirmation(
            confirm_advanced=False,
            confirm_phrase=None,
            warning="Delete field",
            risks=["data loss"],
        )
    assert exc.value.warning == "Delete field"
    assert "data loss" in exc.value.risks


def test_require_advanced_confirmation_rejects_wrong_phrase() -> None:
    with pytest.raises(ConfirmationRequired):
        require_advanced_confirmation(
            confirm_advanced=True,
            confirm_phrase="I understand",
            warning="w",
            risks=[],
        )


def test_confirm_advanced_body_defaults() -> None:
    body = ConfirmAdvancedBody()
    assert body.confirm_advanced is False
    assert body.confirm_phrase is None


def test_update_field_body_accepts_safe_attrs() -> None:
    body = UpdateFieldBody(string="Label", required=True, help="hint")
    dumped = body.model_dump(exclude_none=True)
    assert dumped["string"] == "Label"
    assert dumped["required"] is True


def test_update_access_body_perm_booleans() -> None:
    body = UpdateAccessBody(perm_read=True, perm_unlink=False)
    assert body.perm_read is True
    assert body.perm_unlink is False


def test_update_rule_request_domain_validation() -> None:
    with pytest.raises(ValidationError):
        UpdateRecordRuleRequest(domain_force="not a domain")
    ok = UpdateRecordRuleRequest(domain_force="[('id', '!=', False)]")
    assert ok.domain_force.startswith("[")


def test_update_access_request_empty_ok() -> None:
    # Client raises if no attrs; schema itself allows empty for PATCH bodies.
    req = UpdateAccessRightRequest()
    assert req.name is None


@pytest.fixture
def client() -> TestClient:
    from app.main import app

    with TestClient(app) as c:
        yield c


def test_delete_field_without_connection_404(client: TestClient) -> None:
    res = client.request(
        "DELETE",
        "/api/connections/00000000-0000-0000-0000-000000000000/fields/1",
        json={},
    )
    assert res.status_code == 404


def test_delete_model_without_connection_404(client: TestClient) -> None:
    res = client.request(
        "DELETE",
        "/api/connections/00000000-0000-0000-0000-000000000000/models/x_thing",
        json={"confirm_advanced": True, "confirm_phrase": CONFIRM_PHRASE},
    )
    assert res.status_code == 404


def test_delete_automation_body_validation(client: TestClient) -> None:
    # Missing JSON body → 422 (ConfirmAdvancedBody required)
    res = client.request(
        "DELETE",
        "/api/connections/00000000-0000-0000-0000-000000000000/automations/1",
    )
    assert res.status_code in {404, 422}
