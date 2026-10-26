"""Exact diff preview for a Bot write plan, read from the live DB (BOT-DIFF-BLAST AC1/AC6).

Reads only, through ``ReadOnly`` (method allow-list; anything else raises). One entry per
record x field that would change: {model, id, field, old, new}. Secret fields/values are
masked in the payload. ``readback`` is the WriteGate readback: it re-reads a chunk and
compares to the planned new values (any mismatch or read error -> False -> kill switch).
Supported value shapes (fail closed otherwise): scalars, many2one id/False, and x2many
``[(6, 0, ids)]`` (Command.set). Clean-room: public ORM methods over RPC only.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from app.bots.audit import REDACTED, find_secret
from app.bots.risk.rules import CREDENTIAL_TOKENS, MAGIC_FIELDS, Refusal, credential_match

Rpc = Callable[[str, str, Sequence[Any], dict[str, Any] | None], Any]
READ_METHODS = frozenset({"read", "search", "search_read", "search_count", "fields_get"})
X2MANY = ("one2many", "many2many")
NO_ACTIVE_TEST = {"active_test": False}


class ReadOnly:
    """Wraps an RPC callable so this module can only ever read."""

    def __init__(self, rpc: Rpc) -> None:
        self._rpc = rpc

    def __call__(self, model: str, method: str, args: Sequence[Any], kw: dict | None = None):
        if method not in READ_METHODS:
            raise PermissionError(f"read-only preview refused method {method!r}")
        return self._rpc(model, method, list(args), kw or {})


class DiffRefused(Exception):
    def __init__(self, refusal: Refusal) -> None:
        super().__init__(refusal.text())
        self.refusal = refusal


@dataclass(frozen=True)
class Entry:
    model: str
    id: int
    field: str
    old: Any
    new: Any
    masked: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "id": self.id,
            "field": self.field,
            "old": self.old,
            "new": self.new,
        }


@dataclass(frozen=True)
class Diff:
    model: str
    ids: tuple[int, ...]
    values_shape: tuple[tuple[str, str], ...]  # (field, ttype)
    entries: tuple[Entry, ...]
    unchanged: tuple[int, ...]  # ids where nothing would change
    recompute: tuple[str, ...]  # stored computed fields (model.field) depending on a changed one
    versions: tuple[tuple[int, str], ...] = ()  # (id, write_date): any concurrent edit = stale

    def payload(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "ids": list(self.ids),
            "entries": [e.as_dict() for e in self.entries],
            "unchanged": list(self.unchanged),
            "recompute": list(self.recompute),
            "versions": [list(v) for v in self.versions],
        }


def _refuse(missing: str, reason: str) -> DiffRefused:
    return DiffRefused(Refusal("RF-ANY", missing, reason[:180]))


# Masking only (wider than the risk floors, which stay tied to catalogue_rows.json):
PIN_TOKENS = CREDENTIAL_TOKENS | {"pin", "pins", "pincode", "passcode", "cvv", "iban"}


def secret(model: str, field: str, value: Any) -> bool:
    tokens = set(field.lower().split("_"))
    return (
        bool(tokens & PIN_TOKENS)
        or credential_match(model, field)
        or (isinstance(value, str) and find_secret(value))
    )


def summarise(v: Any) -> Any:
    if not v:
        return v
    b = v.encode() if isinstance(v, str) else bytes(v)
    try:
        n = len(base64.b64decode(b, validate=True))  # Odoo sends binary as base64 text
    except (binascii.Error, ValueError):
        n = len(b)
    return {"bytes": n, "sha256": hashlib.sha256(b).hexdigest()}


def norm_read(ttype: str, v: Any) -> Any:
    """Normalise a read() value to the shape a plan writes."""
    if ttype == "many2one":
        return v[0] if isinstance(v, list | tuple) and v else (v or False)
    if ttype in X2MANY:
        return sorted(v or [])
    return v


def norm_new(ttype: str, v: Any) -> Any:
    if ttype == "many2one":
        if v is False or (isinstance(v, int) and not isinstance(v, bool) and v > 0):
            return v
        raise _refuse("diff-shape", f"many2one value must be id or False, got {type(v).__name__}")
    if ttype in X2MANY:
        ok = (
            isinstance(v, list | tuple)
            and len(v) == 1
            and isinstance(v[0], list | tuple)
            and len(v[0]) == 3
            and v[0][0] == 6
            and isinstance(v[0][2], list | tuple)
            and all(isinstance(i, int) and not isinstance(i, bool) for i in v[0][2])
        )
        if not ok:
            raise _refuse(
                "diff-shape",
                "x2many value must be [(6, 0, ids)]: other commands "
                "have effects a diff cannot show",
            )
        return sorted(v[0][2])
    if isinstance(v, list | tuple | dict):
        raise _refuse("diff-shape", f"unsupported value shape for {ttype}")
    return v


def same(ttype: str, a: Any, b: Any) -> bool:
    if ttype in ("float", "monetary") and isinstance(a, int | float) and isinstance(b, int | float):
        return abs(float(a) - float(b)) <= 1e-9 * max(1.0, abs(float(a)), abs(float(b)))
    return a == b


def _ids(ids: Sequence[Any]) -> tuple[int, ...]:
    out = tuple(dict.fromkeys(ids))
    if not out or any(not isinstance(i, int) or isinstance(i, bool) or i < 1 for i in out):
        raise _refuse("diff-ids", "record ids must be positive ints (and at least one)")
    return out


def _meta(read: Rpc, model: str, fields: Sequence[str]) -> dict[str, dict[str, Any]]:
    meta = read(
        model,
        "fields_get",
        [list(fields)],
        {"attributes": ["type", "readonly", "store", "relation"]},
    )
    missing = [f for f in fields if f not in (meta or {})]
    if missing:
        raise _refuse("diff-field", f"{model} has no field(s) {missing}")
    return meta


def _read(read: Rpc, model: str, ids: Sequence[int], fields: Sequence[str]) -> dict[int, dict]:
    rows = read(model, "read", [list(ids), list(fields)], {"context": NO_ACTIVE_TEST}) or []
    got = {r["id"]: r for r in rows}
    if set(got) != set(ids):
        raise _refuse("diff-ids", f"{len(set(ids) - set(got))} record(s) missing or unreadable")
    return got


def _recompute(read: Rpc, model: str, fields: Sequence[str]) -> tuple[str, ...]:
    """Stored computed fields whose declared depends mention a changed field (any model)."""
    out: set[str] = set()
    for f in fields:
        rows = (
            read(
                "ir.model.fields",
                "search_read",
                [[("store", "=", True), ("depends", "ilike", f)]],
                {"fields": ["model", "name", "depends"], "limit": 2000},
            )
            or []
        )
        for r in rows:
            deps = {d.strip() for d in str(r.get("depends") or "").split(",")}
            if any(d == f or d.startswith(f + ".") or d.endswith("." + f) for d in deps):
                out.add(f"{r['model']}.{r['name']}")
    return tuple(sorted(out))


def build_diff(rpc: Rpc, model: str, ids: Sequence[Any], values: dict[str, Any]) -> Diff:
    """Raises DiffRefused (fail closed) on any shape, field, id or read problem."""
    read = rpc if isinstance(rpc, ReadOnly) else ReadOnly(rpc)
    rids = _ids(ids)
    if not isinstance(values, dict) or not values:
        raise _refuse("diff-shape", "values must be a non-empty dict")
    bad = sorted(set(values) & MAGIC_FIELDS)
    if bad:
        raise _refuse("diff-field", f"magic fields cannot be planned: {bad}")
    fields = sorted(values)
    try:
        meta = _meta(read, model, fields)
        shape = tuple((f, str(meta[f].get("type"))) for f in fields)
        new = {f: norm_new(t, values[f]) for f, t in shape}
        for f, _t in shape:
            if meta[f].get("readonly") and meta[f].get("store") is False:
                raise _refuse("diff-field", f"{model}.{f} is computed, not stored: not writable")
        rows = _read(read, model, rids, [*fields, "write_date"])
        entries, unchanged = [], []
        for rid in rids:
            n = 0
            for f, t in shape:
                old = norm_read(t, rows[rid].get(f))
                if same(t, old, new[f]):
                    continue
                n += 1
                if t == "binary":  # never raw base64 in a preview: size + hash
                    entries.append(Entry(model, rid, f, summarise(old), summarise(new[f]), True))
                elif secret(model, f, old) or secret(model, f, new[f]):
                    entries.append(Entry(model, rid, f, REDACTED, REDACTED, True))
                else:
                    entries.append(Entry(model, rid, f, old, new[f]))
            if not n:
                unchanged.append(rid)
        rec = _recompute(read, model, [f for f, _ in shape])
    except DiffRefused:
        raise
    except Exception as exc:  # noqa: BLE001 - access error, transport: refuse, never guess
        raise _refuse("diff-read", f"diff not readable: {type(exc).__name__}") from None
    vers = tuple((i, str(rows[i].get("write_date") or "")) for i in rids)
    return Diff(model, rids, shape, tuple(entries), tuple(unchanged), rec, vers)


def readback(rpc: Rpc, diff: Diff, values: dict[str, Any]) -> Callable[[Sequence[Any]], bool]:
    """WriteGate readback: True only if every planned field reads back as planned."""
    read = rpc if isinstance(rpc, ReadOnly) else ReadOnly(rpc)
    new = {f: norm_new(t, values[f]) for f, t in diff.values_shape}
    planned = set(diff.ids)

    def check(chunk: Sequence[Any]) -> bool:
        try:
            if not chunk or not set(chunk) <= planned:
                return False
            rows = _read(read, diff.model, list(chunk), list(new))
            return all(
                same(t, norm_read(t, rows[i].get(f)), new[f])
                for i in chunk
                for f, t in diff.values_shape
            )
        except Exception:  # noqa: BLE001 - unreadable = mismatch
            return False

    return check


def canonical_hash(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()
