"""Ingenium-side storage for the builders: layer history and pinned comments.

Nothing here touches Odoo. History keeps layer archs and the combined screen
Odoo returned (structure only, never record contents).
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.db_models import ViewBuilderItem, ViewComment, ViewLayerVersion

logger = logging.getLogger(__name__)
MAX_VERSIONS = 200


def _ensure_tables(db: Session) -> None:
    bind = db.get_bind()
    ViewLayerVersion.__table__.create(bind=bind, checkfirst=True)
    ViewComment.__table__.create(bind=bind, checkfirst=True)
    ViewBuilderItem.__table__.create(bind=bind, checkfirst=True)


def record_version(db: Session, **kw: Any) -> str | None:
    """Best effort: a history write never blocks or undoes a publish."""
    try:
        _ensure_tables(db)
        summary = kw.pop("summary", []) or []
        row = ViewLayerVersion(summary=json.dumps([str(s)[:200] for s in summary][:50]), **kw)
        db.add(row)
        db.commit()
        return row.id
    except Exception as exc:  # noqa: BLE001
        logger.warning("view history write failed: %s", exc)
        db.rollback()
        return None


def version_out(row: ViewLayerVersion) -> dict[str, Any]:
    try:
        summary = json.loads(row.summary or "[]")
    except ValueError:
        summary = []
    return {
        "id": row.id, "action": row.action, "label": row.label, "summary": summary,
        "layer_active": bool(row.layer_active), "has_layer": bool(row.layer_arch),
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "odoo_major": row.odoo_major, "layer_view_id": row.layer_view_id,
    }


def list_versions(db: Session, connection_id: str, layer_name: str) -> list[ViewLayerVersion]:
    _ensure_tables(db)
    return (
        db.query(ViewLayerVersion)
        .filter(ViewLayerVersion.connection_id == connection_id, ViewLayerVersion.layer_name == layer_name)
        .order_by(ViewLayerVersion.created_at.desc())
        .limit(MAX_VERSIONS)
        .all()
    )


def get_version(db: Session, connection_id: str, version_id: str) -> ViewLayerVersion | None:
    _ensure_tables(db)
    return (
        db.query(ViewLayerVersion)
        .filter(ViewLayerVersion.connection_id == connection_id, ViewLayerVersion.id == version_id)
        .one_or_none()
    )


def name_version(db: Session, row: ViewLayerVersion, label: str) -> None:
    row.label = label.strip()[:120] or None
    db.commit()


# ----------------------------------------------------------------------------
# Comments
# ----------------------------------------------------------------------------

def comment_out(row: ViewComment) -> dict[str, Any]:
    return {
        "id": row.id, "node_id": row.node_id, "parent_id": row.parent_id, "author": row.author, "body": row.body,
        "resolved": bool(row.resolved), "created_at": row.created_at.isoformat() if row.created_at else None,
        "resolved_at": row.resolved_at.isoformat() if row.resolved_at else None,
    }


def list_comments(db: Session, connection_id: str, model: str, view_type: str) -> list[ViewComment]:
    _ensure_tables(db)
    return (
        db.query(ViewComment)
        .filter(ViewComment.connection_id == connection_id, ViewComment.model == model, ViewComment.view_type == view_type)
        .order_by(ViewComment.created_at.asc())
        .limit(1000)
        .all()
    )


def add_comment(db: Session, **kw: Any) -> ViewComment:
    _ensure_tables(db)
    row = ViewComment(**kw)
    db.add(row)
    db.commit()
    return row


def get_comment(db: Session, connection_id: str, comment_id: str) -> ViewComment | None:
    _ensure_tables(db)
    return db.query(ViewComment).filter(ViewComment.connection_id == connection_id, ViewComment.id == comment_id).one_or_none()


def set_resolved(db: Session, row: ViewComment, resolved: bool) -> None:
    row.resolved = resolved
    row.resolved_at = datetime.now(UTC) if resolved else None
    db.commit()


def delete_comment(db: Session, row: ViewComment) -> None:
    db.query(ViewComment).filter(ViewComment.parent_id == row.id).delete()
    db.delete(row)
    db.commit()


# ----------------------------------------------------------------------------
# Stage 2b: reusable sections and upgrade-guard baselines
# ----------------------------------------------------------------------------

def item_out(row: ViewBuilderItem) -> dict[str, Any]:
    try:
        payload = json.loads(row.payload or "{}")
    except ValueError:
        payload = {}
    return {"id": row.id, "kind": row.kind, "key": row.key, "name": row.name, "payload": payload,
            "created_at": row.created_at.isoformat() if row.created_at else None}


def list_items(db: Session, connection_id: str, kind: str, key: str | None = None) -> list[ViewBuilderItem]:
    _ensure_tables(db)
    q = db.query(ViewBuilderItem).filter(ViewBuilderItem.connection_id == connection_id, ViewBuilderItem.kind == kind)
    if key is not None:
        q = q.filter(ViewBuilderItem.key == key)
    return q.order_by(ViewBuilderItem.created_at.desc()).limit(200).all()


def get_item(db: Session, connection_id: str, item_id: str) -> ViewBuilderItem | None:
    _ensure_tables(db)
    return db.query(ViewBuilderItem).filter(ViewBuilderItem.connection_id == connection_id, ViewBuilderItem.id == item_id).first()


def save_item(db: Session, *, connection_id: str, kind: str, key: str, name: str, payload: dict[str, Any],
              replace_key: bool = False) -> ViewBuilderItem:
    _ensure_tables(db)
    row = None
    if replace_key:
        row = db.query(ViewBuilderItem).filter(ViewBuilderItem.connection_id == connection_id, ViewBuilderItem.kind == kind,
                                               ViewBuilderItem.key == key).first()
    if row is None:
        row = ViewBuilderItem(connection_id=connection_id, kind=kind, key=key, name=name[:120])
        db.add(row)
    row.name = name[:120]
    row.payload = json.dumps(payload)
    row.updated_at = datetime.now(UTC)
    db.commit()
    return row


def update_item(db: Session, row: ViewBuilderItem, payload: dict[str, Any]) -> None:
    row.payload = json.dumps(payload)
    row.updated_at = datetime.now(UTC)
    db.commit()


def delete_item(db: Session, row: ViewBuilderItem) -> None:
    db.delete(row)
    db.commit()


def save_guard(db: Session, connection_id: str, layer_name: str, payload: dict[str, Any]) -> None:
    """Best effort: a baseline write never blocks a publish."""
    try:
        save_item(db, connection_id=connection_id, kind="guard", key=layer_name, name=layer_name, payload=payload, replace_key=True)
    except Exception as exc:  # noqa: BLE001
        logger.warning("guard baseline write failed: %s", exc)
        db.rollback()


def get_guard(db: Session, connection_id: str, layer_name: str) -> dict[str, Any] | None:
    rows = list_items(db, connection_id, "guard", layer_name)
    return item_out(rows[0])["payload"] if rows else None
