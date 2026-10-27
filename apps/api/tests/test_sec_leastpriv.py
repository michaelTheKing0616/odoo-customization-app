"""SEC-LEASTPRIV AC1. Least privilege toward Odoo (handover §6.4).

Passing check stays an ordinary assert. Each missing behaviour is its own
``pytest.mark.xfail(strict=True)`` and the reason starts with a SEC-6.4 id.
The Code Runner HTTP 403 is not inside those xfails.

``assert_developer_role`` already returns HTTP 403 for an accounts-mode viewer
and builder. A developer, admin, or owner still passes that gate.

Product lines whose deletion would fail the hard asserts:
- viewer 403: ``apps/api/app/code_studio_gating.py:30`` ``raise HTTPException``
  (``status_code=403`` on line 31) inside ``assert_developer_role``
- builder 403: that same raise
- developer pass: delete ``"developer"`` from ``apps/api/app/account_service.py:116``
  (``can_develop``)
- admin pass: delete ``"admin"`` from that set
- owner pass: delete ``"owner"`` from that set

Still missing, so strict xfail:
- SEC-6.4-LOOK: ``key_grant_for_principal`` for ``look-only`` is ``read_only``
  with ``writes`` False, including when ``requested="write"``.
- SEC-6.4-INSTALL: ``role_may_use`` is False for ``viewer`` and ``builder`` on
  ``install`` and ``code_runner``, and True for ``developer`` on both.
- SEC-6.4-ALLOW: ``enforce_install_allow_list`` returns None only for
  ``ingenium_generated`` or ``tope_approved``. Every other provenance raises
  ``InstallRefused``. A module name is not provenance.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest
from fastapi import HTTPException

from app.code_studio_gating import assert_developer_role
from app.workspace_auth import WorkspaceAuth

pytestmark = pytest.mark.no_app_db

_LOOK_ONLY = "look-only"
_DENIED_ROLES = ("viewer", "builder")
_PASS_ROLES = ("developer", "admin", "owner")
_FEATURES = ("code_runner", "install")
_ALLOWED_PROVENANCE = ("ingenium_generated", "tope_approved")
_REFUSED_PROVENANCE = (None, "", "community", "client", "client_approved")


def _caps():
    import app.capabilities as capabilities

    return capabilities


def _key_grant():
    fn = getattr(_caps(), "key_grant_for_principal", None)
    if not callable(fn):
        raise AssertionError(
            "app.capabilities.key_grant_for_principal is missing; "
            "a look-only principal must receive a read-only key"
        )
    return fn


def _role_may_use():
    fn = getattr(_caps(), "role_may_use", None)
    if not callable(fn):
        raise AssertionError(
            "app.capabilities.role_may_use is missing; "
            "viewers and builders must not use Code Runner or install"
        )
    return fn


def _enforce_install():
    caps = _caps()
    fn = getattr(caps, "enforce_install_allow_list", None)
    refused = getattr(caps, "InstallRefused", None)
    if not callable(fn) or not isinstance(refused, type) or not issubclass(refused, Exception):
        raise AssertionError(
            "app.capabilities.enforce_install_allow_list and InstallRefused "
            "are missing; the install allow-list must be enforced on the server"
        )
    return fn, refused


def _read_only_grant(**kwargs: Any) -> Mapping[str, Any]:
    try:
        grant = _key_grant()(_LOOK_ONLY, **kwargs)
    except TypeError as exc:
        raise AssertionError(
            "key_grant_for_principal('look-only') must return a read-only key grant"
        ) from exc
    if not isinstance(grant, Mapping):
        raise AssertionError(
            "look-only key grant must be a mapping with access='read_only' and writes=False"
        )
    return grant


def _assert_read_only(grant: Mapping[str, Any]) -> None:
    assert grant["access"] == "read_only"
    assert grant["writes"] is False


def _accounts(role: str) -> WorkspaceAuth:
    return WorkspaceAuth(mode="accounts", role=role, user_id="u", workspace_id="w")


def test_ac1_negative_accounts_code_runner_role_gate() -> None:
    """Accounts-mode Code Runner gate. Ordinary test. Not an xfail.

    Viewer and builder 403 fail if the ``raise HTTPException`` in
    ``assert_developer_role`` is deleted (``code_studio_gating.py:30``).
    Developer, admin, and owner passes fail if that role is deleted from
    ``can_develop`` (``account_service.py:116``).
    """
    for role in _DENIED_ROLES:
        with pytest.raises(HTTPException) as caught:
            assert_developer_role(_accounts(role))
        assert caught.value.status_code == 403, role
    for role in _PASS_ROLES:
        assert assert_developer_role(_accounts(role)) is None, role


@pytest.mark.xfail(strict=True, reason="SEC-6.4-LOOK: no look-only read-only key")
def test_ac1_positive_look_only_principal_gets_read_only_key() -> None:
    """A look-only principal gets a read-only key, even when write is requested."""
    _assert_read_only(_read_only_grant())
    _assert_read_only(_read_only_grant(requested="write"))


@pytest.mark.xfail(
    strict=True,
    reason="SEC-6.4-INSTALL: viewers and builders are not denied install",
)
def test_ac1_negative_viewers_and_builders_are_denied_install() -> None:
    """``role_may_use`` denies install (and Code Runner) to viewer and builder.

    Does not call ``assert_developer_role``. The HTTP 403 is the ordinary test.
    Developer may use both features once ``role_may_use`` exists.
    """
    may = _role_may_use()
    assert may("developer", "code_runner") is True
    assert may("developer", "install") is True
    for role in _DENIED_ROLES:
        for feature in _FEATURES:
            assert may(role, feature) is False


@pytest.mark.xfail(
    strict=True,
    reason=(
        "SEC-6.4-ALLOW: no server install allow-list limited to "
        "ingenium_generated or tope_approved"
    ),
)
def test_ac1_negative_off_list_provenance_is_refused() -> None:
    """Only ingenium_generated and tope_approved pass. A module name is not provenance."""
    enforce, refused = _enforce_install()
    for provenance in _ALLOWED_PROVENANCE:
        assert enforce("sale", provenance=provenance) is None
    for provenance in _REFUSED_PROVENANCE:
        with pytest.raises(refused):
            enforce("sale", provenance=provenance)
    with pytest.raises(refused):
        enforce("x_ingenium_generated", provenance=None)
