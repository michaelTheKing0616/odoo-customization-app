"""BV-STORE: ORM models for verify_runs / verify_artifacts (migration 4b7e9c1d2a3f).

On the shared Base so alembic autogenerate sees them (drift parity). Imported by
app.db_models.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class VerifyRunRow(Base):
    __tablename__ = "verify_runs"
    __table_args__ = (Index("ix_verify_runs_connection_run", "connection_id", "run_id"),)

    run_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    connection_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("odoo_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workspace_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    changeset_id: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    layers: Mapped[Any] = mapped_column(JSON, nullable=False, server_default=text("'[]'"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class VerifyArtifactRow(Base):
    __tablename__ = "verify_artifacts"

    artifact_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("verify_runs.run_id", ondelete="CASCADE"), nullable=False, index=True
    )
    connection_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    blob_path: Mapped[str] = mapped_column(String, nullable=False)
    content_type: Mapped[str] = mapped_column(
        String, nullable=False, server_default=text("'image/png'")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
