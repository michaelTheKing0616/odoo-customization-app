"""Promote a sandbox-validated module zip onto a real Odoo connection."""

from __future__ import annotations

import hashlib
import logging
import os
import subprocess
import tempfile
import time
import zipfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from module_generator import zip_has_python_models, zip_technical_name
from odoo_client import OdooClient
from odoo_client.client import OdooClientError

from app.db_models import SandboxValidation
from app.zip_safety import safe_extract, validate_zip_bytes

logger = logging.getLogger(__name__)

VALIDATION_TTL_HOURS = 2
PRIMARY_ODOO_CONTAINER = os.environ.get("ODOO_CONTAINER", "odoo-custom-odoo")
LOCAL_HOSTS = {"127.0.0.1", "localhost", "0.0.0.0", "host.docker.internal"}


@dataclass
class PromoteResult:
    ok: bool
    module: str
    method: str  # filesystem | base_import_module
    message: str
    module_state: str | None = None


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def is_local_docker_connection(url: str, *, port: int = 8069) -> bool:
    parsed = urlparse(url if "://" in url else f"http://{url}")
    host = (parsed.hostname or "").lower()
    p = parsed.port or (443 if parsed.scheme == "https" else 80)
    return host in LOCAL_HOSTS and p == port


def record_sandbox_validation(
    db: Session,
    *,
    connection_id: str,
    module_name: str,
    zip_bytes: bytes,
) -> SandboxValidation:
    row = SandboxValidation(
        connection_id=connection_id,
        module_name=module_name,
        zip_sha256=sha256_bytes(zip_bytes),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=VALIDATION_TTL_HOURS),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_valid_validation(
    db: Session,
    *,
    validation_id: str,
    connection_id: str,
    zip_bytes: bytes,
) -> SandboxValidation:
    row = db.get(SandboxValidation, validation_id)
    if row is None or row.connection_id != connection_id:
        raise LookupError("Sandbox validation not found for this connection")
    if row.consumed_at is not None:
        raise ValueError("Sandbox validation already consumed — re-run sandbox")
    now = datetime.now(timezone.utc)
    expires = row.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires < now:
        raise ValueError("Sandbox validation expired — re-run sandbox")
    if row.zip_sha256 != sha256_bytes(zip_bytes):
        raise ValueError("Zip does not match sandbox-validated artifact (sha256 mismatch)")
    return row


def consume_validation(db: Session, row: SandboxValidation) -> None:
    row.consumed_at = datetime.now(timezone.utc)
    db.add(row)
    db.commit()


def _docker_cp_module(zip_bytes: bytes, module_name: str, container: str) -> None:
    validate_zip_bytes(zip_bytes)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
            safe_extract(zf, tmp_path)
        module_dir = tmp_path / module_name
        if not (module_dir / "__manifest__.py").exists():
            raise ValueError(f"Zip missing {module_name}/__manifest__.py")
        subprocess.run(
            ["docker", "exec", container, "rm", "-rf", f"/mnt/extra-addons/{module_name}"],
            check=False,
            capture_output=True,
            text=True,
        )
        cp = subprocess.run(
            ["docker", "cp", str(module_dir), f"{container}:/mnt/extra-addons/{module_name}"],
            capture_output=True,
            text=True,
            check=False,
        )
        if cp.returncode != 0:
            raise RuntimeError(f"docker cp failed: {cp.stderr or cp.stdout}")


def _wait_local_http(url: str, timeout_s: float = 90) -> None:
    import urllib.request

    login = url.rstrip("/") + "/web/login"
    deadline = time.time() + timeout_s
    last: Exception | None = None
    while time.time() < deadline:
        try:
            urllib.request.urlopen(login, timeout=5)  # noqa: S310
            return
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(2)
    raise TimeoutError(f"Odoo not ready after restart: {last}")


def promote_module_zip(
    client: OdooClient,
    zip_bytes: bytes,
    *,
    prefer_filesystem: bool | None = None,
    restart_container: bool = True,
) -> PromoteResult:
    module = zip_technical_name(zip_bytes)
    has_py = zip_has_python_models(zip_bytes)
    use_fs = prefer_filesystem
    if use_fs is None:
        use_fs = is_local_docker_connection(client.config.url) and has_py

    if use_fs:
        if not is_local_docker_connection(client.config.url):
            raise OdooClientError(
                "Filesystem promote only works for local Docker Odoo on :8069. "
                "Export with install_mode=data for remote base_import_module."
            )
        _docker_cp_module(zip_bytes, module, PRIMARY_ODOO_CONTAINER)
        if restart_container:
            subprocess.run(
                ["docker", "restart", PRIMARY_ODOO_CONTAINER],
                check=True,
                capture_output=True,
                text=True,
            )
            _wait_local_http(client.config.url)
            # Re-auth after restart
            client.connect()
        row = client.install_module_by_name(module)
        return PromoteResult(
            ok=True,
            module=module,
            method="filesystem",
            message=f"Installed {module} via extra-addons filesystem",
            module_state=str(row.get("state")),
        )

    if has_py:
        from app.hosting import hosting_hint_from_url

        hint = hosting_hint_from_url(client.config.url)
        if hint == "online":
            raise OdooClientError(
                "Odoo Online cannot install custom Python modules. "
                "Re-export with install_mode=data (XML/metadata only) for "
                "base_import_module, or promote on Odoo.sh / self-hosted Docker "
                "where filesystem Option A is available."
            )
        raise OdooClientError(
            "This zip contains Python models. Remote promote requires install_mode=data "
            "(ir.model XML) or a local Docker connection with filesystem access "
            f"(detected hosting={hint})."
        )

    info = client.import_module_zip(zip_bytes, force=True)
    # After data import, module may appear as installed via base_import_module
    state_row = client.get_module_state(module)
    return PromoteResult(
        ok=True,
        module=module,
        method="base_import_module",
        message=f"Imported {module} via base_import_module (state={info.get('state')})",
        module_state=(state_row or {}).get("state") or info.get("state"),
    )
