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
