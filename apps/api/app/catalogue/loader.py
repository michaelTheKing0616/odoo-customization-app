"""Strict, fail-closed loader for the checked-in task catalogue (data/catalogue.csv).

The CSV is data, never code: it is hash-pinned by data/catalogue.meta.json, every row is
validated against a closed schema, and any deviation raises CatalogueError (no partial
load, no best-effort rows). The risk class here is the catalogue's name-derived class;
the authoritative per-button decision stays with app.bots.risk.classifier.

Refresh (operator only): python -m app.catalogue --import <path/to/catalogue.csv>
which validates the source first, then swaps data + meta in via temp files and rename.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).with_name("data")
CSV_FILE = DATA_DIR / "catalogue.csv"
META_FILE = DATA_DIR / "catalogue.meta.json"

COLUMNS = (
    "id",
    "area",
    "verb",
    "object",
    "tier",
    "versions",
    "prerequisites",
    "risk_class",
    "risk_name",
    "reversibility",
    "blast",
    "controls",
    "verification",
    "source",
    "note",
)
VERSIONS = frozenset({17, 18, 19, 20})
TIERS = frozenset({"T1", "T2", "T3"})
ID_KINDS = frozenset(
    {"m", "c", "v", "mod", "b", "s", "sa", "g", "wiz", "t", "r", "cron", "code", "seq", "param"}
)
# Fixed risk profile per class (RISK_MODEL.md). A row whose name/reversibility/blast
# disagrees with its class is drift and is refused: a mislabeled class must never load.
CLASS_PROFILE: Mapping[str, tuple[str, str, str]] = {
    "R0": ("read-only", "n/a", "none"),
    "R1": ("draft data create/edit", "reversible", "low"),
    "R2": ("settings toggle (non-structural)", "reversible", "medium"),
    "R2W": ("workflow transition (non-financial)", "reversible-by-counter-action", "medium"),
    "R3": ("bulk write / import overwrite", "recoverable-only-from-snapshot", "high"),
    "R4": (
        "financial/stock posting, valuation, locking",
        "IRRECOVERABLE-on-prod (only counter-documents)",
        "high",
    ),
    "R5": ("external side effect (email/SMS/e-invoice/payment/webhook)", "IRRECOVERABLE", "high"),
    "R6": ("delete / merge / cascade", "IRRECOVERABLE without snapshot", "high"),
    "R7": (
        "structural metadata / module install / customization",
        "recoverable-with-upgrade/rollback",
        "high",
    ),
    "R8": ("security / users / groups / auth", "recoverable but lockout risk", "critical"),
    "R8C": (
        "company/currency/tax/chart/fiscal/sequence/localization",
        "often IRRECOVERABLE once transactions exist",
        "critical",
    ),
    "R9": (
        "module uninstall / data-dropping upgrade",
        "IRRECOVERABLE (drops tables/columns)",
        "critical",
    ),
}
# Every class above R2 must carry an explicit human approval (or a forbid/refuse rule).
_APPROVAL = re.compile(r"human-approve-L[123]|FORBIDDEN|REFUSE")
_ID = re.compile(r"^([a-z]+):([A-Za-z0-9_. &(),/:-]+)$")
_SAFE = re.compile(r"^[\x20-\x7e]*$")  # printable ASCII only: no NUL/CR/LF/tab/unicode tricks
_FORMULA = ("=", "+", "-", "@")
MAX_ROWS = 50_000
MAX_CELL = 512


class CatalogueError(ValueError):
    """The catalogue data is missing, tampered with, or fails the schema. Never partial."""


@dataclass(frozen=True, slots=True)
class Task:
    id: str
    area: str
    verb: str
    object: str
    tier: str
    versions: frozenset[int]
    prerequisites: str
    risk_class: str
    risk_name: str
    reversibility: str
    blast: str
    controls: tuple[str, ...]
    verification: str
    source: str
    note: str


@dataclass(frozen=True, slots=True)
class Catalogue:
    sha256: str
    tasks: tuple[Task, ...]
    index: Mapping[str, Task]


def _fail(line: int, msg: str) -> CatalogueError:
    return CatalogueError(f"catalogue row {line}: {msg}")


def _row(line: int, cells: list[str]) -> Task:
    if len(cells) != len(COLUMNS):
        raise _fail(line, f"expected {len(COLUMNS)} cells, got {len(cells)}")
    r = dict(zip(COLUMNS, cells, strict=True))
    for k, v in r.items():
        if len(v) > MAX_CELL or not _SAFE.match(v):
            raise _fail(line, f"{k}: unsafe or oversized cell")
        if v != v.strip():
            raise _fail(line, f"{k}: leading/trailing whitespace")
        if v.startswith(_FORMULA) and k not in ("note",):
            raise _fail(line, f"{k}: formula-like cell")
    if r["note"].startswith(_FORMULA):
        raise _fail(line, "note: formula-like cell")
    m = _ID.match(r["id"])
    if not m or m.group(1) not in ID_KINDS:
        raise _fail(line, f"bad id {r['id']!r}")
    for k in ("area", "verb", "object", "risk_class", "controls", "verification", "source"):
        if not r[k]:
            raise _fail(line, f"{k}: empty")
    if r["tier"] not in TIERS:
        raise _fail(line, f"bad tier {r['tier']!r}")
    try:
        vs = [int(v) for v in r["versions"].split("|")]
    except ValueError:
        raise _fail(line, f"bad versions {r['versions']!r}") from None
    if not vs or len(set(vs)) != len(vs) or vs != sorted(vs) or not set(vs) <= VERSIONS:
        raise _fail(line, f"bad versions {r['versions']!r}")
    prof = CLASS_PROFILE.get(r["risk_class"])
    if prof is None:
        raise _fail(line, f"unknown risk class {r['risk_class']!r}")
    if (r["risk_name"], r["reversibility"], r["blast"]) != prof:
        raise _fail(line, f"{r['risk_class']} profile drift")
    controls = tuple(r["controls"].split(";"))
    if (
        any(not c for c in controls)
        or len(set(controls)) != len(controls)
        or "audit" not in controls
    ):
        raise _fail(line, "controls must be distinct, non-empty and include audit")
    if r["risk_class"] not in ("R0", "R1", "R2") and not _APPROVAL.search(r["controls"]):
        raise _fail(line, f"{r['risk_class']} without human approval control")
    return Task(
        id=r["id"],
        area=r["area"],
        verb=r["verb"],
        object=r["object"],
        tier=r["tier"],
        versions=frozenset(vs),
        prerequisites=r["prerequisites"],
        risk_class=r["risk_class"],
        risk_name=r["risk_name"],
        reversibility=r["reversibility"],
        blast=r["blast"],
        controls=controls,
        verification=r["verification"],
        source=r["source"],
        note=r["note"],
    )


def parse(raw: bytes, expected_sha256: str | None = None) -> Catalogue:
    """Validate raw CSV bytes. All-or-nothing; raises CatalogueError on any defect."""
    sha = hashlib.sha256(raw).hexdigest()
    if expected_sha256 is not None and sha != expected_sha256:
        raise CatalogueError(
            "catalogue.csv sha256 does not match catalogue.meta.json (tampered or stale)"
        )
    if raw.startswith(b"\xef\xbb\xbf"):
        raise CatalogueError("catalogue.csv must not carry a BOM")
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError:
        raise CatalogueError("catalogue.csv must be ASCII") from None
    reader = csv.reader(io.StringIO(text, newline=""), strict=True)
    try:
        header = next(reader)
    except (StopIteration, csv.Error):
        raise CatalogueError("catalogue.csv is empty or malformed") from None
    if tuple(header) != COLUMNS:
        raise CatalogueError("catalogue.csv header does not match the schema")
    tasks: list[Task] = []
    index: dict[str, Task] = {}
    try:
        for line, cells in enumerate(reader, start=2):
            if len(tasks) >= MAX_ROWS:
                raise CatalogueError("catalogue.csv exceeds the row cap")
            t = _row(line, cells)
            if t.id in index:
                raise _fail(line, f"duplicate id {t.id!r}")
            index[t.id] = t
            tasks.append(t)
    except csv.Error as e:
        raise CatalogueError(f"catalogue.csv is malformed: {e}") from None
    if not tasks:
        raise CatalogueError("catalogue.csv has no rows")
    _uniform_controls(tasks)
    return Catalogue(sha256=sha, tasks=tuple(tasks), index=index)


def _uniform_controls(tasks: list[Task]) -> None:
    # One control set per class: a single row with weaker controls than its siblings is drift.
    seen: dict[str, tuple[str, ...]] = {}
    for t in tasks:
        if seen.setdefault(t.risk_class, t.controls) != t.controls:
            raise CatalogueError(f"{t.id}: controls differ from other {t.risk_class} rows")


def _meta() -> dict:
    try:
        meta = json.loads(META_FILE.read_text())
    except (OSError, ValueError):
        raise CatalogueError("catalogue.meta.json missing or unreadable") from None
    if not isinstance(meta, dict) or not re.fullmatch(r"[0-9a-f]{64}", str(meta.get("sha256", ""))):
        raise CatalogueError("catalogue.meta.json is malformed")
    return meta


@lru_cache(maxsize=1)
def load() -> Catalogue:
    meta = _meta()
    try:
        raw = CSV_FILE.read_bytes()
    except OSError:
        raise CatalogueError("catalogue.csv missing") from None
    cat = parse(raw, meta["sha256"])
    if meta.get("rows") != len(cat.tasks):
        raise CatalogueError("catalogue.meta.json row count does not match the data")
    return cat


def by_id(task_id: str) -> Task | None:
    return load().index.get(task_id)


def tasks_for_version(version: int) -> tuple[Task, ...]:
    if version not in VERSIONS:
        raise CatalogueError(f"unsupported Odoo version {version!r}")
    return tuple(t for t in load().tasks if version in t.versions)


def _atomic_write(path: Path, data: bytes) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def import_csv(src: Path) -> Catalogue:
    """Validate src fully, then swap data and meta in atomically (data first, meta last)."""
    raw = Path(src).read_bytes()
    cat = parse(raw)
    meta = {
        "source": "catalogue.csv",
        "sha256": cat.sha256,
        "rows": len(cat.tasks),
        "columns": list(COLUMNS),
    }
    _atomic_write(CSV_FILE, raw)
    _atomic_write(META_FILE, (json.dumps(meta, indent=1) + "\n").encode())
    load.cache_clear()
    return cat
