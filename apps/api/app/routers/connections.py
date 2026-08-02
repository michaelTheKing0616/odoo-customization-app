"""CRUD for saved Odoo connections (credentials encrypted at rest)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.capabilities import capabilities_from_version
from app.crypto import encrypt_secret
from app.db import get_db
from app.db_models import OdooConnection
from app.odoo_service import OdooClientError, probe_credentials
from app.schemas import ConnectionCreate, ConnectionOut, ConnectionUpdate, ProbeResult

router = APIRouter(prefix="/connections", tags=["connections"])


def _connection_out(row: OdooConnection) -> ConnectionOut:
    return ConnectionOut(
        id=row.id,
        name=row.name,
        url=row.url,
        db_name=row.db_name,
        username=row.username,
        server_version=row.server_version,
        created_at=row.created_at,
        updated_at=row.updated_at,
        capabilities=capabilities_from_version(row.server_version, url=row.url),
    )


@router.get("", response_model=list[ConnectionOut])
def list_connections(db: Session = Depends(get_db)) -> list[ConnectionOut]:
    rows = db.query(OdooConnection).order_by(OdooConnection.created_at.desc()).all()
    return [_connection_out(r) for r in rows]


@router.post("", response_model=ConnectionOut, status_code=201)
def create_connection(body: ConnectionCreate, db: Session = Depends(get_db)) -> ConnectionOut:
    server_version: str | None = None
    if body.verify:
        try:
            _, server_version = probe_credentials(
                body.url, body.db_name, body.username, body.password
            )
        except OdooClientError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    row = OdooConnection(
        name=body.name,
        url=body.url.rstrip("/"),
        db_name=body.db_name,
        username=body.username,
        secret_encrypted=encrypt_secret(body.password),
        server_version=server_version,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _connection_out(row)


@router.get("/{connection_id}", response_model=ConnectionOut)
def get_connection(connection_id: str, db: Session = Depends(get_db)) -> ConnectionOut:
    row = db.get(OdooConnection, connection_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Connection not found")
    return _connection_out(row)


@router.patch("/{connection_id}", response_model=ConnectionOut)
def update_connection(
    connection_id: str, body: ConnectionUpdate, db: Session = Depends(get_db)
) -> ConnectionOut:
    row = db.get(OdooConnection, connection_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Connection not found")

    if body.name is not None:
        row.name = body.name
    if body.url is not None:
        row.url = body.url.rstrip("/")
    if body.db_name is not None:
        row.db_name = body.db_name
    if body.username is not None:
        row.username = body.username
    if body.password is not None:
        row.secret_encrypted = encrypt_secret(body.password)

    if body.verify:
        from app.crypto import decrypt_secret

        password = body.password if body.password is not None else decrypt_secret(row.secret_encrypted)
        try:
            _, version = probe_credentials(row.url, row.db_name, row.username, password)
            row.server_version = version
        except OdooClientError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    elif body.url is not None or body.db_name is not None or body.username is not None or body.password is not None:
        # Connection endpoint changed without verify — clear stale version so UI
        # cannot keep a wrong capability matrix until the next probe.
        row.server_version = None

    db.commit()
    db.refresh(row)
    return _connection_out(row)


@router.delete("/{connection_id}", status_code=204)
def delete_connection(connection_id: str, db: Session = Depends(get_db)) -> None:
    from app.db_models import MetadataSnapshot, PromotedModule, SandboxValidation

    row = db.get(OdooConnection, connection_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Connection not found")
    # Cascade app-DB metadata for this connection (Odoo-side customizations remain).
    db.query(MetadataSnapshot).filter(MetadataSnapshot.connection_id == connection_id).delete(
        synchronize_session=False
    )
    db.query(SandboxValidation).filter(SandboxValidation.connection_id == connection_id).delete(
        synchronize_session=False
    )
    db.query(PromotedModule).filter(PromotedModule.connection_id == connection_id).delete(
        synchronize_session=False
    )
    db.delete(row)
    db.commit()


@router.post("/{connection_id}/probe", response_model=ProbeResult)
def probe_connection(connection_id: str, db: Session = Depends(get_db)) -> ProbeResult:
    row = db.get(OdooConnection, connection_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Connection not found")
    from app.capabilities import sample_installed_modules
    from app.crypto import decrypt_secret
    from app.odoo_service import client_from_connection

    try:
        uid, version = probe_credentials(
            row.url, row.db_name, row.username, decrypt_secret(row.secret_encrypted)
        )
        row.server_version = version
        db.commit()
        db.refresh(row)
        mods: list[str] = []
        try:
            client = client_from_connection(row)
            mods = sample_installed_modules(client)
        except OdooClientError:
            mods = []
        return ProbeResult(
            ok=True,
            uid=uid,
            server_version=row.server_version,
            capabilities=capabilities_from_version(
                row.server_version, url=row.url, installed_modules=mods
            ),
        )
    except OdooClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
