"""BV-STORE: verify-run store behind BV-01's injected engines.

Rows live in verify_runs / verify_artifacts (migration 4b7e9c1d2a3f). Artifact bytes
live on disk under <data_root>/<workspace>/verify/<run_id>/<artifact_id>.png; the row
holds only that relative path. Every lookup filters by connection and workspace, and
any miss raises the same NOT_FOUND so a foreign id looks exactly like a random one.
Production wiring is left to a later card; tests wire it via dependency_overrides.
"""

from __future__ import annotations

import os
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import (
    Engine,
    Table,
    and_,
    select,
)

from app.bot_verify.contract import ArtifactFn, BVError, GetFn, VerifyRun
from app.bot_verify.models import VerifyArtifactRow, VerifyRunRow
from app.bot_verify.readback import mask
from app.scans.contract import ScanScope

NOT_FOUND_MSG = "Verify run not found."
CONTENT_TYPES = {"image/png": ".png"}
MAX_ARTIFACT_BYTES = 5 * 1024 * 1024
NO_WORKSPACE = "_none"

_SAFE_ID = re.compile(r"[A-Za-z0-9_-]{1,64}")
_SECRET_KEYS = re.compile(r"(secret|token|password|passwd|api_?key|credential|auth)", re.I)
_SECRET_VALUES = re.compile(
    r"(sk-[A-Za-z0-9_-]{8,}|gh[pousr]_[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16}|"
    r"bearer\s+[A-Za-z0-9._-]{8,}|-----BEGIN [A-Z ]*PRIVATE KEY-----)",
    re.I,
)

verify_runs = VerifyRunRow.__table__
verify_artifacts = VerifyArtifactRow.__table__


def _missing() -> BVError:
    return BVError("NOT_FOUND", NOT_FOUND_MSG)


def _safe_id(value: str) -> str:
    if not isinstance(value, str) or not _SAFE_ID.fullmatch(value):
        raise _missing()
    return value


def safe_blob_path(root: Path, rel: str) -> Path:
    """Resolve a relative blob path under root; refuse traversal, absolute, ~, NUL, symlinks out."""
    if not rel or "\x00" in rel or rel.startswith(("~", "/", "\\")) or os.path.isabs(rel):
        raise ValueError("unsafe blob path")
    parts = Path(rel).parts
    if any(p in ("..", ".", "") for p in parts):
        raise ValueError("unsafe blob path")
    base = Path(root).resolve()
    full = (base / rel).resolve()
    if not full.is_relative_to(base):
        raise ValueError("blob path escapes data root")
    return full


def _secret_free(value: Any) -> bool:
    if isinstance(value, dict):
        return all(
            _secret_free(v) and not (_SECRET_KEYS.search(str(k)) and v not in (None, "", "***"))
            for k, v in value.items()
        )
    if isinstance(value, (list, tuple)):
        return all(_secret_free(v) for v in value)
    return not (isinstance(value, str) and _SECRET_VALUES.search(value))


def _scope_where(table: Table, scope: ScanScope) -> Any:
    ws = verify_runs.c.workspace_id
    cond = [table.c.connection_id == scope.connection_id]
    cond.append(ws.is_(None) if scope.workspace_id is None else ws == scope.workspace_id)
    return and_(*cond)


