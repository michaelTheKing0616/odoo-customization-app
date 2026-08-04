"""FastAPI dependency for TRUST-5 connection mutation lock."""

from __future__ import annotations

from collections.abc import Generator

from fastapi import HTTPException

from app.mutation_lock import ConnectionMutationBusy, connection_mutation_lock


def require_connection_mutation_lock(connection_id: str) -> Generator[None, None, None]:
    try:
        with connection_mutation_lock(connection_id, "mutation"):
            yield
    except ConnectionMutationBusy as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "mutation_in_progress",
                "message": (
                    "Another apply or bulk mutation is already running on this connection. "
                    "Wait for it to finish before starting a new one."
                ),
                "connection_id": exc.connection_id,
                "holder": exc.holder,
            },
        ) from exc
