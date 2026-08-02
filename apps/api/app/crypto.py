"""Fernet helpers for encrypting Odoo credentials at rest."""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from app.settings import settings


class CryptoError(Exception):
    pass


def _fernet() -> Fernet:
    key = settings.fernet_key.encode("utf-8")
    # Allow a stable local-dev key derived from the placeholder string.
    if settings.fernet_key.startswith("dev-only-"):
        # Deterministic 32-byte urlsafe key for local only — NEVER use in prod.
        import base64
        import hashlib

        digest = hashlib.sha256(b"odoo-custom-local-dev-fernet-v1").digest()
        key = base64.urlsafe_b64encode(digest)
    try:
        return Fernet(key)
    except Exception as exc:  # noqa: BLE001
        raise CryptoError(
            "Invalid FERNET_KEY. Generate with: "
            'python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
        ) from exc


def encrypt_secret(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_secret(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise CryptoError("Failed to decrypt credential — wrong FERNET_KEY?") from exc
