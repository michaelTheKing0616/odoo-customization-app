"""Fernet encrypt/decrypt with CI-style ``dev-only-`` key fallback."""

from __future__ import annotations

import pytest

from app import crypto
from app.settings import settings


def test_dev_only_fernet_encrypt_decrypt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "fernet_key", "dev-only-ci-fernet-key")
    token = crypto.encrypt_secret("odoo-secret")
    assert token != "odoo-secret"
    assert crypto.decrypt_secret(token) == "odoo-secret"


def test_plaintext_stub_is_not_wrong_fernet_key() -> None:
    with pytest.raises(crypto.CryptoError, match="not encrypted"):
        crypto.decrypt_secret("dev-only-test")


def test_client_from_connection_maps_plaintext_secret() -> None:
    from types import SimpleNamespace

    from odoo_client.client import OdooClientError

    from app.odoo_service import client_from_connection

    row = SimpleNamespace(
        secret_encrypted="dev-only-test",
        url="http://127.0.0.1:8069",
        db_name="odoo_dev",
        username="admin",
        write_mode="standard",
    )
    with pytest.raises(OdooClientError, match="not encrypted"):
        client_from_connection(row)
