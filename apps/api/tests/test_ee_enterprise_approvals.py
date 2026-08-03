"""EE enterprise approvals driver fake test (CMP-10)."""

from __future__ import annotations

from typing import Any

from app.ee_drivers import probe_enterprise_approvals_driver


class _FakeClient:
    def __init__(self, *, installed: bool, has_model: bool) -> None:
        self._installed = installed
        self._has_model = has_model

    def execute_kw(
        self,
        model: str,
        method: str,
        args: list[Any],
        kwargs: dict[str, Any] | None = None,
    ) -> Any:
        if model == "ir.module.module" and method == "search_read":
            if self._installed:
                return [{"state": "installed"}]
            return []
        if model == "approval.request" and method == "fields_get":
            return {
                "name": {"type": "char"},
                "category_id": {"type": "many2one"},
                "request_status": {"type": "selection"},
                "request_owner_id": {"type": "many2one"},
            }
        raise AssertionError(f"{model}.{method}")

    def model_exists(self, model: str) -> bool:
        return self._has_model and model == "approval.request"


def test_enterprise_approvals_unavailable_without_module() -> None:
    status = probe_enterprise_approvals_driver(_FakeClient(installed=False, has_model=False))
    assert status.available is False


def test_enterprise_approvals_available_when_installed() -> None:
    status = probe_enterprise_approvals_driver(_FakeClient(installed=True, has_model=True))
    assert status.available is True
    assert status.driver_id == "enterprise_approval_requests"
