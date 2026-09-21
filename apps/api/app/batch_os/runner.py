"""Universal batch runner — intake → map → validate → dry-run → apply → audit."""

from __future__ import annotations

import uuid
from typing import Any, Protocol

from sqlalchemy.orm import Session

from app.batch_os.persistence import load_job, public_job_dict, save_job
from app.batch_os.types import BatchJobState, RiskTier


class BatchRecipe(Protocol):
    id: str
    risk: RiskTier
    title: str
    blurb: str

    def intake(
        self,
        *,
        connection_id: str,
        filename: str,
        headers: list[str],
        rows: list[dict[str, str]],
        extras: dict[str, Any] | None = None,
    ) -> BatchJobState: ...

    def map(self, state: BatchJobState, column_map: dict[str, str] | None = None) -> BatchJobState: ...

    def validate(self, state: BatchJobState, client: Any) -> BatchJobState: ...

    def dry_run(self, state: BatchJobState, client: Any) -> BatchJobState: ...

    def apply(
        self,
        state: BatchJobState,
        client: Any,
        *,
        post_after_create: bool = False,
    ) -> BatchJobState: ...


def new_job_id() -> str:
    return str(uuid.uuid4())


def run_phase(
    db: Session,
    recipe: BatchRecipe,
    *,
    phase: str,
    connection_id: str,
    client: Any | None = None,
    job_id: str | None = None,
    filename: str = "",
    headers: list[str] | None = None,
    rows: list[dict[str, str]] | None = None,
    column_map: dict[str, str] | None = None,
    extras: dict[str, Any] | None = None,
    post_after_create: bool = False,
) -> BatchJobState:
    """Advance a job through one lifecycle phase and persist via BulkRun."""
    if phase == "intake":
        state = recipe.intake(
            connection_id=connection_id,
            filename=filename,
            headers=headers or [],
            rows=rows or [],
            extras=extras,
        )
        if not state.job_id:
            state.job_id = new_job_id()
        save_job(db, state)
        return state

    if not job_id:
        raise ValueError("job_id required after intake")
    state = load_job(db, job_id)
    if state is None:
        raise LookupError(f"Batch job {job_id} not found")
    if state.connection_id != connection_id:
        raise PermissionError("Job belongs to another connection")

    if phase == "map":
        state = recipe.map(state, column_map)
    elif phase == "validate":
        if client is None:
            raise ValueError("client required for validate")
        state = recipe.validate(state, client)
    elif phase == "dry_run":
        if client is None:
            raise ValueError("client required for dry_run")
        state = recipe.dry_run(state, client)
        state.dry_run = True
    elif phase == "apply":
        if client is None:
            raise ValueError("client required for apply")
        state = recipe.apply(state, client, post_after_create=post_after_create)
        state.dry_run = False
        state.post_after_create = post_after_create
    else:
        raise ValueError(f"Unknown phase {phase!r}")

    save_job(db, state)
    return state


def job_public(db: Session, job_id: str) -> dict[str, Any] | None:
    state = load_job(db, job_id)
    if state is None:
        return None
    return public_job_dict(state)
