"""Access live pack must not create a global ir.rule without the confirm phrase."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.routers.access import (
    APPLY_LIVE_PACK_RISKS,
    APPLY_LIVE_PACK_WARNING,
    ApplyMultiCompanyLiveBody,
    apply_multi_company_live_route,
)
from app.snapshots import CONFIRM_PHRASE, ConfirmationRequired, require_advanced_confirmation

pytestmark = pytest.mark.no_app_db


def test_live_pack_warning_names_global_ir_rule() -> None:
    assert "ir.rule" in APPLY_LIVE_PACK_WARNING
    assert any("global ir.rule" in risk for risk in APPLY_LIVE_PACK_RISKS)


def test_require_confirm_blocks_unconfirmed_live_pack() -> None:
    with pytest.raises(ConfirmationRequired) as exc:
        require_advanced_confirmation(
            confirm_advanced=False,
            confirm_phrase=None,
            warning=APPLY_LIVE_PACK_WARNING,
            risks=APPLY_LIVE_PACK_RISKS,
        )
    assert "ir.rule" in exc.value.warning


def test_apply_live_pack_route_requires_confirm_phrase() -> None:
    body = ApplyMultiCompanyLiveBody(models=["x_visitor_log"])
    with (
        patch("app.routers.access._client") as client_fn,
        patch("app.multi_company_pack.apply_multi_company_live") as apply_live,
    ):
        with pytest.raises(HTTPException) as exc:
            apply_multi_company_live_route("cid", body, db=MagicMock())
    assert exc.value.status_code == 403
    detail = exc.value.detail
    assert detail["requires_confirmation"] is True
    assert detail["confirm_phrase"] == CONFIRM_PHRASE
    assert "ir.rule" in detail["warning"]
    client_fn.assert_not_called()
    apply_live.assert_not_called()


def test_apply_live_pack_route_with_confirm_phrase_writes() -> None:
    body = ApplyMultiCompanyLiveBody(
        models=["x_visitor_log"],
        confirm_advanced=True,
        confirm_phrase=CONFIRM_PHRASE,
    )
    fake_client = MagicMock()
    with (
        patch("app.routers.access._client", return_value=fake_client) as client_fn,
        patch(
            "app.multi_company_pack.apply_multi_company_live",
            return_value={
                "ok": True,
                "models": ["x_visitor_log"],
                "fields_created": 1,
                "rules_created": 1,
                "warnings": [],
            },
        ) as apply_live,
    ):
        out = apply_multi_company_live_route("cid", body, db=MagicMock())
    assert out.ok is True
    assert out.rules_created == 1
    client_fn.assert_called_once()
    apply_live.assert_called_once_with(fake_client, ["x_visitor_log"])
