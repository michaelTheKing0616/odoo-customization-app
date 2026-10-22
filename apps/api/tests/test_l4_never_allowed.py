"""GATE-L4-11 / 5C-07: never-allowed stays unbypassable. L4 is not enabled."""

from __future__ import annotations

from app.changeset.ops import OP_CATALOG
from app.worker_bot.l4_policy import l4_may_apply

# Hypothetical tenant list: every catalog op. This is not an L4 enablement.
_EVERY_OP = frozenset(OP_CATALOG)
_PLAN_HASH = "a" * 16
_VERIFIED_STAGING = (
    {"plan_hash": _PLAN_HASH, "verified": True, "environment": "staging"},
)


def _permissive(
    *,
    op_type: str,
    model: str = "",
    method: str = "",
    values: dict | None = None,
    args: tuple | list | None = None,
    params: dict | None = None,
    allow_list: frozenset[str] | None = None,
) -> bool:
    return l4_may_apply(
        risk="R1",
        op_type=op_type,
        rows=1,
        mode_t=True,
        staging_verified=True,
        plan_mode="T",
        plan_hash=_PLAN_HASH,
        staging_applies=_VERIFIED_STAGING,
        model=model,
        method=method,
        values=values,
        args=args,
        params=params,
        allow_list=_EVERY_OP if allow_list is None else allow_list,
    )


def test_full_catalog_allow_list_is_every_op_type() -> None:
    assert _EVERY_OP
    assert "data.unlink" in _EVERY_OP
    assert "config_param.set" in _EVERY_OP


def test_l4_refuses_unlink_res_users_even_when_every_op_is_allowlisted() -> None:
    assert (
        _permissive(
            op_type="data.unlink",
            params={"model": "res.users", "ids": [1]},
        )
        is False
    )
    assert (
        l4_may_apply(
            risk="R1",
            op_type="user.unlink",
            rows=1,
            mode_t=True,
            staging_verified=True,
            plan_mode="T",
            plan_hash=_PLAN_HASH,
            staging_applies=_VERIFIED_STAGING,
            model="res.users",
            method="unlink",
            allow_list=_EVERY_OP | {"user.unlink"},
        )
        is False
    )


def test_l4_refuses_touching_user_apikeys_even_when_every_op_is_allowlisted() -> None:
    assert (
        _permissive(
            op_type="data.update_batch",
            model="res.users.apikeys",
            method="read",
        )
        is False
    )
    assert (
        _permissive(
            op_type="data.update_batch",
            params={"model": "res.users.apikeys", "domain": [["id", "=", 1]], "values": {}},
        )
        is False
    )


def test_l4_refuses_protected_param_write_even_when_every_op_is_allowlisted() -> None:
    assert (
        _permissive(
            op_type="config_param.set",
            params={"key": "database.secret", "value": "x"},
        )
        is False
    )
    assert (
        _permissive(
            op_type="config_param.set",
            args=("database.secret", "x"),
        )
        is False
    )


def test_l4_still_allows_benign_r1_when_every_op_is_allowlisted() -> None:
    assert _permissive(op_type="mail_template.create") is True
