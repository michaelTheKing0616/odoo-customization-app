"""Route B (direct-database targets): pg_dump + filestore snapshot, restore-verified.

``take`` writes <dir>/<db>-<ts>.dump (pg_dump -Fc via ``database_backup.pg_dump_argv``) and a
filestore tar, sha256 of each, with the DB fingerprint, taken_at and source row counts of the
touched tables + ir_attachment. The id is ``snap:<sha256(manifest)>`` (goes in bot_audit
snapshot_id). ``verify`` refuses ("snapshot-proof") a missing/corrupt/byte-flipped file, a
manifest that no longer hashes to its id, another DB fingerprint or a stale snapshot; then it
restores into a fresh ``ingenium_scratch_*`` DB (name collision -> new name), compares the
counts, checks the tar, and always drops the scratch DB. A failed or killed dump leaves no id.
No automatic restore onto production (runbook only).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import shutil
import subprocess
import tarfile
import time
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol

from app.bots.risk.rules import Refusal
from app.database_backup import pg_dump_argv

SNAPSHOT_MAX_AGE_S = 6 * 3600
MIN_FREE_BYTES = 256 * 1024 * 1024
SCRATCH_RX = re.compile(r"^ingenium_scratch_[0-9a-f]{12}$")
_TABLE = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")


class SnapshotError(RuntimeError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.refusal = Refusal("RF-R3", "snapshot-proof", reason)


class SnapshotOps(Protocol):
    def dump(self, db: str, out: Path) -> None: ...
    def filestore_tar(self, db: str, out: Path) -> None: ...
    def restore(self, dump: Path, scratch: str) -> None: ...
    def counts(self, db: str, tables: Sequence[str]) -> dict[str, int]: ...
    def db_exists(self, name: str) -> bool: ...
    def drop(self, scratch: str) -> None: ...


@dataclass(frozen=True)
class Snapshot:
    id: str
    db: str
    fingerprint: str
    dump: str
    dump_sha: str
    filestore: str
    filestore_sha: str
    taken_at: float
    counts: dict[str, int]
    mac: str = ""  # HMAC(process key, id): only take() here can sign a manifest


def _sha(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def _manifest(d: dict) -> str:
    body = {k: v for k, v in d.items() if k not in ("id", "mac")}
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()


_KEY = secrets.token_bytes(32)  # same handling as before_image proofs: process-held


def _sign(sid: str) -> str:
    return hmac.new(_KEY, sid.encode(), hashlib.sha256).hexdigest()


def _tables(tables: Sequence[str]) -> list[str]:
    out = sorted({*tables, "ir_attachment"})
    if not all(_TABLE.match(t) for t in out):
        raise SnapshotError("bad table name")
    return out


def take(
    ops: SnapshotOps,
    db: str,
    fingerprint: str,
    out_dir: Path,
    tables: Sequence[str],
    *,
    now: Callable[[], float] = time.time,
    min_free: int = MIN_FREE_BYTES,
) -> Snapshot:
    ts = _tables(tables)
    out_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    if shutil.disk_usage(out_dir).free < min_free:
        raise SnapshotError("disk space below the snapshot floor")
    stem = f"{db}-{int(now())}-{secrets.token_hex(4)}"
    dump, fs, man = (out_dir / f"{stem}{s}" for s in (".dump", ".filestore.tar", ".json"))
    try:
        counts = ops.counts(db, ts)
        ops.dump(db, dump)
        ops.filestore_tar(db, fs)
        if not dump.exists() or dump.stat().st_size == 0 or not fs.exists():
            raise SnapshotError("dump incomplete")
        for p in (dump, fs):
            os.chmod(p, 0o600)  # full DB + filestore: owner only
        d = dict(
            db=db,
            fingerprint=fingerprint,
            dump=str(dump),
            dump_sha=_sha(dump),
            filestore=str(fs),
            filestore_sha=_sha(fs),
            taken_at=now(),
            counts=counts,
        )
        d["id"] = "snap:" + _manifest(d)
        d["mac"] = _sign(d["id"])
        man.write_text(json.dumps(d, sort_keys=True))
        os.chmod(man, 0o600)
    except Exception as exc:  # killed dump, ENOSPC, ...: no id, no partial files
        for p in (dump, fs, man):
            p.unlink(missing_ok=True)
        if isinstance(exc, SnapshotError):
            raise
        raise SnapshotError(f"snapshot failed: {type(exc).__name__}") from exc
    return Snapshot(**d)


def load(manifest: Path) -> Snapshot:
    try:
        return Snapshot(**json.loads(manifest.read_text()))
    except Exception as exc:  # noqa: BLE001
        raise SnapshotError("snapshot manifest unreadable") from exc


def _scratch(ops: SnapshotOps) -> str:
    for _ in range(20):
        name = f"ingenium_scratch_{secrets.token_hex(6)}"
        if not ops.db_exists(name):
            return name
    raise SnapshotError("no free scratch name")


def verify(
    ops: SnapshotOps,
    snap: Snapshot,
    fingerprint: str,
    *,
    now: Callable[[], float] = time.time,
    max_age_s: float = SNAPSHOT_MAX_AGE_S,
) -> Refusal | None:
    """None = restore verified. Every failure is a 'snapshot-proof' refusal."""
    try:
        d = asdict(snap)
        if snap.id != "snap:" + _manifest(d):
            raise SnapshotError("snapshot manifest altered")
        if not hmac.compare_digest(snap.mac or "", _sign(snap.id)):
            raise SnapshotError("snapshot manifest signature invalid")
        if snap.fingerprint != fingerprint:
            raise SnapshotError("snapshot is of another database (fingerprint)")
        if now() - snap.taken_at > max_age_s:
            raise SnapshotError("snapshot stale")
        dump, fs = Path(snap.dump), Path(snap.filestore)
        if not dump.exists() or not fs.exists():
            raise SnapshotError("snapshot file missing")
        if _sha(dump) != snap.dump_sha or _sha(fs) != snap.filestore_sha:
            raise SnapshotError("snapshot hash mismatch (corrupt)")
        try:
            with tarfile.open(fs) as t:
                t.getmembers()
        except (tarfile.TarError, OSError) as exc:
            raise SnapshotError("filestore tar unreadable") from exc
        scratch = _scratch(ops)
        assert SCRATCH_RX.match(scratch)
        try:
            ops.restore(dump, scratch)
            got = ops.counts(scratch, list(snap.counts))
        finally:
            try:
                ops.drop(scratch)
            except Exception:  # noqa: BLE001 - reported below
                got = None
        if got is None:
            raise SnapshotError("scratch drop failed")
        if got != snap.counts:
            raise SnapshotError(
                f"restored counts differ {sorted(set(got.items()) ^ set(snap.counts.items()))[:4]}"
            )
    except SnapshotError as exc:
        return exc.refusal
    except Exception as exc:  # noqa: BLE001 - restore error = not verified
        return Refusal("RF-R3", "snapshot-proof", f"restore failed: {type(exc).__name__}")
    return None


class Verified:
    """rules.gate_with_proofs check for Route B: snapshot-proof only after ``verify`` passed."""

    def __init__(self, ops: SnapshotOps, snap: Snapshot, fingerprint: str) -> None:
        self.snap = snap
        self.refusal = verify(ops, snap, fingerprint)

    def __call__(self, control: str) -> bool:
        return control == "snapshot-proof" and self.refusal is None


def _run(argv: list[str], **kw) -> subprocess.CompletedProcess:
    cp = subprocess.run(argv, capture_output=True, timeout=3600, check=False, **kw)
    if cp.returncode != 0:
        raise RuntimeError(f"{argv[:3]} rc={cp.returncode}: {cp.stderr[-300:]!r}")
    return cp


class ContainerOps:
    """SnapshotOps over ``docker exec`` (Postgres + Odoo containers; no host DB port)."""

    def __init__(self, db_container: str, odoo_container: str, user: str = "odoo") -> None:
        self.db, self.odoo, self.user = db_container, odoo_container, user

    def _psql(self, db: str, q: str) -> str:
        argv = ["docker", "exec", self.db, "psql", "-U", self.user, "-d", db]
        return _run([*argv, "-v", "ON_ERROR_STOP=1", "-tAc", q], text=True).stdout

    def dump(self, db: str, out: Path) -> None:
        with out.open("wb") as f:
            cp = subprocess.run(
                ["docker", "exec", self.db, *pg_dump_argv(db, user=self.user)],
                stdout=f,
                stderr=subprocess.PIPE,
                timeout=3600,
                check=False,
            )
        if cp.returncode != 0:
            raise RuntimeError(f"pg_dump rc={cp.returncode}")

    def filestore_tar(self, db: str, out: Path) -> None:
        fs = "/var/lib/odoo/filestore"
        sh = f"cd {fs} 2>/dev/null && [ -d '{db}' ] && tar -cf - '{db}' || tar -cf - -T /dev/null"
        with out.open("wb") as f:
            cp = subprocess.run(
                ["docker", "exec", self.odoo, "sh", "-c", sh],
                stdout=f,
                stderr=subprocess.PIPE,
                timeout=3600,
                check=False,
            )
        if cp.returncode != 0:
            raise RuntimeError(f"tar rc={cp.returncode}")

    def restore(self, dump: Path, scratch: str) -> None:
        assert SCRATCH_RX.match(scratch)
        self._psql("postgres", f'CREATE DATABASE "{scratch}"')
        with dump.open("rb") as f:
            argv = ["pg_restore", "-U", self.user, "--no-owner", "--exit-on-error", "-d", scratch]
            _run(["docker", "exec", "-i", self.db, *argv], stdin=f)

    def counts(self, db: str, tables: Sequence[str]) -> dict[str, int]:
        ts = _tables(tables) if "ir_attachment" not in tables else list(tables)
        q = " UNION ALL ".join(f"SELECT '{t}', count(*) FROM {t}" for t in ts)
        rows = [r.split("|") for r in self._psql(db, q).split()]
        return {t: int(n) for t, n in rows}

    def db_exists(self, name: str) -> bool:
        return self._psql("postgres", f"SELECT 1 FROM pg_database WHERE datname='{name}'") != ""

    def drop(self, scratch: str) -> None:
        assert SCRATCH_RX.match(scratch)
        self._psql("postgres", f'DROP DATABASE IF EXISTS "{scratch}" WITH (FORCE)')
