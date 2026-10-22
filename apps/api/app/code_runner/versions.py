"""Side-by-side view of one model across Odoo 17/18/19/20 connections."""

from __future__ import annotations

from typing import Any


def compare(per_version: dict[str, dict[str, dict[str, Any]] | None]) -> dict[str, Any]:
    """per_version: {"17": fields_get or None (model missing)} → rows of field presence/type per version."""
    versions = sorted(per_version, key=lambda v: int(v) if v.isdigit() else 0)
    names = sorted({n for f in per_version.values() if f for n in f})
    rows = []
    for n in names:
        cells = {v: ({"type": per_version[v][n].get("type"), "string": per_version[v][n].get("string")}
                     if per_version[v] and n in per_version[v] else None) for v in versions}
        types = {c["type"] for c in cells.values() if c}
        rows.append({"field": n, "cells": cells,
                     "differs": any(c is None for c in cells.values()) or len(types) > 1})
    return {"versions": versions, "missing_model": [v for v in versions if per_version[v] is None],
            "rows": rows, "differing": sum(1 for r in rows if r["differs"])}