class VerifyStore:
    def __init__(self, engine: Engine, data_root: Path | str) -> None:
        if not data_root:
            raise ValueError("data_root is required")
        self.engine = engine
        self.root = Path(data_root)

    # runs -----------------------------------------------------------------
    def save_run(self, scope: ScanScope, run: VerifyRun) -> None:
        _safe_id(run.run_id)
        layers = run.model_dump(mode="json")["layers"]
        if mask(layers) != layers or not _secret_free(layers):
            raise BVError("VALIDATION", "Evidence must be masked before it is stored.")
        values = {
            "changeset_id": run.changeset_id,
            "status": run.status,
            "layers": layers,
            "started_at": run.started_at,
            "finished_at": run.finished_at,
        }
        with self.engine.begin() as c:
            owner = c.execute(
                select(verify_runs.c.connection_id, verify_runs.c.workspace_id).where(
                    verify_runs.c.run_id == run.run_id
                )
            ).first()
            if owner is None:
                c.execute(
                    verify_runs.insert().values(
                        run_id=run.run_id,
                        connection_id=scope.connection_id,
                        workspace_id=scope.workspace_id,
                        **values,
                    )
                )
                return
            if tuple(owner) != (scope.connection_id, scope.workspace_id):
                raise _missing()
            c.execute(
                verify_runs.update()
                .where(and_(verify_runs.c.run_id == run.run_id, _scope_where(verify_runs, scope)))
                .values(**values)
            )

    def get_run(self, scope: ScanScope, run_id: str) -> VerifyRun:
        _safe_id(run_id)
        with self.engine.connect() as c:
            row = c.execute(
                select(verify_runs).where(
                    and_(verify_runs.c.run_id == run_id, _scope_where(verify_runs, scope))
                )
            ).first()
        if row is None:
            raise _missing()
        return VerifyRun(
            run_id=row.run_id,
            changeset_id=row.changeset_id,
            status=row.status,
            layers=row.layers,
            started_at=row.started_at,
            finished_at=row.finished_at,
        )

    # artifacts ------------------------------------------------------------
    def _insert_artifact(self, conn: Any, values: dict[str, Any]) -> None:
        conn.execute(verify_artifacts.insert().values(**values))

    def put_artifact(self, scope: ScanScope, run_id: str, data: bytes, content_type: str) -> str:
        if content_type not in CONTENT_TYPES:
            raise BVError("VALIDATION", "Only PNG artifacts are stored.")
        if not isinstance(data, bytes) or len(data) > MAX_ARTIFACT_BYTES:
            raise BVError("VALIDATION", "Artifact is too large.")
        self.get_run(scope, run_id)  # NOT_FOUND unless the run is in scope
        artifact_id = str(uuid.uuid4())
        ws = _safe_id(scope.workspace_id) if scope.workspace_id else NO_WORKSPACE
        rel = f"{ws}/verify/{run_id}/{artifact_id}{CONTENT_TYPES[content_type]}"
        final = safe_blob_path(self.root, rel)
        final.parent.mkdir(parents=True, exist_ok=True)
        safe_blob_path(self.root, rel)  # re-check after mkdir (symlinked parents)
        tmp = final.with_name(f".{artifact_id}.tmp")
        tmp.write_bytes(data)
        try:
            with self.engine.begin() as c:
                self._insert_artifact(
                    c,
                    {
                        "artifact_id": artifact_id,
                        "run_id": run_id,
                        "connection_id": scope.connection_id,
                        "blob_path": rel,
                        "content_type": content_type,
                        "created_at": datetime.now(UTC),
                    },
                )
            os.replace(tmp, final)
        except BaseException:
            tmp.unlink(missing_ok=True)
            raise
        return artifact_id

    def get_artifact(self, scope: ScanScope, run_id: str, artifact_id: str) -> bytes:
        _safe_id(run_id)
        _safe_id(artifact_id)
        a, rn = verify_artifacts, verify_runs
        with self.engine.connect() as c:
            row = c.execute(
                select(a.c.blob_path)
                .select_from(a.join(rn, a.c.run_id == rn.c.run_id))
                .where(
                    and_(
                        a.c.artifact_id == artifact_id,
                        a.c.run_id == run_id,
                        a.c.connection_id == scope.connection_id,
                        _scope_where(rn, scope),
                    )
                )
            ).first()
        if row is None:
            raise _missing()
        try:
            return safe_blob_path(self.root, row.blob_path).read_bytes()
        except (ValueError, OSError):
            raise _missing() from None


def get_engine_from_store(store: VerifyStore) -> GetFn:
    return store.get_run


def artifact_engine_from_store(store: VerifyStore) -> ArtifactFn:
    return store.get_artifact
