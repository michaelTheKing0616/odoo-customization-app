"""Track 5A — RPC classification tests."""

from __future__ import annotations

from app.rpc_classify import classify_rpc, policy_allows


def test_read_is_read() -> None:
    c = classify_rpc("res.partner", "search_read", ids=[1])
    assert c.risk == "READ"
    assert c.bucket == "A"
    assert c.forbidden is False


def test_create_is_reversible() -> None:
    c = classify_rpc("res.partner", "create", values={"name": "Acme"})
    assert c.risk == "REVERSIBLE"
    assert c.bucket == "B"
    assert c.forbidden is False


def test_unlink_destructive_and_forbidden() -> None:
    blocked = classify_rpc("res.users", "unlink", ids=[2])
    assert blocked.risk == "DESTRUCTIVE"
    assert blocked.forbidden is True
    assert blocked.bucket == "C"

    allowed_shape = classify_rpc("res.partner", "unlink", ids=[99])
    assert allowed_shape.risk == "DESTRUCTIVE"
    assert allowed_shape.forbidden is False
    assert allowed_shape.bucket == "C"


def test_security_models_destructive() -> None:
    c = classify_rpc("ir.model.access", "write", ids=[1], values={"perm_read": True})
    assert c.risk == "DESTRUCTIVE"
    assert c.forbidden is False
    assert c.bucket == "C"
    for model in ("ir.access", "ir.model.access", "ir.rule", "res.groups"):
        created = classify_rpc(model, "create", values={"name": "acl"})
        assert created.risk == "DESTRUCTIVE"
        assert created.forbidden is False
        assert created.bucket == "C"


def test_billable_depends_on_edition() -> None:
    community = classify_rpc("ir.module.module", "button_install", ids=[1], edition="community")
    assert community.risk == "DESTRUCTIVE"
    assert community.forbidden is False

    enterprise = classify_rpc(
        "ir.module.module",
        "button_install",
        ids=[1],
        edition="enterprise",
    )
    assert enterprise.risk == "BILLABLE"
    assert enterprise.bucket == "C"


def test_protected_params_forbidden() -> None:
    c = classify_rpc(
        "ir.config_parameter",
        "write",
        ids=[1],
        values={"database.secret": "x"},
    )
    assert c.forbidden is True
    assert c.risk == "DESTRUCTIVE"


def test_mass_write() -> None:
    c = classify_rpc("res.partner", "write", ids=list(range(51)), values={"name": "bulk"})
    assert c.risk == "DESTRUCTIVE"
    assert c.reason == "mass_write"


def test_policy_thresholds() -> None:
    read = classify_rpc("res.partner", "read", ids=[1])
    rev = classify_rpc("res.partner", "create", values={"name": "x"})
    dest = classify_rpc("res.partner", "unlink", ids=[1])

    assert policy_allows(read, environment="staging") is True
    assert policy_allows(rev, environment="staging") is True
    assert policy_allows(dest, environment="staging") is False

    assert policy_allows(read, environment="production") is True
    assert policy_allows(rev, environment="production") is False
    assert policy_allows(dest, environment="production") is False


def test_approved_does_not_override_never_allowed() -> None:
    c = classify_rpc("res.users", "unlink", ids=[1], approved=True)
    assert c.forbidden is True
    assert policy_allows(c, environment="staging") is False


def test_config_parameter_key_shape_forbidden() -> None:
    secret = classify_rpc(
        "ir.config_parameter",
        "write",
        ids=[1],
        values={"key": "database.secret", "value": "anything"},
    )
    assert secret.forbidden is True
    assert secret.reason == "protected_param"

    url = classify_rpc(
        "res.partner",
        "create",
        values={"key": "web.base.url", "value": "http://x"},
    )
    assert url.forbidden is True
    assert url.reason == "protected_param"

    approved = classify_rpc(
        "ir.config_parameter",
        "write",
        ids=[1],
        values={"key": "database.secret", "value": "x"},
        approved=True,
    )
    assert approved.forbidden is True


def test_set_param_args_forbidden() -> None:
    c = classify_rpc("ir.config_parameter", "set_param", args=("database.secret", "x"))
    assert c.forbidden is True
    assert c.reason == "protected_param"
    assert classify_rpc(
        "ir.config_parameter",
        "set_param",
        args=("database.secret", "x"),
        approved=True,
    ).forbidden is True


def test_apikeys_any_method_forbidden() -> None:
    read_c = classify_rpc("res.users.apikeys", "read", ids=[1])
    assert read_c.forbidden is True
    assert read_c.reason == "never_allowed"

    search_read_c = classify_rpc("res.users.apikeys", "search_read")
    assert search_read_c.forbidden is True
    assert search_read_c.reason == "never_allowed"
