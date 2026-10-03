"""Power Ops _exec_step must classify before execute_kw."""

from __future__ import annotations

import pytest
from odoo_client.client import OdooClientError

from app.power_ops_recipes import RecipeStep, _exec_step


class _FakeClient:
    def execute_kw(self, *args: object, **kwargs: object) -> None:
        raise AssertionError("execute_kw must not be called")


def test_unlink_res_users_raises_forbidden_without_rpc() -> None:
    client = _FakeClient()
    step = RecipeStep(kind="unlink", label="Delete")
    with pytest.raises(OdooClientError, match=r"forbidden.*res\.users.*unlink"):
        _exec_step(client, "res.users", step, [1])


def test_ir_config_parameter_secret_write_forbidden() -> None:
    client = _FakeClient()
    step = RecipeStep(
        kind="write",
        values={"key": "database.secret", "value": "x"},
        label="Write secret param",
    )
    with pytest.raises(OdooClientError, match=r"forbidden.*ir\.config_parameter.*write"):
        _exec_step(client, "ir.config_parameter", step, [1])
