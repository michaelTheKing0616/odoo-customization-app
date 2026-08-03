"""Build a live OdooClient from a stored encrypted connection."""

from __future__ import annotations

from odoo_client import ConnectionConfig, OdooClient
from odoo_client.client import OdooClientError
from sqlalchemy.orm import Session

from app.crypto import decrypt_secret
from app.db_models import OdooConnection


def get_connection_or_404(db: Session, connection_id: str) -> OdooConnection:
    row = db.get(OdooConnection, connection_id)
    if row is None:
        raise LookupError(f"Connection {connection_id} not found")
    return row


def client_from_connection(
    row: OdooConnection,
    *,
    db: Session | None = None,
    watch_version: bool = False,
) -> OdooClient:
    secret = decrypt_secret(row.secret_encrypted)
    client = OdooClient(
        ConnectionConfig(
            url=row.url,
            db=row.db_name,
            username=row.username,
            password=secret,
        )
    )
    client.connect()
    if watch_version and db is not None:
        from app.version_watch import observe_server_version

        version = str(client.server_version().get("server_version", ""))
        observe_server_version(db, row, version, auto_health_check=True)
    return client


def probe_credentials(url: str, db_name: str, username: str, password: str) -> tuple[int, str]:
    client = OdooClient(
        ConnectionConfig(url=url, db=db_name, username=username, password=password)
    )
    uid = client.connect()
    version = str(client.server_version().get("server_version", ""))
    return uid, version


__all__ = [
    "OdooClientError",
    "client_from_connection",
    "get_connection_or_404",
    "probe_credentials",
]
